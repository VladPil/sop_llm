"""Request Schemas для SOP LLM Executor API.

Pydantic models для валидации входящих запросов.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    """Запрос на создание задачи генерации.

    POST /api/v1/tasks/
    """

    model: str = Field(
        description="Название модели (должна быть зарегистрирована в registry)",
        examples=["qwen2.5-7b-instruct", "gpt-4-turbo", "claude-3-opus"],
    )

    prompt: str = Field(
        description="Промпт для генерации",
        min_length=1,
        examples=["Explain quantum computing in simple terms."],
    )

    # Generation parameters (опциональные, используются defaults)
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Температура генерации",
    )

    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=128000,
        description="Максимум токенов в ответе",
    )

    top_p: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling",
    )

    top_k: int = Field(
        default=40,
        ge=0,
        description="Top-K sampling",
    )

    frequency_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Штраф за частоту токенов",
    )

    presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Штраф за присутствие токенов",
    )

    stop_sequences: list[str] = Field(
        default_factory=list,
        description="Stop последовательности",
        examples=[["###", "Human:", "Assistant:"]],
    )

    seed: int | None = Field(
        default=None,
        description="Random seed для воспроизводимости",
    )

    # Structured output
    response_format: dict[str, Any] | None = Field(
        default=None,
        description="JSON schema для structured output (OpenAI-style)",
        examples=[{"type": "json_object"}],
    )

    grammar: str | None = Field(
        default=None,
        description="GBNF grammar для llama.cpp structured output",
    )

    # Streaming
    stream: bool = Field(
        default=False,
        description="Использовать streaming генерацию",
    )

    # Callbacks
    webhook_url: str | None = Field(
        default=None,
        description="URL для callback после завершения (опционально)",
    )

    # Idempotency
    idempotency_key: str | None = Field(
        default=None,
        description="Ключ идемпотентности для дедупликации запросов",
        examples=["user-123-request-456"],
    )

    # Priority
    priority: float = Field(
        default=0.0,
        description="Приоритет задачи (выше = раньше обработается)",
    )

    # Provider-specific
    extra_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific параметры",
    )


class RegisterModelRequest(BaseModel):
    """Запрос на регистрацию модели.

    POST /api/v1/models/register
    """

    name: str = Field(
        description="Уникальное название модели для registry",
        examples=["qwen2.5-7b-instruct"],
    )

    provider: Literal["local", "openai_compatible", "anthropic", "openai", "custom"] = Field(
        description="Тип провайдера"
    )

    # Provider-specific config
    config: dict[str, Any] = Field(
        description="Конфигурация провайдера (зависит от типа)",
        examples=[
            {
                # Local provider
                "model_path": "/app/models/qwen2.5-7b-instruct.gguf",
                "context_window": 8192,
                "gpu_layers": -1,
            },
            {
                # OpenAI provider
                "api_key": "sk-...",
                "model_name": "gpt-4-turbo",
            },
        ],
    )


class UnregisterModelRequest(BaseModel):
    """Запрос на удаление модели из registry.

    DELETE /api/v1/models/{model_name}
    """

    cleanup: bool = Field(
        default=True,
        description="Очистить ресурсы модели (unload, close connections)",
    )
