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
    description="Асинхронный executor для LLM моделей с поддержкой multiple providers",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/docs" if settings.debug else None,  # Swagger UI только в debug
    redoc_url="/redoc" if settings.debug else None,
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

# API v1 routes
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(monitor.router, prefix="/api/v1")


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
