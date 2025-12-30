"""OpenAI Provider для SOP LLM Executor.

Provider для официального OpenAI API (GPT models).
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from src.config import settings
from src.providers.base import (
    GenerationParams,
    GenerationResult,
    ModelInfo,
    StreamChunk,
)
from src.utils.logging import get_logger

logger = get_logger()


class OpenAIProvider:
    """Provider для официального OpenAI API.

    Поддерживает GPT-4, GPT-3.5 и другие модели OpenAI.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        context_window: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        """Инициализировать OpenAI Provider.

        Args:
            model_name: Название модели (например, "gpt-4-turbo-preview")
            api_key: OpenAI API ключ (если None, используется из settings)
            base_url: Base URL API (опционально, для Azure OpenAI)
            context_window: Размер контекстного окна (опционально)
            max_output_tokens: Максимум токенов в ответе (опционально)

        """
        self.model_name = model_name
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url
        self.context_window = context_window or self._get_default_context_window(model_name)
        self.max_output_tokens = max_output_tokens or settings.default_max_tokens

        if not self.api_key:
            msg = "OpenAI API key не установлен (OPENAI_API_KEY)"
            raise ValueError(msg)

        # Асинхронный OpenAI клиент
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )

        logger.info(
            "OpenAIProvider инициализирован",
            model_name=model_name,
            base_url=self.base_url,
            context_window=self.context_window,
        )

    def _get_default_context_window(self, model_name: str) -> int:
        """Получить дефолтный context window для модели.

        Args:
            model_name: Название модели

        Returns:
            Размер контекстного окна

        """
        # Известные размеры для популярных моделей
        model_contexts = {
            "gpt-4-turbo-preview": 128000,
            "gpt-4-turbo": 128000,
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-3.5-turbo": 16385,
            "gpt-3.5-turbo-16k": 16385,
        }

        return model_contexts.get(model_name, settings.default_context_window)

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

            # JSON schema для structured output (GPT-4 Turbo+)
            if params.response_format:
                kwargs["response_format"] = params.response_format

            # Генерация
            response = await self.client.chat.completions.create(**kwargs)  # type: ignore[arg-type]

            # Извлечь результат
            choice = response.choices[0]
            text = choice.message.content or ""
            finish_reason = choice.finish_reason

            # Использование токенов
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
                    "response_id": response.id,
                    "system_fingerprint": response.system_fingerprint,
                },
            )

        except Exception as e:
            logger.exception(
                "Ошибка генерации",
                model=self.model_name,
                error=str(e),
            )
            msg = f"Ошибка генерации: {e}"
            raise RuntimeError(msg) from e

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
                "stream_options": {"include_usage": True},  # Включить usage в последнем chunk
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

            # Генерация chunks
            async for chunk in stream:
                if not isinstance(chunk, ChatCompletionChunk):
                    continue

                choice = chunk.choices[0] if chunk.choices else None

                # Последний chunk с usage
                if choice is None and chunk.usage:
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }

                    logger.info(
                        "Streaming завершён",
                        model=self.model_name,
                        total_tokens=usage["total_tokens"],
                    )

                    yield StreamChunk(
                        text="",
                        finish_reason="stop",
                        usage=usage,
                    )
                    continue

                if choice is None:
                    continue

                delta = choice.delta
                text = delta.content or ""

                # Промежуточный chunk
                if text:
                    yield StreamChunk(text=text)

        except Exception as e:
            logger.exception(
                "Ошибка streaming генерации",
                model=self.model_name,
                error=str(e),
            )
            msg = f"Ошибка streaming: {e}"
            raise RuntimeError(msg) from e

    async def get_model_info(self) -> ModelInfo:
        """Получить метаданные модели.

        Returns:
            Информация о модели

        """
        # GPT-4 Turbo+ поддерживает JSON schema
        supports_structured = "gpt-4" in self.model_name.lower() and "turbo" in self.model_name.lower()

        return ModelInfo(
            name=self.model_name,
            provider="openai",
            context_window=self.context_window,
            max_output_tokens=self.max_output_tokens,
            supports_streaming=True,
            supports_structured_output=supports_structured,
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
            logger.exception(
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

        logger.info("OpenAIProvider cleanup выполнен", model=self.model_name)


async def create_openai_provider(
    model_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
    context_window: int | None = None,
    max_output_tokens: int | None = None,
) -> OpenAIProvider:
    """Создать OpenAI Provider.

    Args:
        model_name: Название модели GPT
        api_key: API ключ (опционально)
        base_url: Base URL API (опционально, для Azure)
        context_window: Размер контекстного окна (опционально)
        max_output_tokens: Максимум токенов (опционально)

    Returns:
        OpenAIProvider instance

    """
    provider = OpenAIProvider(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
    )

    # Health check
    if not await provider.health_check():
        msg = f"Health check failed для {model_name}"
        raise RuntimeError(msg)

    logger.info(
        "OpenAIProvider создан",
        model_name=model_name,
    )

    return provider
