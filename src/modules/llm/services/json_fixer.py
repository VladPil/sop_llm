"""JSON Fixer Manager - исправляет некорректный JSON от слабых LLM моделей.

Использует более мощную модель для исправления.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

import torch
from jsonschema import ValidationError, validate
from loguru import logger

from src.core.config import settings
from src.shared.utils import model_loader
from src.shared.errors import JSONFixFailedError, MemoryExceededError, ModelNotLoadedError


class JSONFixerManager:
    """Менеджер для исправления некорректного JSON от LLM моделей."""

    def __init__(self) -> None:
        """Инициализация менеджера."""
        self.model: Optional[Any] = None
        self.tokenizer: Optional[Any] = None
        self.device = model_loader.device
        self.model_name: Optional[str] = None
        self.is_loaded = False

        # Отдельный семафор для JSON fixer (не блокируем основные запросы)
        self.semaphore = asyncio.Semaphore(1)  # По одному исправлению за раз
        self.active_requests = 0
        self.total_requests = 0
        self.successful_fixes = 0
        self.failed_fixes = 0

        logger.info("JSONFixerManager инициализирован")

    async def load_model(self) -> None:
        """Загружает модель для исправления JSON."""
        if self.is_loaded:
            logger.info("JSON Fixer модель уже загружена")
            return

        if not settings.json_fixer.enabled:
            logger.warning("JSON fixing отключен в настройках")
            return

        self.model_name = settings.json_fixer.model
        load_in_8bit = settings.json_fixer.load_in_8bit

        logger.info(
            f"Загрузка JSON Fixer модели: {self.model_name} (8-bit: {load_in_8bit})"
        )

        self.model, self.tokenizer = await model_loader.load_llm_model(
            model_name=self.model_name, load_in_8bit=load_in_8bit
        )

        self.is_loaded = True
        logger.info(f"JSON Fixer модель загружена: {self.model_name}")

    def _check_memory_availability(self) -> None:
        """Проверяет доступность памяти."""
        available_gb, memory_percent = model_loader.check_available_memory()

        if memory_percent > settings.llm.memory_threshold_percent:
            raise MemoryExceededError(
                current=memory_percent,
                threshold=settings.llm.memory_threshold_percent,
                resource_type="memory",
            )

    @staticmethod
    def validate_json(json_string: str, schema: Optional[Dict] = None) -> bool:
        """Валидирует JSON строку."""
        try:
            parsed = json.loads(json_string)
            if schema:
                validate(instance=parsed, schema=schema)
            return True
        except (json.JSONDecodeError, ValidationError) as e:
            logger.debug(f"JSON валидация не прошла: {e}")
            return False

    def _build_fix_prompt(
        self,
        broken_json: str,
        original_prompt: Optional[str] = None,
        schema: Optional[Dict] = None,
    ) -> str:
        """Создает промпт для исправления JSON."""
        prompt = """Ты - эксперт по исправлению JSON. Твоя задача - исправить некорректный JSON и вернуть только валидный JSON, без объяснений.

