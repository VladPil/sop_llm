"""Models API Routes для SOP LLM Executor.

Endpoints для управления моделями и provider registry.
"""

from pathlib import Path
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
    DownloadStatusResponse,
    EmbeddingPresetInfo,
    ErrorResponse,
    LocalPresetInfo,
    ModelInfo,
    ModelsListResponse,
    PresetsListResponse,
)
from src.core import ProviderType
from src.core.config import settings
from src.core.dependencies import (
    CompatibilityCheckerDep,
    ModelDownloaderDep,
    PresetsLoaderDep,
)
from src.providers import litellm_provider, local
from src.providers.registry import get_provider_registry
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/",
    response_model=ModelsListResponse,
    summary="Список зарегистрированных моделей",
    description="""
Возвращает полный список всех моделей, зарегистрированных в системе.

## Что возвращает

Для каждой модели возвращается:
- **name** — уникальное имя модели в системе (используется в запросах генерации)
- **provider** — тип провайдера (`openai`, `anthropic`, `local`, `openai_compatible`)
- **context_window** — максимальный размер контекста в токенах
- **max_output_tokens** — максимальное количество токенов в ответе
- **supports_streaming** — поддерживает ли модель потоковую генерацию
- **supports_structured_output** — поддерживает ли JSON Schema / GBNF грамматики
- **loaded** — загружена ли модель в память (для локальных моделей)

## Типы провайдеров

| Провайдер | Описание |
|-----------|----------|
| `openai` | OpenAI API (GPT-4, GPT-3.5) |
| `anthropic` | Anthropic API (Claude) |
| `local` | Локальные GGUF модели через llama.cpp |
| `openai_compatible` | Любой OpenAI-совместимый API (Ollama, vLLM) |

## Примечания

- Модели регистрируются при старте приложения или через API `/models/register`
- Для добавления новых моделей используйте `/models/register` или `/models/register-from-preset`
""",
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
        for info in await get_provider_registry().get_all_models_info()
    ]

    return ModelsListResponse(
        models=models_list,
        total=len(models_list),
    )


# === Model Presets Endpoints (должны быть ПЕРЕД /{model_name}) ===


