"""Менеджер LLM моделей с поддержкой пула запросов."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

import torch
from loguru import logger

from src.core.config import settings
from src.shared.errors import MemoryExceededError, ModelNotLoadedError
from src.shared.utils import model_loader, check_model_in_cache


class LLMManager:
    """Менеджер для управления LLM моделью и запросами."""

    def __init__(self, max_concurrent_requests: Optional[int] = None) -> None:
        """Инициализация менеджера.

        Args:
            max_concurrent_requests: Максимум одновременных запросов
        """
        self.model: Optional[Any] = None
        self.tokenizer: Optional[Any] = None
        self.device = model_loader.device
        self.model_name: Optional[str] = None

        # Пул запросов
        self.max_concurrent_requests = (
            max_concurrent_requests or settings.llm.max_concurrent_requests
        )
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self.active_requests = 0
        self.total_requests = 0

        # Очередь запросов
        self.request_queue: asyncio.Queue = asyncio.Queue()

        logger.info(
            f"LLMManager инициализирован с max_concurrent={self.max_concurrent_requests}"
        )

    async def load_model(
        self, model_name: Optional[str] = None, load_in_8bit: bool = False
    ) -> None:
        """Загружает LLM модель.

        Args:
            model_name: Имя модели
            load_in_8bit: Загружать в 8-bit режиме
        """
        self.model_name = model_name or settings.llm.default_model

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
        available_gb, memory_percent = model_loader.check_available_memory()

        if memory_percent > settings.llm.memory_threshold_percent:
            raise MemoryExceededError(
                current=memory_percent,
                threshold=settings.llm.memory_threshold_percent,
                resource_type="memory",
            )

    async def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Генерирует текст на основе промпта.

        Args:
            prompt: Входной промпт
            max_tokens: Максимальное количество токенов
            temperature: Температура генерации
            top_p: Top-p sampling параметр
            **kwargs: Дополнительные параметры генерации

        Returns:
            Словарь с текстом и информацией о токенах:
            {
                "text": str,
                "tokens": {
                    "input": int,
                    "output": int,
                    "total": int
                }
            }

        Raises:
            ModelNotLoadedError: Если модель не загружена
            MemoryExceededError: Если нет доступных ресурсов
        """
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
                    active_requests=self.active_requests,
                )

                # Запускаем генерацию в executor (blocking operation)
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._generate_sync, prompt, max_tokens, temperature, top_p, kwargs
                )

                duration = (datetime.now() - start_time).total_seconds() * 1000

                # Подсчитываем токены
                input_tokens = len(self.tokenizer.encode(prompt))
                output_tokens = len(self.tokenizer.encode(result))

                logger.info(
                    f"Завершена генерация запроса #{request_id}",
                    request_id=request_id,
                    duration_ms=round(duration, 2),
                    tokens_generated=output_tokens,
                )

                return {
                    "text": result,
                    "tokens": {
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": input_tokens + output_tokens,
                    },
                }

            except Exception as e:
                logger.error(f"Генерация не удалась для запроса #{request_id}: {e}")
                raise

            finally:
                self.active_requests -= 1

    def _generate_sync(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        extra_kwargs: Dict,
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
        # Убираем параметры, которые мы передаем явно, из extra_kwargs
        # Также удаляем параметры, которые не поддерживаются model.generate()
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

    async def generate_with_timeout(
        self, prompt: str, timeout: Optional[int] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Генерирует текст с таймаутом.

        Args:
            prompt: Входной промпт
            timeout: Таймаут в секундах
            **kwargs: Параметры генерации

        Returns:
            Словарь с текстом и информацией о токенах

        Raises:
            asyncio.TimeoutError: Если превышен таймаут
        """
        timeout = timeout or settings.llm.request_timeout

        try:
            result = await asyncio.wait_for(
                self.generate(prompt, **kwargs), timeout=timeout
            )
            return result

        except asyncio.TimeoutError:
            logger.error(f"Таймаут генерации после {timeout}с")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Получает статистику менеджера.

        Returns:
            Словарь со статистикой
        """
        return {
            "model_name": self.model_name,
            "device": str(self.device),
            "model_loaded": self.model is not None,
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
            "queue_size": self.request_queue.qsize(),
        }


# Глобальный экземпляр
llm_manager = LLMManager()