ВАЖНО:
- Верни ТОЛЬКО валидный JSON, без дополнительного текста
- Не добавляй markdown форматирование (```json)
- Исправь синтаксические ошибки (запятые, кавычки, скобки)
- Сохрани оригинальную структуру данных
- Если данные неполные - используй null для недостающих значений

"""
        if original_prompt:
            prompt += f"Оригинальный запрос пользователя:\n{original_prompt}\n\n"

        if schema:
            prompt += f"Ожидаемая структура JSON:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"

        prompt += f"Некорректный JSON для исправления:\n{broken_json}\n\nИсправленный JSON:"

        return prompt

    async def fix_json(
        self,
        broken_json: str,
        original_prompt: Optional[str] = None,
        schema: Optional[Dict] = None,
        max_attempts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Исправляет некорректный JSON."""
        if not self.is_loaded:
            await self.load_model()

        if not self.model or not self.tokenizer:
            raise ModelNotLoadedError(model_name=self.model_name or "json_fixer")

        if not settings.json_fixer.enabled:
            return {
                "success": False,
                "fixed_json": None,
                "parsed": None,
                "attempts": 0,
                "error": "JSON fixing отключен в настройках",
            }

        max_attempts = max_attempts or settings.json_fixer.max_attempts

        # Сначала проверим - может JSON уже валидный?
        if self.validate_json(broken_json, schema):
            logger.info("JSON уже валидный, исправление не требуется")
            self.total_requests += 1
            self.successful_fixes += 1
            return {
                "success": True,
                "fixed_json": broken_json,
                "parsed": json.loads(broken_json),
                "attempts": 0,
                "error": None,
            }

        # Проверяем память
        self._check_memory_availability()

        async with self.semaphore:
            self.active_requests += 1
            self.total_requests += 1
            request_id = self.total_requests

            start_time = datetime.now()

            try:
                logger.info(
                    f"Начало исправления JSON #{request_id}",
                    request_id=request_id,
                    broken_json_length=len(broken_json),
                    max_attempts=max_attempts,
                )

                for attempt in range(1, max_attempts + 1):
                    prompt = self._build_fix_prompt(
                        broken_json=broken_json,
                        original_prompt=original_prompt,
                        schema=schema,
                    )

                    fixed_json = await asyncio.get_event_loop().run_in_executor(
                        None, self._generate_sync, prompt
                    )

                    fixed_json = self._clean_json_response(fixed_json)

                    if self.validate_json(fixed_json, schema):
                        duration = (datetime.now() - start_time).total_seconds() * 1000
                        self.successful_fixes += 1

                        logger.info(
                            f"JSON успешно исправлен #{request_id}",
                            request_id=request_id,
                            attempt=attempt,
                            duration_ms=round(duration, 2),
                        )

                        return {
                            "success": True,
                            "fixed_json": fixed_json,
                            "parsed": json.loads(fixed_json),
                            "attempts": attempt,
                            "error": None,
                        }

                    logger.warning(
                        f"Попытка {attempt}/{max_attempts} не удалась для #{request_id}"
                    )

                # Все попытки исчерпаны
                duration = (datetime.now() - start_time).total_seconds() * 1000
                self.failed_fixes += 1

                logger.error(
                    f"Не удалось исправить JSON #{request_id}",
                    request_id=request_id,
                    attempts=max_attempts,
                    duration_ms=round(duration, 2),
                )

                return {
                    "success": False,
                    "fixed_json": fixed_json,
                    "parsed": None,
                    "attempts": max_attempts,
                    "error": f"Не удалось исправить JSON за {max_attempts} попыток",
                }

            except Exception as e:
                self.failed_fixes += 1
                logger.error(f"Ошибка при исправлении JSON #{request_id}: {e}")

                return {
                    "success": False,
                    "fixed_json": None,
                    "parsed": None,
                    "attempts": max_attempts,
                    "error": str(e),
                }

            finally:
                self.active_requests -= 1

    def _clean_json_response(self, text: str) -> str:
        """Очищает ответ от markdown форматирования и лишнего текста."""
        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Пытаемся найти JSON объект или массив
        start_brace = text.find("{")
        start_bracket = text.find("[")

        start = -1
        if start_brace != -1 and start_bracket != -1:
            start = min(start_brace, start_bracket)
        elif start_brace != -1:
            start = start_brace
        elif start_bracket != -1:
            start = start_bracket

        if start == -1:
            return text

        if text[start] == "{":
            end = text.rfind("}")
        else:
            end = text.rfind("]")

        if end != -1 and end > start:
            text = text[start : end + 1]

        return text.strip()

    def _generate_sync(self, prompt: str) -> str:
        """Синхронная генерация текста (для executor)."""
        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=4096
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=2048,
                temperature=0.1,
                top_p=0.9,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt) :].strip()

        return generated_text

    async def fix_json_with_timeout(
        self, broken_json: str, timeout: Optional[int] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Исправляет JSON с таймаутом."""
        timeout = timeout or settings.json_fixer.timeout

        try:
            result = await asyncio.wait_for(
                self.fix_json(broken_json, **kwargs), timeout=timeout
            )
            return result

        except asyncio.TimeoutError:
            logger.error(f"JSON fixing timeout после {timeout}s")
            return {
                "success": False,
                "fixed_json": None,
                "parsed": None,
                "attempts": 0,
                "error": f"Таймаут исправления JSON после {timeout}s",
            }

    def get_stats(self) -> Dict[str, Any]:
        """Получает статистику JSON fixer."""
        success_rate = 0.0
        if self.total_requests > 0:
            success_rate = (self.successful_fixes / self.total_requests) * 100

        return {
            "model_name": self.model_name,
            "device": str(self.device),
            "model_loaded": self.is_loaded,
            "enabled": settings.json_fixer.enabled,
            "load_in_8bit": settings.json_fixer.load_in_8bit,
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "successful_fixes": self.successful_fixes,
            "failed_fixes": self.failed_fixes,
            "success_rate_percent": round(success_rate, 2),
        }


# Глобальный экземпляр
json_fixer = JSONFixerManager()
