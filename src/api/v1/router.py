"""SOP LLM - API v1 Router.

Главный роутер для API версии 1.
"""

from fastapi import APIRouter

from src.api.v1 import health, models, similarity, tasks
from src.core.constants import API_VERSION
from src.core.dependencies import SettingsDep

# Создаем главный роутер для v1
router = APIRouter()

# Подключаем все sub-routers
router.include_router(health.router)
router.include_router(tasks.router)
router.include_router(models.router)
router.include_router(similarity.router)


@router.get(
    "",
    summary="Root endpoint v1",
    description="Возвращает информацию о API v1",
)
async def root(settings: SettingsDep) -> dict:
    """Информация о API v1.

    Args:
        settings: Settings instance.

    Returns:
        Информация о сервисе.

    """
    return {
        "service": settings.app_name,
        "version": API_VERSION,
        "api_version": "v1",
        "status": "running",
        "endpoints": {
            "tasks": "/api/v1/tasks",
            "health": "/api/v1/health",
            "metrics": "/api/v1/health/metrics",
            "models": "/api/v1/models",
            "providers": "/api/v1/models/providers",
            "similarity": "/api/v1/similarity",
            "docs": "/docs",
        },
    }
