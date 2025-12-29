"""Monitor API Routes для SOP LLM Executor.

Endpoints для мониторинга системы, GPU, очереди задач.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.responses import (
    ErrorResponse,
    GPUStatsResponse,
    HealthCheckResponse,
    QueueStatsResponse,
)
from src.engine.gpu_guard import get_gpu_guard
from src.engine.vram_monitor import get_vram_monitor
from src.providers.registry import get_provider_registry
from src.services.task_processor import get_task_processor
from src.utils.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get(
    "/health",
    summary="Health check",
    description="Проверяет доступность всех компонентов системы",
)
async def health_check() -> HealthCheckResponse:
    """Health check всей системы.

    Returns:
        HealthCheckResponse со статусом всех компонентов

    """
    # Проверить Redis
    task_processor = get_task_processor()
    redis_ok = await task_processor.session_store.health_check()

    # Проверить providers
    registry = get_provider_registry()
    providers_health = await registry.health_check_all()

    # Проверить GPU (если есть local providers)
    gpu_info: dict[str, Any] | None = None

    try:
        vram_monitor = get_vram_monitor()
        gpu_data = vram_monitor.get_gpu_info()
        vram_usage = vram_monitor.get_vram_usage()

        gpu_info = {
            "name": gpu_data["name"],
            "vram_used_percent": vram_usage["used_percent"],
            "available": True,
        }

    except Exception as e:
        logger.warning("Не удалось получить GPU info", error=str(e))
        gpu_info = {"available": False}

    # Определить общий статус
    all_healthy = redis_ok and all(providers_health.values())

    if all_healthy:
        overall_status = "healthy"
    elif redis_ok or any(providers_health.values()):
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthCheckResponse(
        status=overall_status,
        redis=redis_ok,
        providers=providers_health,
        gpu=gpu_info,
    )


@router.get(
    "/gpu",
    summary="GPU статистика",
    description="Возвращает детальную статистику GPU (VRAM, temperature, utilization)",
    responses={
        200: {"description": "GPU статистика"},
        503: {"model": ErrorResponse, "description": "GPU недоступен"},
    },
)
async def get_gpu_stats() -> GPUStatsResponse:
    """Получить статистику GPU.

    Returns:
        GPUStatsResponse с метриками GPU

    Raises:
        HTTPException: 503 если GPU недоступен

    """
    try:
        vram_monitor = get_vram_monitor()
        gpu_guard = get_gpu_guard()

        # Получить GPU info
        gpu_info = vram_monitor.get_gpu_info()

        # Получить VRAM usage
        vram_usage = vram_monitor.get_vram_usage()

        # GPU lock статус
        is_locked = gpu_guard.is_locked()
        current_task_id = gpu_guard.get_current_task_id()

        return GPUStatsResponse(
            gpu_info=gpu_info,
            vram_usage=vram_usage,
            is_locked=is_locked,
            current_task_id=current_task_id,
        )

    except Exception as e:
        logger.exception("Ошибка получения GPU stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"GPU недоступен: {e}",
        ) from e


@router.get(
    "/queue",
    summary="Статистика очереди",
    description="Возвращает статистику очереди задач и логов",
)
async def get_queue_stats() -> QueueStatsResponse:
    """Получить статистику очереди задач.

    Returns:
        QueueStatsResponse с метриками очереди

    """
    task_processor = get_task_processor()
    stats = await task_processor.session_store.get_stats()

    return QueueStatsResponse(
        queue_size=stats["queue_size"],
        processing_task=stats["processing_task"],
        recent_logs_count=stats["recent_logs_count"],
    )