@router.get(
    "/presets",
    response_model=PresetsListResponse,
    summary="Список доступных пресетов моделей",
    description="""
Возвращает список всех предустановленных конфигураций моделей из YAML файлов.

## Что такое пресеты

Пресеты — это готовые конфигурации моделей, которые можно быстро зарегистрировать
через `/models/register-from-preset` без ручного указания всех параметров.

## Типы пресетов

### Локальные модели (local_models)
GGUF модели для запуска на GPU через llama.cpp:
- Qwen 2.5 (3B, 7B, 14B, Coder)
- LLaMA 3.2 (3B, 8B)
- Mistral 7B, Phi-3, Gemma 2

Содержат информацию о:
- HuggingFace репозитории для автозагрузки
- Требованиях VRAM для разных квантизаций
- Размере контекстного окна

### Облачные модели (cloud_models)
API провайдеры (требуют API ключи):
- Claude 3.5 Sonnet/Haiku, Claude 3 Opus
- GPT-4 Turbo, GPT-4o, GPT-4o-mini
- Gemini Pro, Mistral Large
- Groq, Together AI, DeepSeek

### Embedding модели (embedding_models)
Модели для векторизации текста:
- E5 (multilingual-large, base, small)
- Sentence Transformers
- BGE, Cohere, Jina

## Следующие шаги

После получения списка пресетов:
1. Выберите нужный пресет
2. Проверьте совместимость с GPU: `POST /models/check-compatibility`
3. Зарегистрируйте: `POST /models/register-from-preset`
""",
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
    response_model=ModelInfo,
    summary="Детальная информация о модели",
    description="""
Возвращает подробную информацию о конкретной зарегистрированной модели.

## Параметры

- **model_name** (path) — уникальное имя модели в системе

## Что возвращает

- **name** — имя модели
- **provider** — тип провайдера
- **context_window** — размер контекстного окна (в токенах)
- **max_output_tokens** — максимум токенов в ответе
- **supports_streaming** — поддержка потоковой генерации
- **supports_structured_output** — поддержка JSON Schema / GBNF
- **loaded** — статус загрузки (для локальных моделей)
- **extra** — дополнительные метаданные (VRAM usage, версия API и т.д.)

## Ошибки

- **404 Not Found** — модель с указанным именем не зарегистрирована
""",
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
    response_model=ModelInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать модель вручную",
    description="""
Динамически регистрирует новую модель в системе с полной конфигурацией.

## Когда использовать

Используйте этот endpoint, когда нужно:
- Подключить модель с нестандартными параметрами
- Зарегистрировать модель, отсутствующую в пресетах
- Подключить кастомный OpenAI-совместимый API

**Для стандартных моделей рекомендуется использовать** `/models/register-from-preset`

## Типы провайдеров и конфигурация

| Провайдер | Обязательные поля в config |
|-----------|---------------------------|
| `openai` | `api_key`, `model_name` |
| `anthropic` | `api_key`, `model_name` |
| `local` | `model_path`, `context_window` |
| `openai_compatible` | `model_name`, `base_url`, `api_key` |

### Дополнительные поля config

| Поле | Тип | Описание |
|------|-----|----------|
| `timeout` | int | Таймаут запроса в секундах (default: 120) |
| `max_retries` | int | Количество повторов при ошибке (default: 3) |
| `gpu_layers` | int | Слои на GPU для local (-1 = все) |

## Ошибки

- **400 Bad Request** — невалидная конфигурация или ошибка инициализации провайдера
- **409 Conflict** — модель с таким именем уже зарегистрирована
""",
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
    description="""
Удаляет зарегистрированную модель из системы.

## Что происходит при удалении

1. Модель удаляется из registry и становится недоступной для генерации
2. Если `cleanup=true` (по умолчанию):
   - Для локальных моделей: выгружается из GPU/RAM
   - Для облачных: закрываются HTTP соединения

## Параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `model_name` | path | Имя модели для удаления |
| `cleanup` | query | Выполнить очистку ресурсов (default: true) |

## Важно

- Файлы моделей НЕ удаляются с диска
- Нельзя удалить модель во время выполнения задачи
- После удаления модель можно зарегистрировать заново

## Ошибки

- **404 Not Found** — модель не найдена в registry
""",
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
    response_model=ModelInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать модель из пресета",
    description="""
Регистрирует модель из предустановленного пресета с автоматической загрузкой.

## Как это работает

### Для локальных моделей (GGUF)
1. Проверяется совместимость с GPU (доступная VRAM)
2. Если модель отсутствует локально и `auto_download=true` — скачивается с HuggingFace
3. Модель загружается в GPU/RAM
4. Регистрируется в системе

### Для облачных моделей
1. Проверяется наличие API ключа в переменных окружения
2. Создаётся подключение к API провайдера
3. Модель регистрируется в системе

## Параметры запроса

| Параметр | Тип | Описание |
|----------|-----|----------|
| `preset_name` | string | Имя пресета из `/models/presets` |
| `auto_download` | bool | Автозагрузка с HuggingFace (default: true) |
| `quantization` | string | Переопределить квантизацию (q4_k_m, q5_k_m, q8_0, fp16) |

## Рекомендации

- Перед регистрацией локальной модели проверьте совместимость через `/models/check-compatibility`
- Для облачных моделей убедитесь что API ключ установлен в переменных окружения

## Ошибки

- **400** — ошибка загрузки или инициализации модели
- **404** — пресет не найден
- **409** — модель с таким именем уже зарегистрирована
""",
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
    downloader: ModelDownloaderDep,
    checker: CompatibilityCheckerDep,
) -> ModelInfo:
    """Зарегистрировать модель из YAML пресета.

    Args:
        request: Параметры регистрации
        loader: ModelPresetsLoader dependency
        downloader: ModelDownloader dependency
        checker: CompatibilityChecker dependency

    Returns:
        ModelInfo зарегистрированной модели

    Raises:
        HTTPException: 404 если пресет не найден, 409 если модель уже зарегистрирована

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
        return await _register_local_from_preset(
            preset=local_preset,
            downloader=downloader,
            checker=checker,
            auto_download=request.auto_download,
            quantization=request.quantization,
        )

    # Попробовать найти облачный пресет
    cloud_preset = loader.get_cloud_preset(request.preset_name)
    if cloud_preset:
        return await _register_cloud_from_preset(preset=cloud_preset)

    # Пресет не найден
    available_local = ", ".join(loader.list_local_names()[:5]) or "нет"
    available_cloud = ", ".join(loader.list_cloud_names()[:5]) or "нет"
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            f"Пресет '{request.preset_name}' не найден. "
            f"Локальные: {available_local}... Облачные: {available_cloud}..."
        ),
    )


@router.post(
    "/check-compatibility",
    response_model=CompatibilityResponse,
    summary="Проверить совместимость модели с GPU",
    description="""
