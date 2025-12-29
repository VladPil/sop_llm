"""Провайдер для Anthropic Claude API.

Адаптация существующего ClaudeProvider к новому интерфейсу BaseLLMProvider.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from anthropic import AsyncAnthropic
from loguru import logger

from src.core.config import settings
from src.modules.llm.providers.base import BaseLLMProvider, ProviderCapability
from src.modules.llm.providers.factory import register_provider
from src.shared.errors import ServiceUnavailableError


@register_provider("claude")
class ClaudeProvider(BaseLLMProvider):
    """Провайдер для работы с Claude API.

    Поддерживает:
    - Асинхронные запросы к Claude API
    - Контроль concurrent запросов
    - Streaming (опционально)
    - Vision (для поддерживаемых моделей)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Инициализация провайдера.

        Args:
            config: Конфигурация провайдера

        """
        super().__init__(config)

        self.client: AsyncAnthropic | None = None
        self.model_name: str = config.get("default_model", settings.claude.model)
        # API key: сначала из config, потом из settings (с проверкой на None)
        self.api_key: str | None = config.get("api_key") or settings.claude.api_key

        # Пул запросов
        self.max_concurrent_requests = config.get(
            "max_concurrent_requests", settings.claude.max_concurrent_requests
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.active_requests = 0
        self.total_requests = 0

    @property
    def provider_name(self) -> str:
        """Имя провайдера.

        Returns:
            Строка "claude"

        """
        return "claude"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        """Поддерживаемые возможности.

        Returns:
            Список поддерживаемых возможностей

        """
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.CHAT_COMPLETION,
            ProviderCapability.STREAMING,
            ProviderCapability.VISION,
        ]

    async def initialize(self) -> None:
        """Инициализация Claude API клиента.

        Raises:
            ValueError: Если API ключ не настроен

        """
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY не настроен. "
                "Пожалуйста, установите его в окружении или .env файле"
            )

        self.client = AsyncAnthropic(api_key=self.api_key)
        self._is_initialized = True

        logger.info(
            f"ClaudeProvider инициализирован: model={self.model_name}, "
            f"max_concurrent={self.max_concurrent_requests}"
        )

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        expected_format: str = "text",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Генерация текста через Claude API.

        Args:
            prompt: Входной промпт
            model: Имя модели Claude (опционально)
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации (0-1 для Claude)
            top_p: Top-p sampling параметр
            expected_format: Ожидаемый формат ответа ("text" или "json")
            **kwargs: Дополнительные параметры

        Returns:
            Унифицированный словарь с результатом:
            {
                "text": str,
                "model": str,
                "tokens": {"input": int, "output": int, "total": int},
                "finish_reason": str,
                "metadata": Dict
            }

        Raises:
            RuntimeError: Если провайдер не инициализирован
            ServiceUnavailableError: Если генерация не удалась

        """
        if not self._is_initialized:
            raise RuntimeError("Provider not initialized. Call initialize() first.")

        if not self.client:
            raise ServiceUnavailableError(message="Claude клиент не инициализирован")

        # Проверяем лимит токенов
        max_tokens = max_tokens or 1024
        if max_tokens > settings.llm.max_tokens_per_request:
            max_tokens = settings.llm.max_tokens_per_request
            logger.warning(
                f"Запрошенный max_tokens превышает лимит, используется {max_tokens}"
            )

        # Claude использует temperature в диапазоне 0-1
        if temperature > 1.0:
            temperature = 1.0
            logger.warning("Temperature ограничен до 1.0 для Claude API")

        model_to_use = model or self.model_name

        # Подготовка для JSON mode
        system_prompt = None
        if expected_format == "json":
            # Для Claude добавляем system prompt для JSON-only ответов
            system_prompt = (
                "You must respond with valid JSON only. "
                "Do not include any text before or after the JSON object. "
                "The response must be parseable by a JSON parser."
            )
            logger.info("JSON mode активирован для Claude API")

        # Используем семафор для контроля concurrent requests
        async with self.semaphore:
            self.active_requests += 1
            self.total_requests += 1
            request_id = self.total_requests

            start_time = datetime.now()

            try:
                logger.info(
                    f"Начало запроса к Claude API #{request_id}",
                    request_id=request_id,
                    model=model_to_use,
                    max_tokens=max_tokens,
                    expected_format=expected_format,
                    active_requests=self.active_requests,
                )

                # Вызываем Claude API
                api_params = {
                    "model": model_to_use,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "messages": [{"role": "user", "content": prompt}],
                }

                # Добавляем system prompt если нужен JSON
                if system_prompt:
                    api_params["system"] = system_prompt

                response = await self.client.messages.create(**api_params)

                # Извлекаем текст из ответа
                result_text = response.content[0].text

                # Получаем информацию о токенах
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens

                duration = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(
                    f"Запрос к Claude API #{request_id} завершён",
                    request_id=request_id,
                    duration_ms=round(duration, 2),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                # Возвращаем в унифицированном формате
                return {
                    "text": result_text,
                    "model": model_to_use,
                    "tokens": {
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": total_tokens,
                    },
                    "finish_reason": response.stop_reason or "stop",
                    "metadata": {
                        "provider": "claude",
                        "duration_ms": round(duration, 2),
                        "request_id": request_id,
                        "model_id": response.model,
                    },
                }

            except Exception as e:
                logger.error(
                    f"Запрос к Claude API #{request_id} не удался: {e}", exc_info=True
                )
                raise ServiceUnavailableError(message=f"Ошибка Claude API: {e!s}")

            finally:
                self.active_requests -= 1

    async def generate_streaming(
        self, prompt: str, model: str | None = None, **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming генерация через Claude API.

        Args:
            prompt: Входной промпт
            model: Имя модели
            **kwargs: Дополнительные параметры

        Yields:
            Словари с частями текста

        """
        if not self._is_initialized or not self.client:
            raise RuntimeError("Provider not initialized")

        model_to_use = model or self.model_name
        max_tokens = kwargs.get("max_tokens", 1024)
        temperature = kwargs.get("temperature", 0.7)
        top_p = kwargs.get("top_p", 0.9)

        async with self.semaphore:
            self.active_requests += 1
            try:
                async with self.client.messages.stream(
                    model=model_to_use,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        yield {
                            "text": text,
                            "finish_reason": None,
                        }

                    # Последний чанк с finish_reason
                    final_message = await stream.get_final_message()
                    yield {
                        "text": "",
                        "finish_reason": final_message.stop_reason or "stop",
                    }

            finally:
                self.active_requests -= 1

    def is_available(self) -> bool:
        """Проверка доступности провайдера.

        Returns:
            True если клиент инициализирован

        """
        return self._is_initialized and self.client is not None

    def get_stats(self) -> dict[str, Any]:
        """Получение статистики провайдера.

        Returns:
            Словарь со статистикой

        """
        return {
            "provider": "claude",
            "model_name": self.model_name,
            "is_available": self.is_available(),
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
        }

    async def cleanup(self) -> None:
        """Очистка ресурсов."""
        if self.client:
            await self.client.close()
            self.client = None

        logger.info("ClaudeProvider очищен")
