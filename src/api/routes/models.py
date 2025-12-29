"""Models API Routes для SOP LLM Executor.

Endpoints для управления моделями и provider registry.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import RegisterModelRequest
from src.api.schemas.responses import ErrorResponse, ModelInfo, ModelsListResponse
from src.providers import anthropic, local, openai, openai_compatible
from src.providers.registry import get_provider_registry
from src.utils.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/",
    summary="Список моделей",
    description="Возвращает список всех зарегистрированных моделей",
)
async def list_models() -> ModelsListResponse:
    """Получить список зарегистрированных моделей.

    Returns:
        ModelsListResponse со списком моделей и их метаданными

    """
    registry = get_provider_registry()

    # Получить метаданные всех моделей
    models_info = await registry.get_all_models_info()

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
    "/{model_name}",
    summary="Информация о модели",
    description="Возвращает детальную информацию о конкретной модели",
    responses={
        200: {"description": "Информация о модели"},
        404: {"model": ErrorResponse, "description": "Модель не найдена"},
    },
)
async def get_model_info(model_name: str) -> ModelInfo:
    """Получить информацию о модели.

    Args:
        model_name: Название модели

    Returns:
        ModelInfo с метаданными

    Raises:
        HTTPException: 404 если модель не найдена

    """
    registry = get_provider_registry()

    try:
        provider = registry.get(model_name)
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
        available = ", ".join(registry.list_providers()) or "нет доступных"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Модель '{model_name}' не найдена. Доступные: {available}",
        ) from e


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать модель",
    description="Динамически регистрирует новую модель в provider registry",
    responses={
        201: {"description": "Модель зарегистрирована"},
        400: {"model": ErrorResponse, "description": "Невалидная конфигурация"},
        409: {"model": ErrorResponse, "description": "Модель уже зарегистрирована"},
    },
)
async def register_model(request: RegisterModelRequest) -> ModelInfo:
    """Зарегистрировать новую модель.

    Args:
        request: Параметры регистрации

    Returns:
        ModelInfo зарегистрированной модели

    Raises:
        HTTPException: 400 если конфигурация невалидна, 409 если уже зарегистрирована

    """
    registry = get_provider_registry()

    # Проверить, не зарегистрирована ли уже
    if request.name in registry:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Модель '{request.name}' уже зарегистрирована",
        )

    try:
        # Создать provider в зависимости от типа
        provider = await _create_provider(request.provider, request.name, request.config)

        # Зарегистрировать
        registry.register(request.name, provider)

        # Получить info
        info = await provider.get_model_info()

        logger.info(
            "Модель зарегистрирована через API",
            model=request.name,
            provider=request.provider,
        )

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

    except Exception as e:
        logger.exception(
            "Ошибка регистрации модели",
            model=request.name,
            provider=request.provider,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка регистрации модели: {e}",
        ) from e


@router.delete(
    "/{model_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить модель",
    description="Удаляет модель из registry и опционально очищает ресурсы",
    responses={
        204: {"description": "Модель удалена"},
        404: {"model": ErrorResponse, "description": "Модель не найдена"},
    },
)
async def unregister_model(
    model_name: str,
    cleanup: bool = True,
) -> None:
    """Удалить модель из registry.

    Args:
        model_name: Название модели
        cleanup: Очистить ресурсы (unload model, close connections)

    Raises:
        HTTPException: 404 если модель не найдена

    """
    registry = get_provider_registry()

    try:
        provider = registry.get(model_name)

        # Cleanup (если запрошено)
        if cleanup:
            await provider.cleanup()

        # Удалить из registry
        registry.unregister(model_name)

        logger.info(
            "Модель удалена из registry через API",
            model=model_name,
            cleanup=cleanup,
        )

    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Модель '{model_name}' не найдена",
        ) from e


# =================================================================
# Вспомогательные функции
# =================================================================

async def _create_provider(
    provider_type: str,
    model_name: str,
    config: dict[str, Any],
) -> Any:
    """Создать provider instance.

    Args:
        provider_type: Тип провайдера
        model_name: Название модели
        config: Конфигурация provider

    Returns:
        Provider instance

    Raises:
        ValueError: Если provider_type неизвестен

    """
    if provider_type == "local":
        return await local.create_local_provider(
            model_name=model_name,
            model_path=config.get("model_path"),
            context_window=config.get("context_window"),
            gpu_layers=config.get("gpu_layers", -1),
        )

    if provider_type == "openai_compatible":
        return await openai_compatible.create_openai_compatible_provider(
            model_name=config.get("model_name", model_name),
            base_url=config.get("base_url"),
            api_key=config.get("api_key"),
            context_window=config.get("context_window"),
            max_output_tokens=config.get("max_output_tokens"),
        )

    if provider_type == "anthropic":
        return await anthropic.create_anthropic_provider(
            model_name=config.get("model_name", model_name),
            api_key=config.get("api_key"),
            context_window=config.get("context_window", 200000),
            max_output_tokens=config.get("max_output_tokens", 4096),
        )

    if provider_type == "openai":
        return await openai.create_openai_provider(
            model_name=config.get("model_name", model_name),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            context_window=config.get("context_window"),
            max_output_tokens=config.get("max_output_tokens"),
        )

    msg = f"Неизвестный provider type: {provider_type}"
    raise ValueError(msg)