Проверяет, поместится ли локальная модель в доступную видеопамять (VRAM).

## Зачем это нужно

Локальные GGUF модели требуют значительного объёма VRAM для работы.
Этот endpoint позволяет заранее проверить:
- Поместится ли модель в доступную VRAM
- Какую квантизацию лучше использовать
- Сколько памяти потребуется

## Как работает

1. Получает требования VRAM из пресета модели
2. Запрашивает текущую доступную VRAM у GPU
3. Сравнивает и выдаёт рекомендацию

## Параметры запроса

| Параметр | Тип | Описание |
|----------|-----|----------|
| `preset_name` | string | Имя локального пресета |
| `quantization` | string | Квантизация для проверки (опционально) |

## Квантизации

| Квантизация | Размер | Качество | Пример для 7B модели |
|-------------|--------|----------|---------------------|
| `q4_k_m` | ~50% | Хорошее | ~4-5 GB |
| `q5_k_m` | ~60% | Очень хорошее | ~5-6 GB |
| `q8_0` | ~90% | Отличное | ~8-9 GB |
| `fp16` | 100% | Максимальное | ~14 GB |

## Что возвращает

| Поле | Описание |
|------|----------|
| `compatible` | Поместится ли модель в VRAM |
| `required_vram_mb` | Требуемая VRAM в MB |
| `available_vram_mb` | Доступная VRAM в MB |
| `recommended_quantization` | Рекомендуемая квантизация (если не compatible) |
| `warning` | Предупреждение о нехватке памяти |

## Примечание

Проверка выполняется только для **локальных** моделей.
Облачные модели не требуют локальных ресурсов GPU.
""",
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


@router.get(
    "/download-status/{preset_name}",
    response_model=DownloadStatusResponse,
    summary="Проверить статус загрузки модели",
    description="""
Проверяет, скачана ли локальная модель и доступна ли она на HuggingFace Hub.

## Зачем это нужно

Перед регистрацией локальной модели полезно проверить:
- Есть ли модель уже на диске (не нужно качать заново)
- Доступна ли модель на HuggingFace для скачивания
- Какой размер файла модели

## Параметры

- **preset_name** (path) — имя локального пресета из `/models/presets`

## Что возвращает

| Поле | Описание |
|------|----------|
| `preset_name` | Имя пресета |
| `exists_locally` | Модель уже скачана |
| `local_path` | Путь к файлу на диске |
| `file_size_mb` | Размер файла в MB |
| `available_on_hf` | Доступна на HuggingFace |

## Использование

