"""Models API Routes для SOP LLM Executor.

Endpoints для управления моделями и provider registry.
"""

import contextlib
from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import (
    CheckCompatibilityRequest,
    RegisterFromPresetRequest,
    RegisterModelRequest,
)
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
from src.core import ProviderType
from src.core.dependencies import (
    CompatibilityCheckerDep,
    PresetsLoaderDep,
)
from src.docs import models as docs
from src.providers import litellm_provider, local
from src.providers.registry import get_provider_registry
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/",
    summary="Список зарегистрированных моделей",
    description=docs.LIST_MODELS,
    responses={
        200: {
            "description": "Список моделей успешно получен",
            "content": {
                "application/json": {
                    "example": {
                        "models": [
                            {
                                "name": "gpt-4-turbo",
                                "provider": "openai",
                                "context_window": 128000,
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
    """Получить список зарегистрированных моделей.

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


# Model Presets Endpoints (должны быть ПЕРЕД /{model_name})


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
    """Получить список всех пресетов моделей.

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
                        "name": "gpt-4-turbo",
                        "provider": "openai",
                        "context_window": 128000,
                        "max_output_tokens": 4096,
                        "supports_streaming": True,
                        "supports_structured_output": True,
                        "loaded": True,
                        "extra": {"api_version": "2024-01-01"},
                    }
                }
            },
        },
        404: {"model": ErrorResponse, "description": "Модель с указанным именем не найдена в registry"},
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
    summary="Зарегистрировать модель вручную",
    description=docs.REGISTER_MODEL,
    responses={
        201: {
            "description": "Модель успешно зарегистрирована",
            "content": {
                "application/json": {
                    "example": {
                        "name": "my-custom-model",
                        "provider": "openai",
                        "context_window": 8192,
                        "max_output_tokens": 4096,
                        "supports_streaming": True,
                        "supports_structured_output": True,
                        "loaded": True,
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Невалидная конфигурация или ошибка инициализации"},
        409: {"model": ErrorResponse, "description": "Модель с таким именем уже зарегистрирована"},
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
    summary="Удалить модель из системы",
    description=docs.UNREGISTER_MODEL,
    responses={
        204: {"description": "Модель успешно удалена из системы"},
        404: {"model": ErrorResponse, "description": "Модель не найдена в registry"},
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


@router.post(
    "/register-from-preset",
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать модель из пресета",
    description=docs.REGISTER_FROM_PRESET,
    responses={
        201: {"description": "Модель успешно зарегистрирована из пресета"},
        400: {"model": ErrorResponse, "description": "Ошибка загрузки модели или отсутствует API ключ"},
        404: {"model": ErrorResponse, "description": "Пресет с указанным именем не найден"},
        409: {"model": ErrorResponse, "description": "Модель с таким именем уже зарегистрирована"},
    },
)
async def register_from_preset(
    request: RegisterFromPresetRequest,
    loader: PresetsLoaderDep,
    checker: CompatibilityCheckerDep,
) -> ModelInfo:
    """Зарегистрировать модель из YAML пресета.

    Args:
        request: Параметры регистрации
        loader: ModelPresetsLoader dependency
        checker: CompatibilityChecker dependency

    Returns:
        ModelInfo зарегистрированной модели

    Raises:
        HTTPException: 404 если пресет не найден, 409 если модель уже зарегистрирована

    Note:
        Локальные GGUF модели больше не поддерживаются напрямую.
        Используйте Ollama для локальных моделей (ollama/model_name).

    """
    registry = get_provider_registry()

    # Проверить, не зарегистрирована ли уже
    if request.preset_name in registry:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Модель '{request.preset_name}' уже зарегистрирована",
        )

    # Попробовать найти локальный пресет
    local_preset = loader.get_local_preset(request.preset_name)
    if local_preset:
        # Локальные GGUF модели теперь обслуживаются через Ollama
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Локальные GGUF модели больше не поддерживаются напрямую. "
                f"Используйте Ollama: ollama pull {local_preset.name}, "
                f"затем зарегистрируйте через /register с model_name='ollama/{local_preset.name}'"
            ),
        )

    # Попробовать найти облачный пресет
    cloud_preset = loader.get_cloud_preset(request.preset_name)
    if cloud_preset:
        return await _register_cloud_from_preset(preset=cloud_preset)

    # Пресет не найден
    available_cloud = ", ".join(loader.list_cloud_names()[:10]) or "нет"
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            f"Пресет '{request.preset_name}' не найден. "
            f"Доступные облачные модели: {available_cloud}..."
        ),
    )


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
    """Проверить совместимость модели с GPU.

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


@router.post(
    "/load",
    summary="Загрузить модель в VRAM",
    description=docs.LOAD_MODEL,
    responses={
        200: {
            "description": "Модель успешно загружена",
            "content": {
                "application/json": {
                    "example": {
                        "model_name": "qwen2.5-7b-instruct",
                        "loaded": True,
                        "load_time_ms": 3500,
                        "vram_used_mb": 5500,
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Модель не поддерживает явную загрузку"},
        404: {"model": ErrorResponse, "description": "Модель не найдена"},
    },
)
async def load_model(model_name: str) -> dict:
    """Загрузить модель в VRAM.

    Args:
        model_name: Имя зарегистрированной модели

    Returns:
        Информация о загрузке

    Raises:
        HTTPException: 404 если модель не найдена, 400 если не поддерживает загрузку

    """
    import time

    from src.api.routes.websocket import broadcast_model_loaded

    registry = get_provider_registry()

    try:
        provider = registry.get(model_name)
    except KeyError as e:
        available = ", ".join(registry.list_providers()) or "нет доступных"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Модель '{model_name}' не найдена. Доступные: {available}",
        ) from e

    # Проверить что provider поддерживает load_model
    if not hasattr(provider, "load_model"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Модель '{model_name}' не поддерживает явную загрузку в VRAM (облачная модель?)",
        )

    try:
        start_time = time.time()

        # Загрузить модель
        await provider.load_model()

        load_time_ms = int((time.time() - start_time) * 1000)

        # Получить VRAM usage
        vram_used_mb = 0
        with contextlib.suppress(Exception):
            from src.engine.vram_monitor import get_vram_monitor
            vram_monitor = get_vram_monitor()
            vram_usage = vram_monitor.get_vram_usage()
            vram_used_mb = vram_usage.get("used_mb", 0)

        # Broadcast событие
        with contextlib.suppress(Exception):
            await broadcast_model_loaded(model_name, vram_used_mb)

        logger.info(
            "Модель загружена через API",
            model=model_name,
            load_time_ms=load_time_ms,
            vram_used_mb=vram_used_mb,
        )

        return {
            "model_name": model_name,
            "loaded": True,
            "load_time_ms": load_time_ms,
            "vram_used_mb": vram_used_mb,
        }

    except Exception as e:
        logger.exception("Ошибка загрузки модели", model=model_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки модели: {e}",
        ) from e


@router.post(
    "/unload",
    summary="Выгрузить модель из VRAM",
    description=docs.UNLOAD_MODEL,
    responses={
        200: {
            "description": "Модель успешно выгружена",
            "content": {
                "application/json": {
                    "example": {
                        "model_name": "qwen2.5-7b-instruct",
                        "unloaded": True,
                        "vram_freed_mb": 5500,
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Модель не поддерживает выгрузку"},
        404: {"model": ErrorResponse, "description": "Модель не найдена"},
    },
)
async def unload_model(model_name: str) -> dict:
    """Выгрузить модель из VRAM.

    Args:
        model_name: Имя зарегистрированной модели

    Returns:
        Информация о выгрузке

    Raises:
        HTTPException: 404 если модель не найдена, 400 если не поддерживает выгрузку

    """
    from src.api.routes.websocket import broadcast_model_unloaded

    registry = get_provider_registry()

    try:
        provider = registry.get(model_name)
    except KeyError as e:
        available = ", ".join(registry.list_providers()) or "нет доступных"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Модель '{model_name}' не найдена. Доступные: {available}",
        ) from e

    # Проверить что provider поддерживает unload_model
    if not hasattr(provider, "unload_model"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Модель '{model_name}' не поддерживает выгрузку из VRAM (облачная модель?)",
        )

    try:
        # Получить VRAM до выгрузки
        vram_before = 0
        vram_monitor = None
        with contextlib.suppress(Exception):
            from src.engine.vram_monitor import get_vram_monitor
            vram_monitor = get_vram_monitor()
            vram_usage = vram_monitor.get_vram_usage()
            vram_before = vram_usage.get("used_mb", 0)

        # Выгрузить модель
        await provider.unload_model()

        # Получить VRAM после выгрузки
        vram_after = 0
        if vram_monitor:
            with contextlib.suppress(Exception):
                vram_usage = vram_monitor.get_vram_usage()
                vram_after = vram_usage.get("used_mb", 0)

        vram_freed_mb = max(0, vram_before - vram_after)

        # Broadcast событие
        with contextlib.suppress(Exception):
            await broadcast_model_unloaded(model_name, vram_freed_mb)

        logger.info(
            "Модель выгружена через API",
            model=model_name,
            vram_freed_mb=vram_freed_mb,
        )

        return {
            "model_name": model_name,
            "unloaded": True,
            "vram_freed_mb": vram_freed_mb,
        }

    except Exception as e:
        logger.exception("Ошибка выгрузки модели", model=model_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка выгрузки модели: {e}",
        ) from e


@router.get(
    "/download-status/{preset_name}",
    summary="[DEPRECATED] Проверить статус загрузки модели",
    description="Этот endpoint устарел. Локальные модели теперь обслуживаются через Ollama.",
    responses={
        410: {"model": ErrorResponse, "description": "Функционал удалён"},
    },
    deprecated=True,
)
async def get_download_status(preset_name: str) -> dict:
    """Устаревший endpoint для проверки статуса загрузки.

    Note:
        Локальные GGUF модели теперь обслуживаются через Ollama.
        HuggingFace downloader удалён.

    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Функционал загрузки моделей с HuggingFace удалён. "
            "Используйте Ollama для локальных моделей: ollama pull model_name"
        ),
    )


# Helper Functions for Preset Registration


async def _register_cloud_from_preset(preset: Any) -> ModelInfo:
    """Зарегистрировать облачную модель из пресета.

    Args:
        preset: CloudModelPreset

    Returns:
        ModelInfo зарегистрированной модели

    Raises:
        HTTPException: Если API ключ не найден

    """
    # Получить config для provider
    config = preset.to_register_config()

    # Проверить API ключ
    if not config.get("api_key"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"API ключ не найден. Установите переменную окружения "
                f"'{preset.api_key_env_var}'"
            ),
        )

    # Создать provider
    provider = litellm_provider.LiteLLMProvider(
        model_name=config["model_name"],
        api_key=config["api_key"],
        base_url=config.get("base_url"),
        timeout=config.get("timeout", 600),
        max_retries=config.get("max_retries", 3),
    )

    registry = get_provider_registry()
    registry.register(preset.name, provider)

    info = await provider.get_model_info()

    logger.info(
        "Облачная модель зарегистрирована из пресета",
        model=preset.name,
        provider=preset.provider,
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
    if provider_type == ProviderType.LOCAL:
        return await local.create_local_provider(
            model_name=model_name,
            model_path=config.get("model_path"),
            context_window=config.get("context_window"),
            gpu_layers=config.get("gpu_layers", -1),
        )

    if provider_type in (ProviderType.OPENAI, ProviderType.ANTHROPIC, ProviderType.OPENAI_COMPATIBLE):
        # Все облачные провайдеры используют LiteLLM
        return litellm_provider.LiteLLMProvider(
            model_name=config.get("model_name", model_name),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            timeout=config.get("timeout", 600),
            max_retries=config.get("max_retries", 3),
        )

    msg = f"Неизвестный provider type: {provider_type}"
    raise ValueError(msg)
