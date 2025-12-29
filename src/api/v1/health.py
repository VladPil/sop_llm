"""SOP LLM - Health Check Endpoints.

Endpoints для проверки здоровья системы и метрик.
"""

import psutil
from fastapi import APIRouter, status
from loguru import logger

from src.api.schemas import HealthResponse, MetricsResponse
from src.core.dependencies import (
    EmbeddingManagerDep,
    HealthCheckerDep,
    JSONFixerDep,
    LLMManagerDep,
    ModelLoaderDep,
    RedisCacheDep,
    SettingsDep,
)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check",
    description="Проверяет здоровье всех компонентов системы",
    status_code=status.HTTP_200_OK,
)
async def health_check(checker: HealthCheckerDep) -> HealthResponse:
    """Выполняет проверку здоровья системы.

    Возвращает статус всех компонентов:
    - Redis
    - Models (LLM и Embedding)
    - System resources (CPU, Memory, Disk)

    Args:
        checker: Health checker instance.

    Returns:
        Статус здоровья системы.

    """
    logger.debug("Health check requested")
    health_status = await checker.get_full_health_status()
    return health_status


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Prometheus метрики",
    description="Возвращает метрики для мониторинга",
    status_code=status.HTTP_200_OK,
)
async def get_metrics(
    llm_manager: LLMManagerDep,
    embedding_manager: EmbeddingManagerDep,
    json_fixer: JSONFixerDep,
    cache: RedisCacheDep,
    model_loader: ModelLoaderDep,
) -> MetricsResponse:
    """Возвращает метрики для Prometheus.

    Включает:
    - Метрики LLM (запросы, активные задачи)
    - Метрики Embedding (количество embeddings)
    - Метрики JSON Fixer (исправления, успешность)
    - Метрики кэша (размер, хиты)
    - Системные метрики (CPU, RAM, GPU VRAM)

    Args:
        llm_manager: LLM manager instance.
        embedding_manager: Embedding manager instance.
        json_fixer: JSON fixer instance.
        cache: Redis cache instance.
        model_loader: Model loader instance.

    Returns:
        Метрики системы.

    """
    logger.debug("Metrics requested")

    # LLM метрики
    llm_stats = llm_manager.get_stats()

    # Embedding метрики
    emb_stats = embedding_manager.get_stats()

    # JSON Fixer метрики
    json_fixer_stats = json_fixer.get_stats()

    # Cache метрики
    cache_stats = await cache.get_stats()

    # Системные метрики
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # GPU метрики
    gpu_info = model_loader.get_gpu_memory_info()

    return MetricsResponse(
        llm=llm_stats,
        embedding=emb_stats,
        json_fixer=json_fixer_stats,
        cache=cache_stats,
        system={
            "cpu_percent": cpu_percent,
            "ram_percent": memory.percent,
            "ram_available_gb": memory.available / (1024**3),
            "ram_total_gb": memory.total / (1024**3),
            "gpu_device": gpu_info.get("device", "N/A"),
            "gpu_memory_allocated_gb": gpu_info.get("allocated_gb", 0),
            "gpu_memory_total_gb": gpu_info.get("total_gb", 0),
            "gpu_memory_free_gb": gpu_info.get("free_gb", 0),
            "gpu_utilization_percent": gpu_info.get("utilization_percent", 0),
        },
    )
