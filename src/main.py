"""SOP LLM Service - Main Entry Point.

Главная точка входа приложения.
Следует принципам async-first архитектуры и стандартам wiki-engine.
"""

import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import uvicorn
import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Импорты из новой структуры
from src.core.config import settings
from src.core.constants import API_PREFIX, API_VERSION
from src.shared.logging import setup_logger
from src.shared.errors import setup_exception_handlers
from src.shared.errors.context import get_trace_id, set_trace_id
from src.shared.cache import redis_cache
from src.api import router as api_router
from src.modules.monitoring import websocket_endpoint
from src.modules.llm.services import (
    llm_manager,
    embedding_manager,
    unified_llm,
    json_fixer,
    provider_manager,
)


class TraceContextMiddleware:
    """Middleware для установки trace_id в контекст запроса."""

    def __init__(self, app: Any) -> None:
        """Инициализация middleware.

        Args:
            app: FastAPI приложение.

        """
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """Обработка запроса с установкой trace_id.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.

        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Генерируем или извлекаем trace_id
        headers = dict(scope.get("headers", []))
        trace_id = headers.get(b"x-trace-id", b"").decode() or str(uuid4())

        # Устанавливаем в контекст
        set_trace_id(trace_id)

        # Добавляем в scope для доступа в обработчиках
        scope["state"] = getattr(scope, "state", {})
        scope["state"]["trace_id"] = trace_id

        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Менеджер жизненного цикла приложения.

    Управляет запуском и остановкой всех компонентов системы:
    - Инициализация логирования
    - Подключение к Redis
    - Загрузка провайдеров и моделей
    - Graceful shutdown

    Args:
        app: Экземпляр FastAPI приложения.

    Yields:
        Управление приложением во время его работы.

    Raises:
        Exception: При критических ошибках инициализации.

    """
    logger.info(f"Запуск {settings.app_name}...")
    logger.info(f"Окружение: {settings.environment}")
    logger.info(f"Режим отладки: {settings.debug}")

    try:
        # Подключаемся к Redis
        logger.info("Подключение к Redis...")
        try:
            await redis_cache.connect()
            logger.success("Redis подключен успешно")
        except Exception as e:
            logger.error(f"Не удалось подключиться к Redis: {e}")
            if settings.environment == "prod":
                logger.error("Redis критичен для production - приложение не будет запущено")
                sys.exit(1)
            logger.warning("Продолжаем без Redis (development mode)")

        # Загружаем провайдеров из конфигурации
        logger.info("Инициализация ProviderManager...")
        try:
            providers_config_path = Path(__file__).parent.parent / "config" / "providers.yaml"

            if providers_config_path.exists():
                with open(providers_config_path, "r", encoding="utf-8") as f:
                    providers_yaml = yaml.safe_load(f)
                    providers_config = providers_yaml.get("providers", [])

                await provider_manager.initialize(providers_config)
                logger.success(
                    f"ProviderManager инициализирован с {len(provider_manager.providers)} провайдерами: "
                    f"{list(provider_manager.providers.keys())}"
                )
            else:
                logger.warning(
                    f"Конфигурация провайдеров не найдена: {providers_config_path}"
                )
        except Exception as e:
            logger.error(f"Не удалось инициализировать ProviderManager: {e}", exc_info=True)
            logger.warning("Приложение продолжит работу с ограниченным функционалом")

        # Загружаем LLM модель
        logger.info("Загрузка LLM модели...")
        try:
            await llm_manager.load_model()
            logger.success(f"LLM модель загружена: {settings.llm.default_model}")
        except Exception as e:
            logger.error(f"Не удалось загрузить LLM модель: {e}", exc_info=True)
            if settings.environment == "prod":
                logger.error("LLM модель критична для production")
                sys.exit(1)

        # Загружаем Embedding модель
        logger.info("Загрузка Embedding модели...")
        try:
            await embedding_manager.load_model()
            logger.success(f"Embedding модель загружена: {settings.llm.default_embedding_model}")
        except Exception as e:
            logger.error(f"Не удалось загрузить Embedding модель: {e}", exc_info=True)

        # Загружаем JSON Fixer модель если включен в настройках
        if settings.json_fixer.enabled:
            logger.info("Загрузка JSON Fixer модели...")
            try:
                await json_fixer.load_model()
                logger.success(
                    f"JSON Fixer модель загружена: {settings.json_fixer.model} "
                    f"(8-bit: {settings.json_fixer.load_in_8bit})"
                )
            except Exception as e:
                logger.warning(f"Не удалось загрузить JSON Fixer модель: {e}")
                logger.warning("JSON Fixer будет использовать lazy loading")
        else:
            logger.info("JSON Fixer отключен в настройках")

        # Инициализируем UnifiedLLM (включая Claude API если настроен)
        logger.info("Инициализация унифицированного LLM интерфейса...")
        try:
            await unified_llm.initialize()
            logger.success("UnifiedLLM инициализирован")
        except Exception as e:
            logger.error(f"Не удалось инициализировать UnifiedLLM: {e}", exc_info=True)

        logger.success(f"{settings.app_name} успешно запущен!")
        logger.info(f"API доступен по адресу: http://{settings.server.host}:{settings.server.port}{API_PREFIX}")
        logger.info(f"Документация: http://{settings.server.host}:{settings.server.port}/docs")

        yield

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске приложения: {e}", exc_info=True)
        raise

    finally:
        logger.info("Завершение работы приложения...")

        # Очистка ProviderManager
        try:
            await provider_manager.cleanup()
            logger.info("ProviderManager очищен")
        except Exception as e:
            logger.error(f"Ошибка при очистке ProviderManager: {e}")

        # Отключаемся от Redis
        try:
            await redis_cache.disconnect()
            logger.info("Redis отключен")
        except Exception as e:
            logger.error(f"Ошибка при отключении Redis: {e}")

        logger.success("Завершение работы выполнено")


