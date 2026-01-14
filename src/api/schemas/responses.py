"""Response Schemas для SOP LLM Executor API.

Pydantic models для API responses.
"""

from typing import Any

from pydantic import BaseModel, Field

from src.core.enums import FinishReason, HealthStatus, ProviderType, TaskStatus

# Типизированные вложенные модели для лучшей Swagger документации


class TokenUsage(BaseModel):
    """Статистика использования токенов."""

    prompt_tokens: int = Field(description="Количество токенов в промпте")
    completion_tokens: int = Field(description="Количество токенов в ответе")
    total_tokens: int = Field(description="Общее количество токенов")


class VRAMUsage(BaseModel):
    """Статистика использования VRAM."""

    total_mb: int = Field(description="Общий объём VRAM в MB")
    used_mb: int = Field(description="Использовано VRAM в MB")
    free_mb: int = Field(description="Свободно VRAM в MB")
    used_percent: float = Field(description="Процент использования VRAM")


class GPUInfo(BaseModel):
    """Информация о GPU."""

    name: str = Field(description="Название GPU")
    driver_version: str | None = Field(default=None, description="Версия драйвера")
    cuda_version: str | None = Field(default=None, description="Версия CUDA")
    compute_capability: str | None = Field(default=None, description="Compute capability")
    total_memory_mb: int | None = Field(default=None, description="Общий объём памяти в MB")


class TaskResponse(BaseModel):
    """Ответ с информацией о задаче.

    Используется в:
    - POST /api/v1/tasks/ (создание задачи)
    - GET /api/v1/tasks/{task_id} (статус задачи)
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "task_abc123",
                    "status": "completed",
                    "model": "gpt-4-turbo",
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:30:05Z",
                    "finished_at": "2024-01-15T10:30:05Z",
                    "result": {
                        "text": "Сгенерированный ответ модели",
                        "finish_reason": "stop",
                        "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
                    },
                    "error": None,
                    "webhook_url": None,
                    "idempotency_key": "user-123-request-456",
                    "trace_id": "trace_xyz789",
                }
            ]
        }
    }

    task_id: str = Field(description="Уникальный ID задачи")

    status: TaskStatus = Field(description="Статус задачи")

    model: str = Field(description="Название модели")

    created_at: str = Field(description="Timestamp создания (ISO 8601)")

    updated_at: str = Field(description="Timestamp последнего обновления (ISO 8601)")

    finished_at: str | None = Field(
        default=None,
        description="Timestamp завершения (ISO 8601, только для completed/failed)",
    )

    # Результат (только для completed)
    result: dict[str, Any] | None = Field(
        default=None,
        description="Результат генерации (только для completed статуса)",
    )

    # Ошибка (только для failed)
    error: str | None = Field(
        default=None,
        description="Сообщение об ошибке (только для failed статуса)",
    )

    # Метаданные
    webhook_url: str | None = Field(
        default=None,
        description="URL для callback",
    )

    idempotency_key: str | None = Field(
        default=None,
        description="Ключ идемпотентности",
    )

    # Observability
    trace_id: str | None = Field(
        default=None,
        description="Langfuse trace ID для отладки и корреляции логов",
    )


class GenerationResult(BaseModel):
    """Результат генерации (часть TaskResponse.result).

    Структура поля `result` в TaskResponse когда status=completed.
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Сгенерированный ответ модели",
                    "finish_reason": "stop",
                    "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
                    "model": "gpt-4-turbo",
                    "extra": {"response_id": "chatcmpl-abc123"},
                }
            ]
        }
    }

    text: str = Field(description="Сгенерированный текст")

    finish_reason: FinishReason = Field(description="Причина завершения генерации")

    usage: TokenUsage = Field(description="Статистика использования токенов")

    model: str = Field(description="Название модели")

    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific метаданные (response_id, latency_ms, etc.)",
    )


