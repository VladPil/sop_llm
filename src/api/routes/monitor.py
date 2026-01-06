"""Monitor API Routes для SOP LLM Executor.

Endpoints для мониторинга системы, GPU, очереди задач.
"""

import asyncio
import shutil
import time
from datetime import UTC, datetime
from typing import Any

import psutil
from fastapi import APIRouter, HTTPException, Response, status

from src.api.schemas.responses import (
    ComponentHealth,
    ErrorResponse,
    GPUStatsResponse,
    HealthCheckResponse,
    QueueStatsResponse,
    SystemResources,
)
from src.core import HealthStatus, settings
from src.engine.gpu_guard import get_gpu_guard
from src.engine.vram_monitor import get_vram_monitor
from src.providers.registry import get_provider_registry
from src.services.session_store import get_session_store
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/monitor", tags=["monitor"])

# Глобальный uptime tracker
_app_start_time = time.time()


async def _check_component_health(
    name: str,
    check_func: callable,
    timeout: float = 5.0,
) -> ComponentHealth:
    """Проверить здоровье компонента с таймаутом.

    Args:
        name: Название компонента
        check_func: Async функция для проверки
        timeout: Таймаут в секундах

    Returns:
        ComponentHealth со статусом компонента

    """
    start_time = time.time()

    try:
        # Запустить проверку с таймаутом
        result = await asyncio.wait_for(check_func(), timeout=timeout)
        response_time = (time.time() - start_time) * 1000

        if result:
            return ComponentHealth(
                status="up",
                message=f"{name} доступен",
                response_time_ms=round(response_time, 2),
            )

        return ComponentHealth(
            status="down",
            message=f"{name} недоступен",
            response_time_ms=round(response_time, 2),
        )

    except TimeoutError:
        return ComponentHealth(
            status="down",
            message=f"{name} превышен таймаут {timeout}s",
            response_time_ms=timeout * 1000,
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ComponentHealth(
            status="down",
            message=f"{name} ошибка: {e!s}",
            response_time_ms=round(response_time, 2),
        )


def _get_system_resources() -> SystemResources:
    """Получить информацию о системных ресурсах.

    Returns:
        SystemResources с метриками системы

    """
    # Disk usage
    disk = shutil.disk_usage("/")
    disk_usage_percent = (disk.used / disk.total) * 100
    disk_free_gb = disk.free / (1024**3)

    # Memory usage
    memory = psutil.virtual_memory()
    memory_usage_percent = memory.percent
    memory_available_gb = memory.available / (1024**3)

    return SystemResources(
        disk_usage_percent=round(disk_usage_percent, 2),
        disk_free_gb=round(disk_free_gb, 2),
        memory_usage_percent=round(memory_usage_percent, 2),
        memory_available_gb=round(memory_available_gb, 2),
    )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Комплексная проверка состояния системы",
    description="""
Выполняет полную проверку всех компонентов системы и возвращает детальный статус.

## Что проверяется

### Критические компоненты
- **Redis** — хранилище сессий и очередь задач

### Провайдеры моделей
- Все зарегистрированные LLM провайдеры
- Статус каждого провайдера отдельно

### Системные ресурсы
- Использование диска (%)
- Свободное место на диске (GB)
- Использование RAM (%)
- Доступная RAM (GB)

### GPU (если доступен)
- Название GPU
- Использование VRAM (%)

## Статусы ответа

| Статус | HTTP код | Описание |
|--------|----------|----------|
| `healthy` | 200 | Все компоненты работают |
| `degraded` | 503 | Некоторые компоненты недоступны |
| `unhealthy` | 503 | Критические компоненты недоступны |

## Использование

Подходит для:
- **Kubernetes** — livenessProbe и readinessProbe
- **Docker Compose** — healthcheck
- **Load Balancer** — проверка доступности backend

## Примечание

Для простого health check без деталей используйте `/health` (root endpoint).
""",
    responses={
        200: {
            "description": "Система работает нормально",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                        "uptime_seconds": 3600.5,
                        "timestamp": "2024-01-15T10:30:00Z",
                        "components": {
                            "redis": {"status": "up", "message": "Redis доступен", "response_time_ms": 1.5},
                            "provider_gpt-4-turbo": {"status": "up", "message": "Provider gpt-4-turbo доступен"},
                        },
                        "resources": {
                            "disk_usage_percent": 45.2,
                            "disk_free_gb": 120.5,
                            "memory_usage_percent": 62.3,
                            "memory_available_gb": 8.5,
                        },
                        "gpu": {"name": "NVIDIA RTX 4090", "vram_used_percent": 35.0, "available": True},
                    }
                }
            },
        },
        503: {"description": "Есть проблемы с одним или несколькими компонентами"},
    },
)
async def health_check(response: Response) -> HealthCheckResponse:
    """Health check всей системы.

    Проверяет:
    - Redis доступность
    - Providers (если зарегистрированы)
    - Системные ресурсы (disk, memory)
    - GPU (если доступен)

    Returns:
        HealthCheckResponse со статусом всех компонентов

    HTTP Status Codes:
        - 200: Все компоненты healthy
        - 503: Есть degraded или unhealthy компоненты

    """
    components: dict[str, ComponentHealth] = {}

    # Проверить Redis
    session_store = get_session_store()
    components["redis"] = await _check_component_health(
        "Redis",
        session_store.health_check,
        timeout=3.0,
    )

    # Проверить providers (если есть)
    try:
        registry = get_provider_registry()
        providers_health = await registry.health_check_all()

        # Добавить каждый provider как отдельный компонент
        for model_name, is_healthy in providers_health.items():
            components[f"provider_{model_name}"] = ComponentHealth(
                status="up" if is_healthy else "down",
                message=f"Provider {model_name} {'доступен' if is_healthy else 'недоступен'}",
            )

    except Exception as e:
        logger.warning("Не удалось проверить providers", error=str(e))
        components["providers"] = ComponentHealth(
            status="down",
            message=f"Ошибка проверки providers: {e}",
        )

    # Получить системные ресурсы
    resources = _get_system_resources()

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

        components["gpu"] = ComponentHealth(
            status="up",
            message=f"GPU {gpu_data['name']} доступен",
        )

    except Exception as e:
        logger.debug("GPU недоступен (это нормально без GPU)", error=str(e))
        gpu_info = {"available": False}

    # Определить общий статус
    statuses = [comp.status for comp in components.values()]
    critical_components = ["redis"]  # Redis критичен для работы

    # Проверить критичные компоненты
    critical_down = any(
        components.get(comp, ComponentHealth(status="down")).status == "down"
        for comp in critical_components
    )

    if critical_down or all(s == "down" for s in statuses):
        overall_status = HealthStatus.UNHEALTHY
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(s == "down" for s in statuses):
        overall_status = HealthStatus.DEGRADED
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        overall_status = HealthStatus.HEALTHY
        response.status_code = status.HTTP_200_OK

    # Uptime
    uptime_seconds = time.time() - _app_start_time

    # Timestamp
    timestamp = datetime.now(UTC).isoformat()

    return HealthCheckResponse(
        status=overall_status,
        version=settings.app_version,
        uptime_seconds=round(uptime_seconds, 2),
        timestamp=timestamp,
        components=components,
        resources=resources,
        gpu=gpu_info,
    )