def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения.

    Создает экземпляр FastAPI с настроенными:
    - Middleware (CORS, timing, trace_id)
    - Exception handlers
    - API роутерами
    - WebSocket endpoints

    Returns:
        Настроенный экземпляр FastAPI приложения.

    """
    # Инициализируем логирование перед созданием приложения
    setup_logger()

    # Создаем приложение
    app = FastAPI(
        title=settings.app_name,
        description="Асинхронный сервис для работы с LLM моделями и провайдерами",
        version=API_VERSION,
        lifespan=lifespan,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Добавляем middleware для trace_id (должен быть первым)
    app.add_middleware(TraceContextMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В production использовать конкретные origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Timing middleware
    @app.middleware("http")
    async def timing_middleware(request: Request, call_next: Any) -> Any:
        """Middleware для измерения времени выполнения запросов.

        Args:
            request: Входящий HTTP запрос.
            call_next: Следующий обработчик в цепочке.

        Returns:
            HTTP ответ с добавленными заголовками.

        """
        start_time = time.time()

        # Получаем trace_id из контекста
        trace_id = get_trace_id()

        # Добавляем в state для доступа в handlers
        request.state.trace_id = trace_id

        try:
            response = await call_next(request)

            # Вычисляем время выполнения
            duration_ms = (time.time() - start_time) * 1000

            # Добавляем headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Duration-Ms"] = str(round(duration_ms, 2))

            # Логируем
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    "trace_id": trace_id,
                    "duration_ms": round(duration_ms, 2),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )

            return response

        except Exception as e:
            logger.error(
                f"Запрос завершился с ошибкой: {e}",
                extra={"trace_id": trace_id},
                exc_info=True,
            )
            raise

    # Настраиваем обработчики исключений
    setup_exception_handlers(app)

    # Подключаем API роутеры
    app.include_router(api_router, prefix=API_PREFIX)

    # Подключаем WebSocket endpoint для мониторинга
    app.add_websocket_route("/ws/monitoring", websocket_endpoint)

    # Корневой endpoint
    @app.get("/")
    async def root() -> dict[str, Any]:
        """Корневой endpoint с информацией о сервисе.

        Returns:
            Словарь с информацией о сервисе и доступных endpoints.

        """
        return {
            "service": settings.app_name,
            "version": API_VERSION,
            "environment": settings.environment,
            "status": "running",
            "endpoints": {
                "api": API_PREFIX,
                "docs": "/docs",
                "redoc": "/redoc",
                "monitoring": "/ws/monitoring",
            },
        }

    # Health check endpoint
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Endpoint для проверки состояния сервиса.

        Returns:
            Словарь со статусом сервиса.

        """
        return {"status": "healthy"}

    return app


def main_uvicorn() -> None:  # pragma: no cover
    """Запуск приложения через Uvicorn (для разработки).

    Использует настройки из конфигурации для запуска dev-сервера
    с автоперезагрузкой и подробным логированием.
    """
    uvicorn.run(
        "src.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.debug,
        log_level=settings.log.level.lower(),
        access_log=True,
    )


# TODO: Раскомментировать когда создадим src/core/gunicorn.py
# def main_gunicorn() -> None:  # pragma: no cover
#     """Запуск приложения через Gunicorn (для production).
#
#     Использует многопроцессную архитектуру Gunicorn для
#     обработки большого количества запросов в production.
#     """
#     from src.core.gunicorn import Application, get_app_options
#
#     Application(
#         application=app,
#         options=get_app_options(
#             host=settings.server.host,
#             port=settings.server.port,
#             timeout=settings.server.timeout,
#             workers=settings.server.workers,
#             log_level=settings.log.level.lower(),
#         ),
#     ).run()


# Создаем экземпляр приложения для импорта
app = create_app()


if __name__ == "__main__":
    main_uvicorn()