class ModelInfo(BaseModel):
    """Информация о модели.

    GET /api/v1/models/{model_name}
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "gpt-4-turbo",
                    "provider": "openai",
                    "context_window": 128000,
                    "max_output_tokens": 4096,
                    "supports_streaming": True,
                    "supports_structured_output": True,
                    "loaded": True,
                    "extra": {"api_version": "2024-01-01", "organization": "my-org"},
                }
            ]
        }
    }

    name: str = Field(description="Название модели")

    provider: ProviderType = Field(description="Тип провайдера")

    context_window: int = Field(description="Размер контекстного окна")

    max_output_tokens: int = Field(description="Максимум токенов в ответе")

    supports_streaming: bool = Field(description="Поддержка streaming")

    supports_structured_output: bool = Field(
        description="Поддержка structured output (GBNF/JSON schema)"
    )

    loaded: bool = Field(description="Модель загружена в память/VRAM")

    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific метаданные (VRAM usage, quantization, api_version)",
    )


class ModelsListResponse(BaseModel):
    """Список зарегистрированных моделей.

    GET /api/v1/models/
    """

    models: list[ModelInfo] = Field(description="Список моделей")

    total: int = Field(description="Общее количество моделей")


class ComponentHealth(BaseModel):
    """Статус отдельного компонента системы."""

    status: str = Field(description="Статус: 'up', 'down', 'degraded'")
    message: str | None = Field(default=None, description="Сообщение об ошибке или детали")
    response_time_ms: float | None = Field(default=None, description="Время ответа в миллисекундах")


class SystemResources(BaseModel):
    """Системные ресурсы."""

    disk_usage_percent: float = Field(description="Использование диска в процентах")
    disk_free_gb: float = Field(description="Свободное место на диске в GB")
    memory_usage_percent: float = Field(description="Использование памяти в процентах")
    memory_available_gb: float = Field(description="Доступная память в GB")


class HealthCheckResponse(BaseModel):
    """Health check ответ.

    GET /api/v1/monitor/health
    """

    status: HealthStatus = Field(description="Общий статус сервиса")
    version: str = Field(description="Версия приложения")
    uptime_seconds: float = Field(description="Время работы в секундах")
    timestamp: str = Field(description="Текущее время сервера (ISO 8601)")

    # Компоненты
    components: dict[str, ComponentHealth] = Field(
        description="Статус каждого компонента (redis, providers, etc.)"
    )

    # Системные ресурсы
    resources: SystemResources = Field(description="Системные ресурсы")

    # GPU (опционально)
    gpu: dict[str, Any] | None = Field(
        default=None,
        description="GPU информация (если local provider используется)",
    )


class GPUStatsResponse(BaseModel):
    """Статистика GPU.

    GET /api/v1/monitor/gpu
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
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
            ]
        }
    }

    gpu_info: dict[str, Any] = Field(
        description="Метаданные GPU (name, driver_version, cuda_version, compute_capability)"
    )

    vram_usage: dict[str, Any] = Field(
        description="VRAM usage (total_mb, used_mb, free_mb, used_percent)"
    )

    is_locked: bool = Field(description="GPU занят задачей")

    current_task_id: str | None = Field(
        default=None,
        description="ID текущей задачи на GPU",
    )


class QueueStatsResponse(BaseModel):
    """Статистика очереди задач.

    GET /api/v1/monitor/queue
    """

    queue_size: int = Field(description="Количество задач в очереди")

    processing_task: str | None = Field(
        default=None,
        description="ID обрабатываемой задачи",
    )

    recent_logs_count: int = Field(description="Количество последних логов")


class EmbeddingResponse(BaseModel):
    """Ответ с embeddings.

    POST /api/v1/embeddings
    """

    embeddings: list[list[float]] = Field(
        description="Список векторных представлений для каждого текста"
    )

    model: str = Field(description="Название использованной модели")

    dimensions: int = Field(description="Размерность векторов")


