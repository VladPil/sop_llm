"""SOP LLM Executor - FastAPI Application.

Главное приложение с инициализацией всех компонентов.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import litellm
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.routes import conversations, embeddings, models, monitor, tasks, websocket
from src.core.config import settings
from src.engine.vram_monitor import get_vram_monitor
from src.providers.registry import get_provider_registry
from src.services.conversation_store import (
    create_conversation_store,
    set_conversation_store,
)
from src.services.embedding_manager import (
    EmbeddingManager,
    set_embedding_manager,
)
from src.services.model_presets import (
    create_compatibility_checker,
    create_presets_loader,
    set_compatibility_checker,
    set_presets_loader,
)
from src.services.observability import (
    configure_litellm_callbacks,
    flush_observations,
    initialize_langfuse,
    is_observability_enabled,
)
from src.services.session_store import create_session_store, set_session_store
from src.services.task import create_task_orchestrator, get_task_orchestrator
from src.services.task.task_executor import TaskExecutor
from src.services.task.task_state_manager import TaskStateManager
from src.services.task.webhook_service import WebhookService
from src.shared.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager для startup/shutdown.

    Args:
        _app: FastAPI application (не используется, но требуется сигнатурой)

    Yields:
        None

    """
    logger.info(
        "SOP LLM Executor запускается",
        env=settings.app_env,
        debug=settings.debug,
        log_level=settings.log_level,
    )

    # Инициализация Langfuse Observability
    if settings.langfuse_enabled and settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            initialize_langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                enabled=True,
            )
            logger.info("Langfuse observability инициализирован")

            # Настроить LiteLLM callbacks для автоматического трейсинга
            configure_litellm_callbacks()
        except Exception as e:
            logger.warning(f"Не удалось инициализировать Langfuse: {e}")
    else:
        logger.info("Langfuse observability отключен")

    # Настроить LiteLLM
    litellm.drop_params = settings.litellm_drop_params
    litellm.set_verbose = settings.litellm_debug  # type: ignore[attr-defined]
    logger.info(f"LiteLLM настроен: debug={settings.litellm_debug}, drop_params={settings.litellm_drop_params}")

    # Создать SessionStore
    session_store = await create_session_store()
    set_session_store(session_store)
    logger.info("SessionStore инициализирован")

    # Создать ConversationStore (использует тот же Redis client)
    conversation_store = create_conversation_store(session_store.redis)
    set_conversation_store(conversation_store)
    logger.info("ConversationStore инициализирован")

    # Инициализировать Model Presets сервисы
    vram_monitor = None
    presets_loader = None

    try:
        # 1. ModelPresetsLoader - загрузка YAML пресетов
        presets_dir = Path(settings.hf_presets_dir)
        presets_loader = create_presets_loader(presets_dir)
        set_presets_loader(presets_loader)
        logger.info(
            "ModelPresetsLoader инициализирован",
            local=len(presets_loader.list_local()),
            cloud=len(presets_loader.list_cloud()),
            embedding=len(presets_loader.list_embedding()),
        )

        # 2. Связать ProviderRegistry с presets_loader для lazy loading
        registry = get_provider_registry()
        registry.set_presets_loader(presets_loader)
        logger.info("ProviderRegistry связан с presets_loader (lazy loading enabled)")

        # 3. VRAMMonitor и CompatibilityChecker
        try:
            vram_monitor = get_vram_monitor()
            compatibility_checker = create_compatibility_checker(vram_monitor)
            set_compatibility_checker(compatibility_checker)
            logger.info("CompatibilityChecker инициализирован")
        except Exception as e:
            logger.warning(f"VRAMMonitor недоступен (нет GPU?): {e}")

        # 4. EmbeddingManager с lazy loading и FIFO eviction
        embedding_device = "cuda" if vram_monitor else "cpu"
        embedding_manager = EmbeddingManager(
            presets_loader=presets_loader,
            device=embedding_device,
            max_loaded_models=5,
        )
        if vram_monitor:
            embedding_manager.set_vram_monitor(vram_monitor)
        set_embedding_manager(embedding_manager)
        logger.info(f"EmbeddingManager инициализирован (device={embedding_device})")

    except FileNotFoundError as e:
        logger.warning(f"Model presets не загружены: {e}")
    except Exception as e:
        logger.warning(f"Ошибка инициализации model presets: {e}")

    # Создать компоненты TaskOrchestrator
    provider_registry = get_provider_registry()
    executor = TaskExecutor(provider_registry)
    webhook_service = WebhookService()
    state_manager = TaskStateManager(session_store)

    # Создать TaskOrchestrator
    orchestrator = create_task_orchestrator(
        executor=executor,
        webhook_service=webhook_service,
        state_manager=state_manager,
        session_store=session_store,
    )
    logger.info("TaskOrchestrator создан")

    # Запустить TaskOrchestrator worker
    await orchestrator.start()
    logger.info("TaskOrchestrator worker запущен")

    # С lazy loading модели создаются автоматически при первом запросе.
    # Доступные модели определяются пресетами в config/model_presets/

    logger.info(
        "SOP LLM Executor готов",
        server_host=settings.server_host,
        server_port=settings.server_port,
    )

    yield

    logger.info("SOP LLM Executor останавливается")

    # Остановить WebSocket broadcaster
    from src.api.routes.websocket import stop_broadcaster
    await stop_broadcaster()
    logger.info("WebSocket broadcaster остановлен")

    # Остановить TaskOrchestrator worker
    orchestrator = get_task_orchestrator()
    await orchestrator.stop()
    logger.info("TaskOrchestrator остановлен")

    # Cleanup всех providers
    registry = get_provider_registry()
    await registry.cleanup_all()
    logger.info("Providers cleanup выполнен")

    # Закрыть соединение с Redis
    await session_store.redis.close()
    logger.info("Redis connection закрыт")

    # Flush Langfuse observations
    flush_observations()

    logger.info("SOP LLM Executor остановлен")


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
- **LiteLLM** - 100+ LLM провайдеров (Anthropic, OpenAI, Google Gemini, Mistral, Cohere, и др.)

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
            "name": "conversations",
            "description": "Управление multi-turn диалогами (контекстом)",
        },
        {
            "name": "models",
            "description": "Управление LLM моделями и провайдерами",
        },
        {
            "name": "monitor",
            "description": "Мониторинг состояния системы, GPU и очереди",
        },
        {
            "name": "embeddings",
            "description": "Генерация векторных представлений (embeddings) для текстов",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# API v1 endpoints (для совместимости с SOP Intake)
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(monitor.router, prefix="/api/v1")
app.include_router(embeddings.router, prefix="/api/v1")

# WebSocket endpoint (без версии, как в ТЗ)
app.include_router(websocket.router)

# Legacy endpoints без версии (обратная совместимость, не показываются в Swagger)
app.include_router(tasks.router, prefix="/api", include_in_schema=False)
app.include_router(conversations.router, prefix="/api", include_in_schema=False)
app.include_router(models.router, prefix="/api", include_in_schema=False)
app.include_router(monitor.router, prefix="/api", include_in_schema=False)
app.include_router(embeddings.router, prefix="/api", include_in_schema=False)


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


@app.get("/health", tags=["root"])
async def health() -> dict[str, str]:
    """Health check endpoint для Docker и мониторинга.

    Простой health check который всегда возвращает OK.
    Для детального health check используйте /api/v1/monitor/health

    Returns:
        Статус сервиса

    """
    return {
        "status": "ok",
        "service": "sop_llm",
        "version": "1.0.0",
    }


@app.get("/observability", tags=["root"])
async def observability_info() -> dict[str, str | bool]:
    """Информация об observability (Langfuse).

    Returns:
        Информация о конфигурации observability

    """
    return {
        "enabled": is_observability_enabled(),
        "platform": "langfuse" if is_observability_enabled() else "disabled",
        "host": settings.langfuse_host if settings.langfuse_enabled else "",
    }
