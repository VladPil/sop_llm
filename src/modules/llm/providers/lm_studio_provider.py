"""Провайдер для LM Studio - локальный сервер с OpenAI-compatible API.

Новый провайдер для работы с моделями запущенными в LM Studio.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from src.modules.llm.providers.base import BaseLLMProvider, ProviderCapability
from src.modules.llm.providers.factory import register_provider
from src.shared.errors import ServiceUnavailableError


@register_provider("lm_studio")
class LMStudioProvider(BaseLLMProvider):
    """Провайдер для LM Studio.

    LM Studio - это десктоп приложение для запуска локальных LLM,
    которое предоставляет OpenAI-compatible API на localhost.

    Поддерживает:
    - OpenAI-compatible API (chat/completions endpoint)
    - Streaming генерацию
    - Любые модели загруженные в LM Studio
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Инициализация провайдера.

        Args:
            config: Конфигурация провайдера

        """
        super().__init__(config)

        # Конфигурация
        self.base_url = config.get("base_url", "http://localhost:1234/v1")
        self.api_key = config.get(
            "api_key", "lm-studio"
        )  # Dummy key для LM Studio
        self.timeout = config.get("timeout", 60.0)
        self.model_name = config.get("default_model", "local-model")

        # HTTP клиент
        self.client: httpx.AsyncClient | None = None

        # Пул запросов
        self.max_concurrent_requests = config.get("max_concurrent_requests", 5)
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.active_requests = 0
        self.total_requests = 0

    @property
    def provider_name(self) -> str:
        """Имя провайдера.

        Returns:
            Строка "lm_studio"

        """
        return "lm_studio"

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
        ]

    async def initialize(self) -> None:
        """Инициализация HTTP клиента и проверка доступности LM Studio.

        Raises:
            RuntimeError: Если LM Studio недоступен

        """
        # Создаём HTTP клиент
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        # Проверка доступности LM Studio
        try:
            response = await self.client.get("/models")
            response.raise_for_status()

            models_data = response.json()
            logger.info(
                f"LM Studio доступен, найдено моделей: {len(models_data.get('data', []))}"
            )

            self._is_initialized = True

        except httpx.ConnectError:
            msg = (
                f"Не удалось подключиться к LM Studio по адресу {self.base_url}. "
                "Убедитесь, что LM Studio запущен и API сервер активен."
            )
            raise RuntimeError(
                msg
            )
        except Exception as e:
            msg = f"Ошибка при инициализации LM Studio: {e}"
            raise RuntimeError(msg)

        logger.info(
            f"LMStudioProvider инициализирован: {self.base_url}, "
            f"default_model={self.model_name}"
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
        """Генерация текста через LM Studio API.

        Args:
            prompt: Входной промпт
            model: Имя модели (опционально, использует default)
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
            top_p: Top-p sampling параметр
            expected_format: Ожидаемый формат ответа ("text" или "json")
            **kwargs: Дополнительные параметры

        Returns:
            Унифицированный словарь с результатом

        Raises:
            RuntimeError: Если провайдер не инициализирован
            ServiceUnavailableError: Если генерация не удалась

        """
        if not self._is_initialized:
            raise RuntimeError("Provider not initialized. Call initialize() first.")

        if not self.client:
            raise ServiceUnavailableError(message="HTTP клиент не инициализирован")

        model_to_use = model or self.model_name
        max_tokens = max_tokens or 1024

        # Используем семафор для контроля concurrent requests
        async with self.semaphore:
            self.active_requests += 1
            self.total_requests += 1
            request_id = self.total_requests

            start_time = datetime.now()

            try:
                logger.info(
                    f"Начало запроса к LM Studio #{request_id}",
                    request_id=request_id,
                    model=model_to_use,
                    max_tokens=max_tokens,
                    expected_format=expected_format,
                    active_requests=self.active_requests,
                )

                # Формируем запрос в формате OpenAI
                messages = []

                # Добавляем system message для JSON mode
                if expected_format == "json":
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "You must respond with valid JSON only. "
                                "Do not include any text, explanations, or markdown formatting. "
                                "Only output a valid JSON object or array."
                            ),
                        }
                    )
                    logger.info("JSON mode активирован для LM Studio")

                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": model_to_use,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "stream": False,
                }

                # Добавляем response_format для JSON mode (OpenAI-compatible)
                if expected_format == "json":
                    payload["response_format"] = {"type": "json_object"}

                # Добавляем дополнительные параметры
                for key, value in kwargs.items():
                    if key not in payload and key != "system_prompt":
                        payload[key] = value

                # Отправляем запрос
                response = await self.client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()

                # Извлекаем результат
                choice = data["choices"][0]
                generated_text = choice["message"]["content"]
                finish_reason = choice.get("finish_reason", "stop")

                # Извлекаем токены
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

                duration = (datetime.now() - start_time).total_seconds() * 1000

                logger.info(
                    f"Запрос к LM Studio #{request_id} завершён",
                    request_id=request_id,
                    duration_ms=round(duration, 2),
                    tokens_generated=output_tokens,
                )

                # Возвращаем в унифицированном формате
                return {
                    "text": generated_text,
                    "model": data.get("model", model_to_use),
                    "tokens": {
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": total_tokens,
                    },
                    "finish_reason": finish_reason,
                    "metadata": {
                        "provider": "lm_studio",
                        "duration_ms": round(duration, 2),
                        "request_id": request_id,
                        "base_url": self.base_url,
                    },
                }

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP ошибка при запросе к LM Studio #{request_id}: {e}",
                    exc_info=True,
                )
                raise ServiceUnavailableError(
                    message=f"LM Studio HTTP error: {e.response.status_code}"
                )

            except httpx.ConnectError:
                logger.error(
                    f"Не удалось подключиться к LM Studio для запроса #{request_id}"
                )
                raise ServiceUnavailableError(
                    message="LM Studio недоступен. Убедитесь, что сервер запущен."
                )

            except Exception as e:
                logger.error(
                    f"Запрос к LM Studio #{request_id} не удался: {e}", exc_info=True
                )
                raise ServiceUnavailableError(message=f"Ошибка LM Studio: {e!s}")

            finally:
                self.active_requests -= 1

    async def generate_streaming(
        self, prompt: str, model: str | None = None, **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming генерация через LM Studio API.

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

        payload = {
            "model": model_to_use,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }

        async with self.semaphore:
            self.active_requests += 1
            try:
                async with self.client.stream(
                    "POST", "/chat/completions", json=payload
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        if line.startswith("data: "):
                            data = line[6:]

                            if data == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data)
                                delta = chunk["choices"][0]["delta"]

                                if "content" in delta:
                                    yield {
                                        "text": delta["content"],
                                        "finish_reason": None,
                                    }

                                finish_reason = chunk["choices"][0].get(
                                    "finish_reason"
                                )
                                if finish_reason:
                                    yield {
                                        "text": "",
                                        "finish_reason": finish_reason,
                                    }

                            except json.JSONDecodeError:
                                continue

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
            "provider": "lm_studio",
            "base_url": self.base_url,
            "default_model": self.model_name,
            "is_available": self.is_available(),
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
        }

    async def cleanup(self) -> None:
        """Очистка ресурсов - закрытие HTTP клиента."""
        if self.client:
            await self.client.aclose()
            self.client = None

        logger.info("LMStudioProvider очищен")
