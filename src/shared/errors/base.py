"""Base exception class for application errors.

Базовая логика исключений с автогенерацией кодов и сообщений.
"""

import re
from typing import Any

from loguru import logger
from pydantic import ValidationError

from src.shared.errors.context import get_trace_id
from src.shared.errors.schemas import ErrorDetail, ErrorResponse


class AppException(Exception):
    """Базовый класс для всех бизнес-ошибок.

    Автоматика:
    - Генерация error_code из имени класса (ModelNotFound -> MODEL_NOT_FOUND)
    - Генерация default_message из docstring
    - Валидация details через Pydantic
    - Генерация OpenAPI схем
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "Внутренняя ошибка сервера"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | ErrorDetail | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        """Инициализация исключения.

        Args:
            message: Сообщение об ошибке.
            details: Дополнительные детали.
            status_code: HTTP статус код.
            code: Код ошибки.

        """
        self.message = message or self.default_message

        if details is not None:
            if isinstance(details, ErrorDetail):
                self.details = details.model_dump(exclude_none=True)
            else:
                try:
                    validated = ErrorDetail(**details)
                    self.details = validated.model_dump(exclude_none=True)
                except ValidationError as e:
                    logger.exception(f"Invalid details in {self.__class__.__name__}: {e}")
                    msg = "Invalid details format"
                    raise ValueError(msg) from e
        else:
            self.details = {}

        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code

        super().__init__(self.message)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Автоматическая генерация code и default_message.

        Args:
            **kwargs: Дополнительные аргументы.

        """
        super().__init_subclass__(**kwargs)

        if cls.__name__ == "AppException":
            return

        # Генерация code из имени класса
        if "code" not in cls.__dict__:
            name = cls.__name__
            for suffix in ("Exception", "Error"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            cls.code = re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()

        # Генерация default_message из docstring
        if "default_message" not in cls.__dict__ and cls.__doc__:
            cls.default_message = cls.__doc__.strip().split("\n")[0]

    def to_response(self) -> ErrorResponse:
        """Сериализация в Pydantic модель.

        Returns:
            ErrorResponse с данными ошибки.

        """
        return ErrorResponse(
            error=self.code,
            message=self.message,
            details=self.details,
            trace_id=get_trace_id(),
        )

    @classmethod
    def openapi_response(cls) -> dict[str, Any]:
        """Генерация OpenAPI схемы.

        Returns:
            Словарь с OpenAPI схемой ответа.

        """
        return {
            "model": ErrorResponse,
            "description": cls.default_message,
            "content": {
                "application/json": {
                    "example": {
                        "error": cls.code,
                        "message": cls.default_message,
                        "details": {},
                        "trace_id": "example-trace-id",
                    }
                }
            },
        }