class ErrorResponse(BaseModel):
    """Стандартный error response.

    Используется для всех ошибок (4xx, 5xx).
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "validation_error",
                    "message": "Невалидный запрос: поле 'prompt' обязательно",
                    "details": {"field": "prompt", "reason": "field required"},
                    "trace_id": "trace_xyz789",
                },
                {
                    "error": "not_found",
                    "message": "Модель 'unknown-model' не найдена",
                    "details": None,
                    "trace_id": "trace_abc123",
                },
            ]
        }
    }

    error: str = Field(
        description="Тип ошибки (validation_error, not_found, internal_error, rate_limit, etc.)"
    )

    message: str = Field(description="Человекочитаемое сообщение об ошибке")

    details: dict[str, Any] | None = Field(
        default=None,
        description="Дополнительные детали (field, reason, etc.)",
    )

    # Observability
    trace_id: str | None = Field(
        default=None,
        description="Langfuse trace ID для отладки и корреляции логов",
    )


# Model Presets Responses


class CompatibilityResponse(BaseModel):
    """Результат проверки совместимости модели с GPU.

    POST /api/v1/models/check-compatibility
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "compatible": True,
                    "required_vram_mb": 5500,
                    "available_vram_mb": 24000,
                    "recommended_quantization": None,
                    "warning": None,
                },
                {
                    "compatible": False,
                    "required_vram_mb": 28000,
                    "available_vram_mb": 24000,
                    "recommended_quantization": "q4_k_m",
                    "warning": "Модель требует 28000MB VRAM, доступно 24000MB. Рекомендуется использовать q4_k_m",
                },
            ]
        }
    }

    compatible: bool = Field(
        description="True если модель поместится в доступную VRAM"
    )

    required_vram_mb: int = Field(
        description="Требуемая VRAM в MB для выбранной квантизации"
    )

    available_vram_mb: int = Field(
        description="Доступная VRAM в MB на текущем GPU"
    )

    recommended_quantization: str | None = Field(
        default=None,
        description="Рекомендуемая квантизация если модель не помещается (q4_k_m, q5_k_m, q8_0, fp16)",
    )

    warning: str | None = Field(
        default=None,
        description="Предупреждение если модель не помещается в VRAM",
    )


class LocalPresetInfo(BaseModel):
    """Информация о локальном пресете модели."""

    name: str = Field(description="Уникальное имя пресета")
    huggingface_repo: str = Field(description="HuggingFace репозиторий")
    filename: str = Field(description="Имя GGUF файла")
    size_b: float = Field(description="Размер модели в миллиардах параметров")
    context_window: int = Field(description="Размер контекстного окна")
    vram_requirements: dict[str, int] = Field(
        description="Требования VRAM по квантизациям (q4_k_m, q5_k_m, q8_0, fp16) в MB"
    )


class CloudPresetInfo(BaseModel):
    """Информация об облачном пресете модели."""

    name: str = Field(description="Уникальное имя пресета")
    provider: str = Field(description="Провайдер (openai, anthropic, gemini, etc.)")
    model_name: str = Field(description="ID модели в API провайдера")
    api_key_env_var: str | None = Field(default=None, description="Имя переменной окружения с API ключом. None для Ollama.")


class EmbeddingPresetInfo(BaseModel):
    """Информация об embedding пресете модели."""

    name: str = Field(description="Уникальное имя пресета")
    huggingface_repo: str = Field(description="HuggingFace репозиторий")
    dimensions: int = Field(description="Размерность embedding вектора")


class PresetsListResponse(BaseModel):
    """Список всех доступных пресетов моделей.

    GET /api/v1/models/presets
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "local_models": [
                        {
                            "name": "qwen2.5-7b-instruct",
                            "huggingface_repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
                            "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
                            "size_b": 7.0,
                            "context_window": 32768,
                            "vram_requirements": {
                                "q4_k_m": 5500,
                                "q5_k_m": 6500,
                                "q8_0": 9000,
                                "fp16": 14000,
                            },
                        }
                    ],
                    "cloud_models": [
                        {
                            "name": "claude-3.5-sonnet",
                            "provider": "anthropic",
                            "model_name": "claude-3-5-sonnet-20241022",
                            "api_key_env_var": "ANTHROPIC_API_KEY",
                        }
                    ],
                    "embedding_models": [
                        {
                            "name": "multilingual-e5-large",
                            "huggingface_repo": "intfloat/multilingual-e5-large",
                            "dimensions": 1024,
                        }
                    ],
                    "total_local": 1,
                    "total_cloud": 1,
                    "total_embedding": 1,
                }
            ]
        }
    }

    local_models: list[LocalPresetInfo] = Field(
        description="Список локальных пресетов (GGUF модели)"
    )

    cloud_models: list[CloudPresetInfo] = Field(
        description="Список облачных пресетов (API провайдеры)"
    )

    embedding_models: list[EmbeddingPresetInfo] = Field(
        description="Список embedding пресетов"
    )

    total_local: int = Field(description="Количество локальных пресетов")

    total_cloud: int = Field(description="Количество облачных пресетов")

    total_embedding: int = Field(description="Количество embedding пресетов")


class DownloadStatusResponse(BaseModel):
    """Статус загрузки модели.

    GET /api/v1/models/download-status/{preset_name}
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "preset_name": "qwen2.5-7b-instruct",
                    "exists_locally": True,
                    "local_path": "/models/qwen2.5-7b-instruct-q4_k_m.gguf",
                    "file_size_mb": 4370.5,
                    "available_on_hf": True,
                },
                {
                    "preset_name": "llama-3.2-8b-instruct",
                    "exists_locally": False,
                    "local_path": None,
                    "file_size_mb": 0.0,
                    "available_on_hf": True,
                },
            ]
        }
    }

    preset_name: str = Field(description="Имя пресета")

    exists_locally: bool = Field(
        description="True если модель уже скачана локально"
    )

    local_path: str | None = Field(
        default=None,
        description="Путь к локальному файлу модели",
    )

    file_size_mb: float = Field(
        default=0.0,
        description="Размер файла в MB (если существует локально)",
    )

    available_on_hf: bool = Field(
        description="True если модель доступна на HuggingFace Hub"
    )