@router.get(
    "/gpu",
    response_model=GPUStatsResponse,
    summary="Детальная статистика GPU",
    description="""
Возвращает полную информацию о GPU и использовании видеопамяти (VRAM).

## Что возвращает

### GPU Info
- **name** — название GPU (например, "NVIDIA RTX 4090")
- **driver_version** — версия драйвера NVIDIA
- **cuda_version** — версия CUDA
- **compute_capability** — вычислительные возможности GPU

### VRAM Usage
- **total_mb** — общий объём VRAM в MB
- **used_mb** — использовано VRAM в MB
- **free_mb** — свободно VRAM в MB
- **used_percent** — процент использования VRAM

### Lock Status
- **is_locked** — занят ли GPU задачей генерации
- **current_task_id** — ID текущей задачи (если GPU занят)

## Использование

- Проверка доступной VRAM перед загрузкой модели
- Мониторинг занятости GPU текущими задачами
- Отслеживание использования ресурсов в Grafana/Prometheus

## Ошибки

- **503 Service Unavailable** — GPU недоступен (нет NVIDIA GPU или драйверов)
""",
    responses={
        200: {
            "description": "Статистика GPU успешно получена",
            "content": {
                "application/json": {
                    "example": {
                        "gpu_info": {
                            "name": "NVIDIA RTX 4090",
                            "driver_version": "535.104.05",
                            "cuda_version": "12.2",
                        },
                        "vram_usage": {
                            "total_mb": 24576,
                            "used_mb": 8500,
                            "free_mb": 16076,
                            "used_percent": 34.6,
                        },
                        "is_locked": False,
                        "current_task_id": None,
                    }
                }
            },
        },
        503: {"model": ErrorResponse, "description": "GPU недоступен (нет NVIDIA GPU или драйверов)"},
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
    response_model=QueueStatsResponse,
    summary="Статистика очереди задач",
    description="""
Возвращает информацию о текущем состоянии очереди задач генерации.

## Что возвращает

### Метрики очереди
- **queue_size** — количество задач в очереди ожидания
- **processing_task** — ID задачи, которая сейчас выполняется (или null)
- **recent_logs_count** — количество записей в логах за последний период

## Использование

- Мониторинг нагрузки на сервис
- Балансировка запросов между серверами
- Алертинг при переполнении очереди

## Интерпретация значений

| queue_size | Статус | Рекомендация |
|------------|--------|--------------|
| 0 | Idle | Система простаивает |
| 1-10 | Normal | Нормальная нагрузка |
| 11-50 | Busy | Повышенная нагрузка |
| 50+ | Overloaded | Рассмотреть масштабирование |

## Связь с другими endpoints

- `/monitor/health` — общий статус системы
- `/monitor/gpu` — детали о GPU и VRAM
- `/tasks/{task_id}` — статус конкретной задачи
""",
    responses={
        200: {
            "description": "Статистика очереди успешно получена",
            "content": {
                "application/json": {
                    "example": {
                        "queue_size": 5,
                        "processing_task": "task_abc123",
                        "recent_logs_count": 100,
                    }
                }
            },
        }
    },
)
async def get_queue_stats() -> QueueStatsResponse:
    """Получить статистику очереди задач.

    Returns:
        QueueStatsResponse с метриками очереди

    """
    session_store = get_session_store()
    stats = await session_store.get_stats()

    return QueueStatsResponse(
        queue_size=stats["queue_size"],
        processing_task=stats["processing_task"],
        recent_logs_count=stats["recent_logs_count"],
    )
