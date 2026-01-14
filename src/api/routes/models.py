"""Models API Routes для SOP LLM Executor.

Endpoints для просмотра моделей и пресетов.
С lazy loading модели автоматически создаются при первом запросе.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import CheckCompatibilityRequest
from src.api.schemas.responses import (
    CloudPresetInfo,
    CompatibilityResponse,
    EmbeddingPresetInfo,
    ErrorResponse,
    LocalPresetInfo,
    ModelInfo,
    ModelsListResponse,
    PresetsListResponse,
)
from src.core.dependencies import (
    CompatibilityCheckerDep,
    PresetsLoaderDep,
)
from src.docs import models as docs
from src.providers.registry import get_provider_registry
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/",
    summary="Список активных моделей",
    description=docs.LIST_MODELS,
    responses={
        200: {
            "description": "Список активных моделей",
            "content": {
                "application/json": {
                    "example": {
                        "models": [
                            {
                                "name": "claude-sonnet-4",
                                "provider": "litellm",
                                "context_window": 200000,
                                "max_output_tokens": 4096,
                                "supports_streaming": True,
                                "supports_structured_output": True,
                                "loaded": True,
                            }
                        ],
                        "total": 1,
                    }
                }
            },
        }
    },
)
async def list_models() -> ModelsListResponse:
    """Получить список активных (созданных) моделей.

    С lazy loading модели создаются автоматически при первом запросе.
    Этот endpoint показывает только уже активированные модели.

    Для просмотра всех доступных пресетов используйте GET /models/presets.

    Returns:
        ModelsListResponse со списком моделей и их метаданными

    """
    models_info = await get_provider_registry().get_all_models_info()
    models_list = [
        ModelInfo(
            name=info.name,
            provider=info.provider,
            context_window=info.context_window,
            max_output_tokens=info.max_output_tokens,
            supports_streaming=info.supports_streaming,
            supports_structured_output=info.supports_structured_output,
            loaded=info.loaded,
            extra=info.extra,
        )
        for info in models_info.values()
    ]

    return ModelsListResponse(
        models=models_list,
        total=len(models_list),
    )


@router.get(
    "/presets",
    summary="Список доступных пресетов моделей",
    description=docs.LIST_PRESETS,
    responses={
        200: {"description": "Список пресетов успешно получен"},
    },
)
async def list_presets(
    loader: PresetsLoaderDep,
) -> PresetsListResponse:
    """Получить список всех доступных пресетов моделей.

    Пресеты автоматически активируются при первом запросе к модели.
    Не требуется ручная регистрация.

    Args:
        loader: ModelPresetsLoader dependency

    Returns:
        PresetsListResponse со списками локальных, облачных и embedding пресетов

    """
    local_presets = loader.list_local()
    cloud_presets = loader.list_cloud()
    embedding_presets = loader.list_embedding()

    return PresetsListResponse(
        local_models=[
            LocalPresetInfo(
                name=p.name,
                huggingface_repo=p.huggingface_repo,
                filename=p.filename,
                size_b=p.size_b,
                context_window=p.provider_config.context_window,
                vram_requirements=p.vram_requirements,
            )
            for p in local_presets
        ],
        cloud_models=[
            CloudPresetInfo(
                name=p.name,
                provider=p.provider,
                model_name=p.provider_config.model_name,
                api_key_env_var=p.api_key_env_var,
            )
            for p in cloud_presets
        ],
        embedding_models=[
            EmbeddingPresetInfo(
                name=p.name,
                huggingface_repo=p.huggingface_repo,
                dimensions=p.dimensions,
            )
            for p in embedding_presets
        ],
        total_local=len(local_presets),
        total_cloud=len(cloud_presets),
        total_embedding=len(embedding_presets),
    )


@router.get(
    "/{model_name}",
    summary="Детальная информация о модели",
    description=docs.GET_MODEL_INFO,
    responses={
        200: {
            "description": "Информация о модели успешно получена",
            "content": {
                "application/json": {
                    "example": {
                        "name": "claude-sonnet-4",
                        "provider": "litellm",
                        "context_window": 200000,
                        "max_output_tokens": 4096,
                        "supports_streaming": True,
                        "supports_structured_output": True,
                        "loaded": True,
                        "extra": {"timeout": 600},
                    }
                }
            },
        },
        404: {"model": ErrorResponse, "description": "Модель не найдена в пресетах"},
    },
)
async def get_model_info(model_name: str) -> ModelInfo:
    """Получить информацию о модели.

    Модель автоматически активируется (lazy loading) если ещё не была создана.

    Args:
        model_name: Название модели (должно совпадать с именем пресета)

    Returns:
        ModelInfo с метаданными

    Raises:
        HTTPException: 404 если модель не найдена в пресетах

    """
    registry = get_provider_registry()

    try:
        # Lazy loading: получить или создать провайдер
        provider = registry.get_or_create(model_name)
        info = await provider.get_model_info()

        return ModelInfo(
            name=info.name,
            provider=info.provider,
            context_window=info.context_window,
            max_output_tokens=info.max_output_tokens,
            supports_streaming=info.supports_streaming,
            supports_structured_output=info.supports_structured_output,
            loaded=info.loaded,
            extra=info.extra,
        )

    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.delete(
    "/{model_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить модель из активных",
    description=docs.UNREGISTER_MODEL,
    responses={
        204: {"description": "Модель успешно удалена из активных"},
        404: {"model": ErrorResponse, "description": "Модель не найдена в активных"},
    },
)
async def unregister_model(
    model_name: str,
    cleanup: bool = True,
) -> None:
    """Удалить модель из активных (освободить ресурсы).

    Модель может быть повторно активирована при следующем запросе.

    Args:
        model_name: Название модели
        cleanup: Очистить ресурсы (освободить память)

    Raises:
        HTTPException: 404 если модель не активирована

    """
    registry = get_provider_registry()

    try:
        provider = registry.get(model_name)

        if cleanup:
            await provider.cleanup()

        registry.unregister(model_name)

        logger.info(
            "Модель удалена из активных",
            model=model_name,
            cleanup=cleanup,
        )

    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Модель '{model_name}' не активирована",
        ) from e


@router.post(
    "/check-compatibility",
    summary="Проверить совместимость модели с GPU",
    description=docs.CHECK_COMPATIBILITY,
    responses={
        200: {"description": "Результат проверки совместимости с GPU"},
        404: {"model": ErrorResponse, "description": "Локальный пресет не найден"},
    },
)
async def check_compatibility(
    request: CheckCompatibilityRequest,
    loader: PresetsLoaderDep,
    checker: CompatibilityCheckerDep,
) -> CompatibilityResponse:
    """Проверить совместимость локальной модели с GPU.

    Args:
        request: Параметры проверки
        loader: ModelPresetsLoader dependency
        checker: CompatibilityChecker dependency

    Returns:
        CompatibilityResponse с результатом проверки

    Raises:
        HTTPException: 404 если пресет не найден

    """
    preset = loader.get_local_preset(request.preset_name)
    if not preset:
        available = ", ".join(loader.list_local_names()[:10]) or "нет"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Локальный пресет '{request.preset_name}' не найден. "
                f"Доступные: {available}"
            ),
        )

    result = checker.check_compatibility(preset, request.quantization)

    return CompatibilityResponse(
        compatible=result.compatible,
        required_vram_mb=result.required_vram_mb,
        available_vram_mb=result.available_vram_mb,
        recommended_quantization=result.recommended_quantization,
        warning=result.warning,
    )
