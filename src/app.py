"""SOP LLM Executor - FastAPI Application.

Главное приложение с инициализацией всех компонентов.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import settings
from src.api.routes import models, monitor, tasks
from src.providers.registry import get_provider_registry
from src.services.session_store import create_session_store
from src.services.task_processor import create_task_processor, get_task_processor
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager для startup/shutdown.

    Args:
        _app: FastAPI application (не используется, но требуется сигнатурой)

    Yields:
        None

    """
    # =================================================================
    # Startup
    # =================================================================
    logger.info(
        "SOP LLM Executor запускается",
        env=settings.app_env,
        debug=settings.debug,
        log_level=settings.log_level,
    )

    # Создать SessionStore
    session_store = await create_session_store()
    logger.info("SessionStore инициализирован")

    # Создать TaskProcessor
    task_processor = create_task_processor(session_store)
    logger.info("TaskProcessor создан")

    # Запустить TaskProcessor worker
    await task_processor.start()
    logger.info("TaskProcessor worker запущен")

    # Модели регистрируются через API (/api/v1/models/register)

    logger.info(
        "SOP LLM Executor готов",
        server_host=settings.server_host,
        server_port=settings.server_port,
    )

    yield

    # =================================================================
    # Shutdown
    # =================================================================
    logger.info("SOP LLM Executor останавливается")

    # Остановить TaskProcessor worker
    task_processor = get_task_processor()
    await task_processor.stop()
    logger.info("TaskProcessor остановлен")

    # Cleanup всех providers
    registry = get_provider_registry()
    await registry.cleanup_all()
    logger.info("Providers cleanup выполнен")

    # Закрыть Redis connection
    await session_store.redis.close()
    logger.info("Redis connection закрыт")

    logger.info("SOP LLM Executor остановлен")


# =================================================================
# FastAPI Application
# =================================================================

app = FastAPI(
    title=settings.app_name,
    description="""
# SOP LLM Executor API

Высокопроизводительный асинхронный сервис для работы с языковыми моделями.

## Основные возможности

- **Унифицированный интерфейс** для локальных и удаленных моделей
- **Асинхронная обработка** с priority queue
- **Streaming генерация** для real-time вывода
- **Structured Output** через JSON Schema и GBNF грамматики
- **Webhook callbacks** с retry механизмом
- **Idempotency** для дедупликации запросов
- **GPU Management** с VRAM мониторингом

## Поддерживаемые провайдеры

- **Local** - llama.cpp (GGUF модели)
- **OpenAI** - GPT-4, GPT-3.5 и др.
- **Anthropic** - Claude 3 модели
- **OpenAI-Compatible** - любые OpenAI-совместимые API

## Архитектура

Сервис использует паттерн "Dumb Executor" — выполняет только inference,
вся бизнес-логика и промпты передаются в запросах.

Подробная документация: https://github.com/VladPil/sop_llm/tree/main/docs
    """,
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "tasks",
            "description": "Управление задачами генерации текста",
        },
        {
            "name": "models",
            "description": "Управление LLM моделями и провайдерами",
        },
        {
            "name": "monitor",
            "description": "Мониторинг состояния системы, GPU и очереди",
        },
    ],
    contact={
        "name": "Vladislav",
        "email": "vladislav@example.com",
    },
    license_info={
        "name": "MIT",
    },
)

# =================================================================
# Middleware
# =================================================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production настроить конкретные origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
if settings.app_env != "development":
    Instrumentator().instrument(app).expose(app)
    logger.info("Prometheus metrics enabled на /metrics")

# =================================================================
# Routes
# =================================================================

# API routes
app.include_router(tasks.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(monitor.router, prefix="/api")


# =================================================================
# Root Endpoint
# =================================================================

@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Информация о сервисе

    """
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
    }
