"""Anthropic Provider для SOP LLM Executor.

Provider для Claude API (Anthropic).
"""

from typing import AsyncIterator
from anthropic import AsyncAnthropic
from config.settings import settings
from src.providers.base import (
    GenerationParams,
    GenerationResult,
    LLMProvider,
    ModelInfo,
    StreamChunk,
)
from src.utils.logging import get_logger

logger = get_logger()


class AnthropicProvider:
    """Provider для Anthropic Claude API.

    Поддерживает все модели Claude (Opus, Sonnet, Haiku).
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        context_window: int = 200000,  # Claude 3 default
        max_output_tokens: int = 4096,
    ) -> None:
        """Инициализировать Anthropic Provider.

        Args:
            model_name: Название модели (например, "claude-3-opus-20240229")
            api_key: Anthropic API ключ (если None, используется из settings)
            context_window: Размер контекстного окна
            max_output_tokens: Максимум токенов в ответе
        """
        self.model_name = model_name
        self.api_key = api_key or settings.anthropic_api_key
        self.context_window = context_window
        self.max_output_tokens = max_output_tokens

        if not self.api_key:
            msg = "Anthropic API key не установлен (ANTHROPIC_API_KEY)"
            raise ValueError(msg)

        # AsyncAnthropic client
        self.client = AsyncAnthropic(
            api_key=self.api_key,
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )

        logger.info(
            "AnthropicProvider инициализирован",
            model_name=model_name,
            context_window=context_window,
        )

    async def generate(
        self,
        prompt: str,
        params: GenerationParams,
    ) -> GenerationResult:
        """Сгенерировать текст (non-streaming).

        Args:
            prompt: Промпт для генерации
            params: Параметры генерации

        Returns:
            Результат генерации

        Raises:
            RuntimeError: Ошибка генерации
        """
        logger.debug(
            "Начало генерации",
            model=self.model_name,
            prompt_length=len(prompt),
            max_tokens=params.max_tokens,
        )

        try:
            # Подготовить параметры
            kwargs = {
                "model": self.model_name,
                "max_tokens": min(params.max_tokens, self.max_output_tokens),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": params.temperature,
                "top_p": params.top_p,
                "stream": False,
            }

            # Опциональные параметры
            if params.stop_sequences:
                kwargs["stop_sequences"] = params.stop_sequences

            # Генерация
            response = await self.client.messages.create(**kwargs)  # type: ignore[arg-type]

            # Извлечь результат (Claude возвращает list[ContentBlock])
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            finish_reason = response.stop_reason or "stop"

            # Token usage
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

            logger.info(
                "Генерация завершена",
                model=self.model_name,
                finish_reason=finish_reason,
                completion_tokens=usage["completion_tokens"],
            )

            return GenerationResult(
                text=text,
                finish_reason=finish_reason if finish_reason in ("end_turn", "max_tokens") else "stop",
                usage=usage,
                model=self.model_name,
                extra={
                    "response_id": response.id,
                    "stop_reason": response.stop_reason,
                },
            )

        except Exception as e:
            logger.error(
                "Ошибка генерации",
                model=self.model_name,
                error=str(e),
            )
            raise RuntimeError(f"Ошибка генерации: {e}") from e

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
        logger.debug(
            "Начало streaming генерации",
            model=self.model_name,
            prompt_length=len(prompt),
        )

        try:
            # Подготовить параметры
            kwargs = {
                "model": self.model_name,
                "max_tokens": min(params.max_tokens, self.max_output_tokens),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": params.temperature,
                "top_p": params.top_p,
                "stream": True,
            }

            # Опциональные параметры
            if params.stop_sequences:
                kwargs["stop_sequences"] = params.stop_sequences

            # Streaming генерация
            async with self.client.messages.stream(**kwargs) as stream:  # type: ignore[arg-type]
                async for text_chunk in stream.text_stream:
                    yield StreamChunk(text=text_chunk)

                # Получить финальный message с usage
                final_message = await stream.get_final_message()

                usage = {
                    "prompt_tokens": final_message.usage.input_tokens,
                    "completion_tokens": final_message.usage.output_tokens,
                    "total_tokens": final_message.usage.input_tokens + final_message.usage.output_tokens,
                }

                finish_reason = final_message.stop_reason or "stop"

                logger.info(
                    "Streaming завершён",
                    model=self.model_name,
                    finish_reason=finish_reason,
                    total_tokens=usage["total_tokens"],
                )

                # Последний chunk с usage
                yield StreamChunk(
                    text="",
                    finish_reason=finish_reason if finish_reason in ("end_turn", "max_tokens") else "stop",
                    usage=usage,
                )

        except Exception as e:
            logger.error(
                "Ошибка streaming генерации",
                model=self.model_name,
                error=str(e),
            )
            raise RuntimeError(f"Ошибка streaming: {e}") from e

    async def get_model_info(self) -> ModelInfo:
        """Получить метаданные модели.

        Returns:
            Информация о модели
        """
        return ModelInfo(
            name=self.model_name,
            provider="anthropic",
            context_window=self.context_window,
            max_output_tokens=self.max_output_tokens,
            supports_streaming=True,
            supports_structured_output=False,  # Claude пока не поддерживает JSON schema
            loaded=True,  # Remote модель всегда "loaded"
            extra={
                "api": "anthropic",
            },
        )

    async def health_check(self) -> bool:
        """Проверить доступность provider'а.

        Returns:
            True если API доступен
        """
        try:
            # Простой тестовый запрос
            await self.client.messages.create(
                model=self.model_name,
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}],
            )
            return True

        except Exception as e:
            logger.error(
                "Health check failed",
                model=self.model_name,
                error=str(e),
            )
            return False

    async def cleanup(self) -> None:
        """Очистить ресурсы (close HTTP connections).

        Вызывается при shutdown приложения.
        """
        await self.client.close()

        logger.info("AnthropicProvider cleanup выполнен", model=self.model_name)


# =================================================================
# Factory Function
# =================================================================

async def create_anthropic_provider(
    model_name: str,
    api_key: str | None = None,
    context_window: int = 200000,
    max_output_tokens: int = 4096,
) -> AnthropicProvider:
    """Создать Anthropic Provider.

    Args:
        model_name: Название модели Claude
        api_key: API ключ (опционально)
        context_window: Размер контекстного окна
        max_output_tokens: Максимум токенов в ответе

    Returns:
        AnthropicProvider instance
    """
    provider = AnthropicProvider(
        model_name=model_name,
        api_key=api_key,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
    )

    logger.info(
        "AnthropicProvider создан",
        model_name=model_name,
    )

    return provider