# Conversation Responses


class ConversationMessage(BaseModel):
    """Сообщение в диалоге."""

    role: str = Field(description="Роль: system, user, assistant")
    content: str = Field(description="Текст сообщения")
    timestamp: str = Field(description="Время добавления (ISO 8601)")


class ConversationResponse(BaseModel):
    """Информация о диалоге.

    POST /api/v1/conversations/ - создание
    GET /api/v1/conversations/{conversation_id} - получение
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "conv_abc123def456",
                    "model": "claude-3.5-sonnet",
                    "system_prompt": "Ты - полезный ассистент",
                    "message_count": 5,
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:35:00Z",
                    "metadata": {"user_id": "user_123"},
                }
            ]
        }
    }

    conversation_id: str = Field(description="Уникальный ID диалога")

    model: str | None = Field(
        default=None,
        description="Модель по умолчанию для диалога",
    )

    system_prompt: str | None = Field(
        default=None,
        description="Системный промпт диалога",
    )

    message_count: int = Field(
        default=0,
        description="Количество сообщений в диалоге",
    )

    created_at: str = Field(description="Время создания (ISO 8601)")

    updated_at: str = Field(description="Время последнего обновления (ISO 8601)")

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Дополнительные метаданные",
    )


class ConversationDetailResponse(ConversationResponse):
    """Детальная информация о диалоге с сообщениями.

    GET /api/v1/conversations/{conversation_id}?include_messages=true
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "conv_abc123def456",
                    "model": "claude-3.5-sonnet",
                    "system_prompt": "Ты - полезный ассистент",
                    "message_count": 3,
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:35:00Z",
                    "metadata": None,
                    "messages": [
                        {"role": "system", "content": "Ты - полезный ассистент", "timestamp": "2024-01-15T10:30:00Z"},
                        {"role": "user", "content": "Привет!", "timestamp": "2024-01-15T10:30:01Z"},
                        {"role": "assistant", "content": "Здравствуйте! Чем могу помочь?", "timestamp": "2024-01-15T10:30:02Z"},
                    ],
                }
            ]
        }
    }

    messages: list[ConversationMessage] = Field(
        default_factory=list,
        description="История сообщений диалога",
    )


class ConversationsListResponse(BaseModel):
    """Список диалогов.

    GET /api/v1/conversations/
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversations": [
                        {
                            "conversation_id": "conv_abc123",
                            "model": "gpt-4-turbo",
                            "message_count": 10,
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T11:00:00Z",
                        },
                        {
                            "conversation_id": "conv_def456",
                            "model": "claude-3.5-sonnet",
                            "message_count": 5,
                            "created_at": "2024-01-14T09:00:00Z",
                            "updated_at": "2024-01-14T09:30:00Z",
                        },
                    ],
                    "total": 2,
                    "limit": 100,
                    "offset": 0,
                }
            ]
        }
    }

    conversations: list[ConversationResponse] = Field(
        description="Список диалогов"
    )

    total: int = Field(description="Общее количество диалогов")

    limit: int = Field(description="Лимит для пагинации")

    offset: int = Field(description="Смещение для пагинации")
