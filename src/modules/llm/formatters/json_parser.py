"""JSON парсер для обработки JSON ответов от LLM.

Включает извлечение JSON из markdown блоков и валидацию.
"""

import json
import re
from typing import Any

from src.modules.llm.formatters.base import BaseResponseParser


class JSONResponseParser(BaseResponseParser):
    """Парсер для JSON ответов.

    Особенности:
    - Извлекает JSON из markdown code blocks (```json ... ```)
    - Извлекает JSON из обычных code blocks (``` ... ```)
    - Пытается найти JSON объект в тексте
    - Поддерживает валидацию по JSON Schema
    """

    def parse(
        self,
        response: str,
        expected_format: str = "text",
        json_schema: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """Парсинг ответа.

        Args:
            response: Текст ответа
            expected_format: Ожидаемый формат
            json_schema: JSON Schema для валидации (опционально)
            **kwargs: Дополнительные параметры

        Returns:
            Для expected_format="json": распарсенный dict/list
            Для expected_format="text": исходная строка

        Raises:
            ValueError: Если expected_format="json" но не удалось распарсить JSON

        """
        if expected_format != "json":
            return response

        # Попытка извлечь JSON из разных форматов
        json_text = self._extract_json(response)

        # Парсинг JSON
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in response: {e}\nText: {json_text[:200]}"
            raise ValueError(
                msg
            )

        # Валидация по схеме (если предоставлена)
        if json_schema:
            self._validate_schema(parsed, json_schema)

        return parsed

    def _extract_json(self, text: str) -> str:
        """Извлечение JSON из текста.

        Пытается найти JSON в следующем порядке:
        1. Markdown code block с языком json: ```json ... ```
        2. Обычный code block: ``` ... ```
        3. JSON объект в тексте: {...}
        4. JSON массив в тексте: [...]

        Args:
            text: Исходный текст

        Returns:
            Извлечённый JSON текст

        Raises:
            ValueError: Если JSON не найден

        """
        # 1. Поиск markdown json block
        json_match = re.search(
            r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE
        )
        if json_match:
            return json_match.group(1).strip()

        # 2. Поиск обычного code block
        code_match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if code_match:
            code_content = code_match.group(1).strip()
            # Проверяем что это похоже на JSON
            if code_content.startswith(("{", "[")):
                return code_content

        # 3. Поиск JSON объекта
        obj_match = re.search(r"\{.*\}", text, re.DOTALL)
        if obj_match:
            return obj_match.group(0)

        # 4. Поиск JSON массива
        arr_match = re.search(r"\[.*\]", text, re.DOTALL)
        if arr_match:
            return arr_match.group(0)

        # Если ничего не найдено, пытаемся парсить весь текст
        # (возможно это уже чистый JSON)
        text = text.strip()
        if text.startswith(("{", "[")):
            return text

        raise ValueError("No JSON found in response")

    def _validate_schema(self, data: Any, schema: dict) -> None:
        """Валидация JSON по схеме.

        Args:
            data: Данные для валидации
            schema: JSON Schema

        Raises:
            ValueError: Если данные не соответствуют схеме

        """
        try:
            from jsonschema import ValidationError, validate
        except ImportError:
            # jsonschema не установлен, пропускаем валидацию
            return

        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            msg = f"JSON validation error: {e.message}"
            raise ValueError(msg)
