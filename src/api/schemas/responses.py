"""Response Schemas для SOP LLM Executor API.

Pydantic models для API responses.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    """Ответ с информацией о задаче.

    Используется в:
    - POST /api/v1/tasks/ (создание задачи)
    - GET /api/v1/tasks/{task_id} (статус задачи)
    """

    task_id: str = Field(description="Уникальный ID задачи")

    status: Literal["pending", "processing", "completed", "failed"] = Field(
        description="Статус задачи"
    )

    model: str = Field(description="Название модели")

    created_at: str = Field(description="Timestamp создания (ISO 8601)")

    updated_at: str = Field(description="Timestamp последнего обновления (ISO 8601)")

    finished_at: str | None = Field(
        default=None,
        description="Timestamp завершения (ISO 8601, только для completed/failed)",
    )

    # Result (только для completed)
    result: dict[str, Any] | None = Field(
        default=None,
        description="Результат генерации (только для completed статуса)",
    )

    # Error (только для failed)
    error: str | None = Field(
        default=None,
        description="Сообщение об ошибке (только для failed статуса)",
    )

    # Metadata
    webhook_url: str | None = Field(
        default=None,
        description="URL для callback",
    )

    idempotency_key: str | None = Field(
        default=None,
        description="Ключ идемпотентности",
    )


class GenerationResult(BaseModel):
    """Результат генерации (часть TaskResponse.result).

    Структура поля `result` в TaskResponse когда status=completed.
    """

    text: str = Field(description="Сгенерированный текст")

    finish_reason: Literal["stop", "length", "error"] = Field(
        description="Причина завершения генерации"
    )

    usage: dict[str, int] = Field(
        description="Статистика токенов (prompt_tokens, completion_tokens, total_tokens)"
    )

    model: str = Field(description="Название модели")

    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific метаданные",
    )


class ModelInfo(BaseModel):
    """Информация о модели.

    GET /api/v1/models/{model_name}
    """

    name: str = Field(description="Название модели")

    provider: Literal["local", "openai_compatible", "anthropic", "openai", "custom"] = Field(
        description="Тип провайдера"
    )

    context_window: int = Field(description="Размер контекстного окна")

    max_output_tokens: int = Field(description="Максимум токенов в ответе")

    supports_streaming: bool = Field(description="Поддержка streaming")

    supports_structured_output: bool = Field(
        description="Поддержка structured output (GBNF/JSON schema)"
    )

    loaded: bool = Field(description="Модель загружена в память/VRAM")

    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific метаданные (VRAM usage, quantization, etc.)",
    )


class ModelsListResponse(BaseModel):
    """Список зарегистрированных моделей.

    GET /api/v1/models/
    """

    models: list[ModelInfo] = Field(description="Список моделей")

    total: int = Field(description="Общее количество моделей")


class HealthCheckResponse(BaseModel):
    """Health check ответ.

    GET /api/v1/monitor/health
    """

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        description="Общий статус сервиса"
    )

    redis: bool = Field(description="Redis доступен")

    providers: dict[str, bool] = Field(
        description="Статус каждого provider (model_name: is_healthy)"
    )

    gpu: dict[str, Any] | None = Field(
        default=None,
        description="GPU информация (если local provider используется)",
    )


class GPUStatsResponse(BaseModel):
    """Статистика GPU.

    GET /api/v1/monitor/gpu
    """

    gpu_info: dict[str, Any] = Field(
        description="Метаданные GPU (name, driver, CUDA, etc.)"
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


class ErrorResponse(BaseModel):
    """Стандартный error response.

    Используется для всех ошибок (4xx, 5xx).
    """

    error: str = Field(description="Тип ошибки")

    message: str = Field(description="Человекочитаемое сообщение")

    details: dict[str, Any] | None = Field(
        default=None,
        description="Дополнительные детали (опционально)",
    )
