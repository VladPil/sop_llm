"""Base types и Protocol для LLM Providers.

Использует typing.Protocol для duck typing вместо ABC (согласно ТЗ).
"""

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class GenerationParams(BaseModel):
    """Параметры генерации (общие для всех providers).

    Следует OpenAI Chat Completions API спецификации.
    """

    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Температура генерации (0 = детерминированный, 2 = креативный)",
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
        description="Top-K sampling (0 = disabled)",
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
    )
    seed: int | None = Field(
        default=None,
        description="Random seed для воспроизводимости",
    )

    # Structured Output
    response_format: dict[str, Any] | None = Field(
        default=None,
        description="JSON schema для structured output (OpenAI-style)",
    )
    grammar: str | None = Field(
        default=None,
        description="GBNF grammar для llama.cpp structured output",
    )

    # Provider-specific
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific параметры",
    )


class GenerationResult(BaseModel):
    """Результат генерации."""

    text: str = Field(description="Сгенерированный текст")
    finish_reason: Literal["stop", "length", "error"] = Field(
        description="Причина завершения генерации"
    )
    usage: dict[str, int] = Field(
        description="Статистика использования токенов (prompt_tokens, completion_tokens, total_tokens)"
    )
    model: str = Field(description="Название модели")
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific метаданные",
    )


class StreamChunk(BaseModel):
    """Chunk для streaming генерации."""

    text: str = Field(description="Текст chunk'а")
    finish_reason: Literal["stop", "length", "error"] | None = Field(
        default=None,
        description="Причина завершения (только в последнем chunk)",
    )
    usage: dict[str, int] | None = Field(
        default=None,
        description="Статистика (только в последнем chunk)",
    )


class ModelInfo(BaseModel):
    """Метаданные модели."""

    name: str = Field(description="Название модели")
    provider: Literal["local", "openai_compatible", "anthropic", "openai", "custom"] = Field(
        description="Тип провайдера"
    )
    context_window: int = Field(description="Размер контекстного окна")
    max_output_tokens: int = Field(description="Максимум токенов в ответе")
    supports_streaming: bool = Field(default=True, description="Поддержка streaming")
    supports_structured_output: bool = Field(
        default=False,
        description="Поддержка structured output (GBNF/JSON schema)",
    )
    loaded: bool = Field(default=False, description="Модель загружена в память/VRAM")
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific метаданные (VRAM usage, quantization, etc.)",
    )


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol для всех LLM providers.

    Использует Protocol вместо ABC для duck typing (согласно ТЗ).
    Все providers должны реализовать эти методы.
    """

    async def generate(
        self,
        prompt: str,
        params: GenerationParams,
    ) -> GenerationResult:
        """Сгенерировать текст (не-streaming).

        Args:
            prompt: Промпт для генерации
            params: Параметры генерации

        Returns:
            Результат генерации

        Raises:
            RuntimeError: Ошибка генерации

        """
        ...

    async def generate_stream(
        self,
        prompt: str,
        params: GenerationParams,
    ) -> AsyncIterator[StreamChunk]:
        """Сгенерировать текст (streaming).

        Args:
            prompt: Промпт для генерации
            params: Параметры генерации

        Yields:
            Stream chunks

        Raises:
            RuntimeError: Ошибка генерации

        """
        ...

    async def get_model_info(self) -> ModelInfo:
        """Получить метаданные модели.

        Returns:
            Информация о модели

        """
        ...

    async def health_check(self) -> bool:
        """Проверить доступность provider'а.

        Returns:
            True если provider доступен

        """
        ...

    async def cleanup(self) -> None:
        """Очистить ресурсы (unload model, close connections, etc.).

        Вызывается при shutdown приложения.
        """
        ...
