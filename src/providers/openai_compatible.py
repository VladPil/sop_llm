"""OpenAI-Compatible Provider для SOP LLM Executor.

Универсальный provider для OpenAI-совместимых API:
- LM Studio
- vLLM
- Ollama
- OpenRouter
- Together AI
- Любые другие OpenAI-compatible endpoints
"""

from typing import AsyncIterator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
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


class OpenAICompatibleProvider:
    """Provider для OpenAI-совместимых API.

    Работает с любым сервером, реализующим OpenAI Chat Completions API.
    """

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        context_window: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        """Инициализировать OpenAI-Compatible Provider.

        Args:
            model_name: Название модели на сервере
            base_url: Base URL API (если None, используется из settings)
            api_key: API ключ (если None, используется из settings)
            context_window: Размер контекстного окна (опционально)
            max_output_tokens: Максимум токенов в ответе (опционально)
        """
        self.model_name = model_name
        self.base_url = base_url or settings.openai_compatible_base_url
        self.api_key = api_key or settings.openai_compatible_api_key
        self.context_window = context_window or settings.default_context_window
        self.max_output_tokens = max_output_tokens or settings.default_max_tokens

        # AsyncOpenAI client
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )

        logger.info(
            "OpenAICompatibleProvider инициализирован",
            model_name=model_name,
            base_url=self.base_url,
            context_window=self.context_window,
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
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": params.max_tokens,
                "temperature": params.temperature,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "stream": False,
            }

            # Опциональные параметры
            if params.stop_sequences:
                kwargs["stop"] = params.stop_sequences

            if params.seed is not None:
                kwargs["seed"] = params.seed

            # JSON schema для structured output (если поддерживается)
            if params.response_format:
                kwargs["response_format"] = params.response_format

            # Генерация
            response = await self.client.chat.completions.create(**kwargs)  # type: ignore[arg-type]

            # Извлечь результат
            choice = response.choices[0]
            text = choice.message.content or ""
            finish_reason = choice.finish_reason

            # Token usage
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }

            logger.info(
                "Генерация завершена",
                model=self.model_name,
                finish_reason=finish_reason,
                completion_tokens=usage["completion_tokens"],
            )

            return GenerationResult(
                text=text,
                finish_reason=finish_reason if finish_reason in ("stop", "length") else "error",
                usage=usage,
                model=self.model_name,
                extra={
                    "base_url": self.base_url,
                    "response_id": response.id,
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
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": params.max_tokens,
                "temperature": params.temperature,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "stream": True,
            }

            # Опциональные параметры
            if params.stop_sequences:
                kwargs["stop"] = params.stop_sequences

            if params.seed is not None:
                kwargs["seed"] = params.seed

            if params.response_format:
                kwargs["response_format"] = params.response_format

            # Streaming генерация
            stream = await self.client.chat.completions.create(**kwargs)  # type: ignore[arg-type]

            # Yield chunks
            async for chunk in stream:
                if not isinstance(chunk, ChatCompletionChunk):
                    continue

                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue

                delta = choice.delta
                text = delta.content or ""
                finish_reason = choice.finish_reason

                # Последний chunk
                if finish_reason:
                    # OpenAI не отправляет usage в streaming, используем None
                    usage = None

                    logger.info(
                        "Streaming завершён",
                        model=self.model_name,
                        finish_reason=finish_reason,
                    )

                    yield StreamChunk(
                        text=text,
                        finish_reason=finish_reason if finish_reason in ("stop", "length") else "error",
                        usage=usage,
                    )

                else:
                    # Промежуточный chunk
                    if text:  # Пропускаем пустые chunks
                        yield StreamChunk(text=text)

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
        # Попытаться получить info через /v1/models (если поддерживается)
        supports_structured_output = False

        try:
            models = await self.client.models.list()
            model_data = next((m for m in models.data if m.id == self.model_name), None)

            if model_data:
                # Некоторые серверы возвращают метаданные
                supports_structured_output = getattr(model_data, "supports_response_format", False)

        except Exception:
            # Endpoint не поддерживается, используем defaults
            pass

        return ModelInfo(
            name=self.model_name,
            provider="openai_compatible",
            context_window=self.context_window,
            max_output_tokens=self.max_output_tokens,
            supports_streaming=True,
            supports_structured_output=supports_structured_output,
            loaded=True,  # Remote модель всегда "loaded"
            extra={
                "base_url": self.base_url,
            },
        )

    async def health_check(self) -> bool:
        """Проверить доступность provider'а.

        Returns:
            True если API доступен
        """
        try:
            # Попытаться получить список моделей
            await self.client.models.list()
            return True

        except Exception as e:
            logger.error(
                "Health check failed",
                model=self.model_name,
                base_url=self.base_url,
                error=str(e),
            )
            return False

    async def cleanup(self) -> None:
        """Очистить ресурсы (close HTTP connections).

        Вызывается при shutdown приложения.
        """
        await self.client.close()

        logger.info("OpenAICompatibleProvider cleanup выполнен", model=self.model_name)


# =================================================================
# Factory Function
# =================================================================

async def create_openai_compatible_provider(
    model_name: str,
    base_url: str | None = None,
    api_key: str | None = None,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
) -> OpenAICompatibleProvider:
    """Создать OpenAI-Compatible Provider.

    Args:
        model_name: Название модели
        base_url: Base URL API (опционально)
        api_key: API ключ (опционально)
        context_window: Размер контекстного окна (опционально)
        max_output_tokens: Максимум токенов (опционально)

    Returns:
        OpenAICompatibleProvider instance
    """
    provider = OpenAICompatibleProvider(
        model_name=model_name,
        base_url=base_url,
        api_key=api_key,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
    )

    # Health check
    if not await provider.health_check():
        msg = f"Health check failed для {model_name} на {provider.base_url}"
        raise RuntimeError(msg)

    logger.info(
        "OpenAICompatibleProvider создан",
        model_name=model_name,
        base_url=provider.base_url,
    )

    return provider
