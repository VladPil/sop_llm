"""Провайдер для локальных LLM моделей через HuggingFace Transformers.

Адаптация существующего LLMManager к новому интерфейсу BaseLLMProvider.
"""

import asyncio
from datetime import datetime
from typing import Any

import torch
from loguru import logger

from src.core.config import settings
from src.modules.llm.providers.base import BaseLLMProvider, ProviderCapability
from src.modules.llm.providers.factory import register_provider
from src.shared.errors import (
    MemoryExceededError,
    ModelNotLoadedError,
    ServiceUnavailableError,
)
from src.shared.utils import check_model_in_cache, model_loader


@register_provider("local")
class LocalLLMProvider(BaseLLMProvider):
    """Провайдер для локальных LLM моделей.

    Поддерживает:
    - Загрузку моделей из HuggingFace
    - Quantization (8-bit, 4-bit)
    - Контроль concurrent запросов
    - Управление памятью
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Инициализация провайдера.

        Args:
            config: Конфигурация провайдера

        """
        super().__init__(config)

        self.model: Any | None = None
        self.tokenizer: Any | None = None
        self.device = model_loader.device
        self.model_name: str | None = None

        # Пул запросов
        self.max_concurrent_requests = config.get(
            "max_concurrent_requests", settings.llm.max_concurrent_requests
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.active_requests = 0
        self.total_requests = 0

        # Очередь запросов
        self.request_queue: asyncio.Queue = asyncio.Queue()

    @property
    def provider_name(self) -> str:
        """Имя провайдера.

        Returns:
            Строка "local"

        """
        return "local"

    @property
    def capabilities(self) -> list[ProviderCapability]:
        """Поддерживаемые возможности.

        Returns:
            Список поддерживаемых возможностей

        """
        return [
            ProviderCapability.TEXT_GENERATION,
            ProviderCapability.CHAT_COMPLETION,
            ProviderCapability.JSON_MODE,
        ]

    async def initialize(self) -> None:
        """Инициализация провайдера - загрузка модели.

        Raises:
            Exception: Если загрузка модели не удалась

        """
        # Получаем параметры из конфига
        model_name = self.config.get("default_model", settings.llm.default_model)
        load_in_8bit = self.config.get("load_in_8bit", False)

        await self._load_model(model_name, load_in_8bit)

        self._is_initialized = True

        logger.info(
            f"LocalLLMProvider инициализирован: {self.model_name}, "
            f"device={self.device}, max_concurrent={self.max_concurrent_requests}"
        )

    async def _load_model(self, model_name: str, load_in_8bit: bool = False) -> None:
        """Загружает LLM модель.

        Args:
            model_name: Имя модели из HuggingFace
            load_in_8bit: Загружать в 8-bit режиме

        """
        self.model_name = model_name

        # Проверяем кэш перед загрузкой
        is_cached = check_model_in_cache(self.model_name)
        if is_cached:
            logger.info(f"Модель {self.model_name} уже в кэше, загружаем...")
        else:
            logger.info(
                f"Модель {self.model_name} не в кэше, "
                "будет загружена при первом запросе"
            )

        logger.info(f"Загружаем LLM модель: {self.model_name}")

        self.model, self.tokenizer = await model_loader.load_llm_model(
            model_name=self.model_name, load_in_8bit=load_in_8bit
        )

        logger.info(f"LLM модель загружена: {self.model_name}")

    def _check_memory_availability(self) -> None:
        """Проверяет доступность памяти.

        Raises:
            MemoryExceededError: Если памяти недостаточно

        """
        _available_gb, memory_percent = model_loader.check_available_memory()

        if memory_percent > settings.llm.memory_threshold_percent:
            raise MemoryExceededError(
                current=memory_percent,
                threshold=settings.llm.memory_threshold_percent,
                resource_type="memory",
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
        """Генерация текста.

        Args:
            prompt: Входной промпт
            model: Имя модели (игнорируется, используется загруженная)
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
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
            ModelNotLoadedError: Если модель не загружена
            MemoryExceededError: Если нет доступных ресурсов

        """
        if not self._is_initialized:
            raise RuntimeError("Provider not initialized. Call initialize() first.")

        if not self.model or not self.tokenizer:
            raise ModelNotLoadedError(model_name=self.model_name or "unknown")

        # Проверяем лимит токенов
        max_tokens = max_tokens or 512
        if max_tokens > settings.llm.max_tokens_per_request:
            max_tokens = settings.llm.max_tokens_per_request
            logger.warning(
                f"Запрошено max_tokens превышает лимит, используем {max_tokens}"
            )

        # Проверяем память
        self._check_memory_availability()

        # Улучшаем промпт для JSON mode
        enhanced_prompt = prompt
        if expected_format == "json":
            json_instruction = (
                "\n\nIMPORTANT: You must respond with valid JSON only. "
                "Do not include any explanations, markdown formatting, or additional text. "
                "Only output a properly formatted JSON object or array that can be parsed directly."
            )
            enhanced_prompt = prompt + json_instruction
            logger.info("JSON mode активирован для локальной модели")

        # Используем семафор для контроля concurrent requests
        async with self.semaphore:
            self.active_requests += 1
            self.total_requests += 1
            request_id = self.total_requests

            start_time = datetime.now()

            try:
                logger.info(
                    f"Начинаем генерацию запроса #{request_id}",
                    request_id=request_id,
                    model_name=self.model_name,
                    max_tokens=max_tokens,
                    expected_format=expected_format,
                    active_requests=self.active_requests,
                )

                # Запускаем генерацию в executor (blocking operation)
                generated_text = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._generate_sync,
                    enhanced_prompt,
                    max_tokens,
                    temperature,
                    top_p,
                    kwargs,
                )

                duration = (datetime.now() - start_time).total_seconds() * 1000

                # Подсчитываем токены
                input_tokens = len(self.tokenizer.encode(prompt))
                output_tokens = len(self.tokenizer.encode(generated_text))

                logger.info(
                    f"Завершена генерация запроса #{request_id}",
                    request_id=request_id,
                    duration_ms=round(duration, 2),
                    tokens_generated=output_tokens,
                )

                # Возвращаем в унифицированном формате
                return {
                    "text": generated_text,
                    "model": self.model_name,
                    "tokens": {
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": input_tokens + output_tokens,
                    },
                    "finish_reason": "stop",  # Для локальных моделей всегда "stop"
                    "metadata": {
                        "provider": "local",
                        "device": str(self.device),
                        "duration_ms": round(duration, 2),
                        "request_id": request_id,
                    },
                }

            except Exception as e:
                logger.error(f"Генерация не удалась для запроса #{request_id}: {e}")
                raise ServiceUnavailableError(
                    message=f"Не удалось сгенерировать текст: {e!s}"
                )

            finally:
                self.active_requests -= 1

    def _generate_sync(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        extra_kwargs: dict,
    ) -> str:
        """Синхронная генерация текста (для executor).

        Args:
            prompt: Входной промпт
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
            top_p: Top-p sampling параметр
            extra_kwargs: Дополнительные параметры

        Returns:
            Сгенерированный текст

        """
        # Убираем параметры, которые мы передаем явно
        filtered_kwargs = {
            k: v
            for k, v in extra_kwargs.items()
            if k
            not in [
                "max_new_tokens",
                "temperature",
                "top_p",
                "do_sample",
                "pad_token_id",
                "system_prompt",
                "model",
            ]
        }

        # Токенизация
        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=2048
        ).to(self.device)

        # Генерация
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=temperature > 0,
                pad_token_id=self.tokenizer.eos_token_id,
                **filtered_kwargs,
            )

        # Декодирование
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Удаляем исходный промпт из результата
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt) :].strip()

        return generated_text

    def is_available(self) -> bool:
        """Проверка доступности провайдера.

        Returns:
            True если модель загружена и готова к использованию

        """
        return (
            self._is_initialized
            and self.model is not None
            and self.tokenizer is not None
        )

    def get_stats(self) -> dict[str, Any]:
        """Получение статистики провайдера.

        Returns:
            Словарь со статистикой

        """
        return {
            "provider": "local",
            "model_name": self.model_name,
            "device": str(self.device),
            "model_loaded": self.model is not None,
            "is_available": self.is_available(),
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
            "queue_size": self.request_queue.qsize(),
        }

    async def cleanup(self) -> None:
        """Очистка ресурсов."""
        # Освобождаем память модели
        if self.model is not None:
            del self.model
            self.model = None

        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None

        # Очищаем CUDA cache если используется GPU
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("LocalLLMProvider очищен")
