"""Базовые классы для форматирования промптов и парсинга ответов.

Strategy Pattern для разных способов форматирования.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BasePromptFormatter(ABC):
    """Базовый класс для форматирования промптов.

    Используется Strategy Pattern - разные стратегии форматирования
    для разных моделей и форматов.
    """

    @abstractmethod
    def format_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Форматирование простого промпта.

        Args:
            prompt: Исходный промпт
            **kwargs: Дополнительные параметры

        Returns:
            Отформатированный промпт
        """

    @abstractmethod
    def format_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Форматирование chat истории в промпт.

        Args:
            messages: Список сообщений в формате:
                [
                    {"role": "system", "content": "..."},
                    {"role": "user", "content": "..."},
                    {"role": "assistant", "content": "..."},
                ]
            **kwargs: Дополнительные параметры

        Returns:
            Отформатированный промпт
        """


class DefaultPromptFormatter(BasePromptFormatter):
    """Форматтер по умолчанию.

    Не меняет промпт, возвращает как есть.
    """

    def format_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Возвращает промпт без изменений.

        Args:
            prompt: Исходный промпт
            **kwargs: Дополнительные параметры (игнорируются)

        Returns:
            Исходный промпт
        """
        return prompt

    def format_chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Форматирует chat в простой текст.

        Формат:
        System: ...
        User: ...
        Assistant: ...

        Args:
            messages: Список сообщений
            **kwargs: Дополнительные параметры (игнорируются)

        Returns:
            Отформатированный промпт
        """
        formatted_parts = []
        for msg in messages:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            formatted_parts.append(f"{role}: {content}")

        return "\n".join(formatted_parts)


class BaseResponseParser(ABC):
    """Базовый класс для парсинга ответов от LLM."""

    @abstractmethod
    def parse(
        self, response: str, expected_format: str = "text", **kwargs: Any
    ) -> Any:
        """Парсинг ответа.

        Args:
            response: Текст ответа от LLM
            expected_format: Ожидаемый формат ("text", "json", etc.)
            **kwargs: Дополнительные параметры

        Returns:
            Распарсенный результат (str, dict, list, etc.)

        Raises:
            ValueError: Если не удалось распарсить
        """


class DefaultResponseParser(BaseResponseParser):
    """Парсер по умолчанию.

    Возвращает текст как есть.
    """

    def parse(
        self, response: str, expected_format: str = "text", **kwargs: Any
    ) -> Any:
        """Возвращает текст без изменений.

        Args:
            response: Текст ответа
            expected_format: Ожидаемый формат (игнорируется)
            **kwargs: Дополнительные параметры (игнорируются)

        Returns:
            Исходный текст
        """
        return response
