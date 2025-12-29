"""Унифицированный интерфейс для работы с разными LLM провайдерами."""

from typing import Any, Literal

from loguru import logger

from src.modules.llm.services.json_fixer import json_fixer
from src.modules.llm.services.llm_manager import llm_manager


class UnifiedLLM:
    """Унифицированный интерфейс для работы с локальными моделями и API."""

    def __init__(self) -> None:
        """Инициализация."""
        self.local_manager = llm_manager
        logger.info("UnifiedLLM инициализирован")

    async def generate(
        self,
        prompt: str,
        provider: Literal["local"] = "local",
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        expected_format: Literal["text", "json"] = "text",
        json_schema: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Генерирует текст используя выбранный провайдер."""
        logger.info(f"Генерируем текст с провайдером={provider}, модель={model}, формат={expected_format}")

        try:
            result = await self.local_manager.generate_with_timeout(
                prompt=prompt, max_tokens=max_tokens, temperature=temperature, top_p=top_p, **kwargs
            )

            response = {
                "text": result["text"],
                "provider": "local",
                "model": self.local_manager.model_name or "unknown",
                "tokens": result["tokens"],
            }

            if expected_format == "json":
                response = await self._process_json_response(
                    response=response, json_schema=json_schema, original_prompt=prompt
                )

            return response

        except Exception as e:
            logger.error(f"Генерация не удалась с провайдером={provider}: {e}", exc_info=True)
            raise

    async def _process_json_response(
        self, response: dict[str, Any], json_schema: dict[str, Any] | None, original_prompt: str
    ) -> dict[str, Any]:
        """Обрабатывает JSON ответ: валидирует и исправляет при необходимости."""
        generated_text = response["text"]

        is_valid = json_fixer.validate_json(generated_text, json_schema)

        if is_valid:
            logger.info("Сгенерированный JSON валидный, исправление не требуется")
            response["was_fixed"] = False
            response["fix_attempts"] = 0
            return response

        logger.warning("Сгенерированный JSON невалидный, пытаемся исправить")

        fix_result = await json_fixer.fix_json(
            broken_json=generated_text, original_prompt=original_prompt, schema=json_schema
        )

        if fix_result["success"]:
            logger.info(f"JSON успешно исправлен после {fix_result['attempts']} попыток")
            response["text"] = fix_result["fixed_json"]
            response["was_fixed"] = True
            response["fix_attempts"] = fix_result["attempts"]
        else:
            logger.error(f"Не удалось исправить JSON: {fix_result['error']}")
            response["was_fixed"] = False
            response["fix_attempts"] = fix_result["attempts"]

        return response

    def get_stats(self) -> dict[str, Any]:
        """Получает статистику провайдеров."""
        return {"local": self.local_manager.get_stats()}


# Глобальный экземпляр
unified_llm = UnifiedLLM()