Если модель не скачана (`exists_locally=false`), она автоматически загрузится
при вызове `/models/register-from-preset` с `auto_download=true`.
""",
    responses={
        200: {"description": "Статус загрузки модели"},
        404: {"model": ErrorResponse, "description": "Локальный пресет не найден"},
    },
)
async def get_download_status(
    preset_name: str,
    loader: PresetsLoaderDep,
    downloader: ModelDownloaderDep,
) -> DownloadStatusResponse:
    """Получить статус загрузки модели.

    Args:
        preset_name: Имя пресета
        loader: ModelPresetsLoader dependency
        downloader: ModelDownloader dependency

    Returns:
        DownloadStatusResponse со статусом загрузки

    Raises:
        HTTPException: 404 если пресет не найден

    """
    preset = loader.get_local_preset(preset_name)
    if not preset:
        available = ", ".join(loader.list_local_names()[:10]) or "нет"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Локальный пресет '{preset_name}' не найден. "
                f"Доступные: {available}"
            ),
        )

    # Проверить локально
    exists, local_path = downloader.model_exists(preset.filename)
    file_size_mb = 0.0
    if exists and local_path:
        file_size_mb = local_path.stat().st_size / (1024**2)

    # Проверить на HuggingFace
    available_on_hf, _ = await downloader.check_availability(
        preset.huggingface_repo,
        preset.filename,
    )

    return DownloadStatusResponse(
        preset_name=preset_name,
        exists_locally=exists,
        local_path=str(local_path) if local_path else None,
        file_size_mb=file_size_mb,
        available_on_hf=available_on_hf,
    )


# === Helper Functions for Preset Registration ===


async def _register_local_from_preset(
    preset: Any,
    downloader: Any,
    checker: Any,
    auto_download: bool,
    quantization: str | None,
) -> ModelInfo:
    """Зарегистрировать локальную модель из пресета.

    Args:
        preset: LocalModelPreset
        downloader: ModelDownloader
        checker: CompatibilityChecker
        auto_download: Автоскачивание
        quantization: Переопределение квантизации

    Returns:
        ModelInfo зарегистрированной модели

    Raises:
        HTTPException: Если модель недоступна или несовместима

    """
    # Проверить совместимость (warning, не блокировка)
    compat = checker.check_compatibility(preset, quantization)
    if not compat.compatible:
        logger.warning(
            "Модель может не поместиться в VRAM",
            model=preset.name,
            required_mb=compat.required_vram_mb,
            available_mb=compat.available_vram_mb,
            recommended=compat.recommended_quantization,
        )

    # Скачать если нужно
    if auto_download:
        result = await downloader.download_if_needed(preset)
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка загрузки модели: {result.error_message}",
            )
        model_path = result.local_path
    else:
        # Проверить что модель есть локально
        exists, model_path = downloader.model_exists(preset.filename)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Модель '{preset.filename}' не найдена локально. "
                    "Установите auto_download=true для автоскачивания"
                ),
            )

    # Создать config для provider
    models_dir = Path(settings.models_dir)
    config = preset.to_register_config(models_dir)

    # Создать и зарегистрировать provider
    provider = await local.create_local_provider(
        model_name=preset.name,
        model_path=config["model_path"],
        context_window=config["context_window"],
        gpu_layers=config["gpu_layers"],
    )

    registry = get_provider_registry()
    registry.register(preset.name, provider)

    info = await provider.get_model_info()

    logger.info(
        "Локальная модель зарегистрирована из пресета",
        model=preset.name,
        path=str(model_path),
        compatible=compat.compatible,
    )

    return ModelInfo(
        name=info.name,
        provider=info.provider,
        context_window=info.context_window,
        max_output_tokens=info.max_output_tokens,
        supports_streaming=info.supports_streaming,
        supports_structured_output=info.supports_structured_output,
        loaded=info.loaded,
        extra={
            **info.extra,
            "compatibility_warning": compat.warning,
        },
    )


async def _register_cloud_from_preset(preset: Any) -> ModelInfo:
    """Зарегистрировать облачную модель из пресета.

    Args:
        preset: CloudModelPreset

    Returns:
        ModelInfo зарегистрированной модели

    Raises:
        HTTPException: Если API ключ не найден

    """
    import os

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
