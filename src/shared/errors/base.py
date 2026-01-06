"""Базовый класс исключений приложения.

Этот модуль содержит `AppException` - базовый класс для всех доменных исключений
приложения с автоматической генерацией кодов ошибок и методом сериализации.
"""

from typing import Any
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Схема ответа с ошибкой.

    Attributes:
        error_code: Уникальный код ошибки (генерируется из имени класса).
        message: Человекочитаемое описание ошибки.
        details: Дополнительная информация об ошибке (опционально).
    """

    error_code: str = Field(..., description="Уникальный код ошибки")
    message: str = Field(..., description="Описание ошибки")
    details: dict[str, Any] | None = Field(None, description="Дополнительные детали")


class AppException(Exception):
    """Базовое исключение приложения.

    Автоматически генерирует error_code из имени класса (snake_case) и извлекает
    message из docstring класса, если не указан явно.

    Attributes:
        status_code: HTTP статус код (по умолчанию 500).
        code: Уникальный код ошибки.
        message: Описание ошибки.
        details: Дополнительная информация.

    Examples:
        >>> class CustomError(AppException):
        ...     '''Произошла кастомная ошибка.'''
        ...     status_code = 400
        >>>
        >>> error = CustomError(details={"field": "value"})
        >>> error.code
        'custom_error'
        >>> error.message
        'Произошла кастомная ошибка.'
    """

    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация исключения.

        Args:
            message: Описание ошибки. Если не указано, берется из docstring.
            details: Дополнительная информация об ошибке.
        """
        self.code = self._generate_error_code()
        self.message = message or self._get_default_message()
        self.details = details or {}
        super().__init__(self.message)

    def _generate_error_code(self) -> str:
        """Генерирует error_code из имени класса.

        Преобразует CamelCase в snake_case.

        Returns:
            Код ошибки в формате snake_case.

        Examples:
            >>> ValidationError -> validation_error
            >>> NotFoundError -> not_found_error
        """
        name = self.__class__.__name__
        # Вставляем подчеркивание перед заглавными буквами
        snake_case = ""
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                snake_case += "_"
            snake_case += char.lower()
        return snake_case

    def _get_default_message(self) -> str:
        """Извлекает сообщение по умолчанию из docstring класса.

        Returns:
            Первая строка docstring или имя класса, если docstring отсутствует.
        """
        doc = self.__class__.__doc__
        if doc:
            # Берем первую непустую строку из docstring
            lines = [line.strip() for line in doc.strip().split("\n")]
            return next((line for line in lines if line), self.__class__.__name__)
        return self.__class__.__name__

    def to_response(self) -> ErrorResponse:
        """Преобразует исключение в Pydantic схему ответа.

        Returns:
            ErrorResponse: Схема ответа с ошибкой для сериализации в JSON.
        """
        return ErrorResponse(
            error_code=self.code,
            message=self.message,
            details=self.details if self.details else None,
        )

    def __repr__(self) -> str:
        """Строковое представление исключения."""
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"
