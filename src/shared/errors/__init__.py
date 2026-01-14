"""Модуль обработки исключений приложения.

Предоставляет унифицированную систему исключений с автоматической генерацией
кодов ошибок, доменные исключения и маппинг инфраструктурных ошибок.

Основные компоненты:
    - AppException: Базовый класс всех доменных исключений
    - ErrorResponse: Pydantic схема для сериализации ошибок
    - Доменные исключения: ValidationError, NotFoundError, и т.д.
    - LLM-специфичные исключения: ModelNotFoundError, ProviderUnavailableError, и т.д.
    - ExceptionMapper: Маппинг инфраструктурных исключений на доменные

Examples:
    Использование доменных исключений:

    >>> from src.shared.errors import NotFoundError, ValidationError
    >>>
    >>> # Простое использование
    >>> raise NotFoundError(message="Пользователь не найден")
    >>>
    >>> # С дополнительными деталями
    >>> raise ValidationError(
    ...     message="Неверный формат email",
    ...     details={"field": "email", "value": "invalid"}
    ... )

    Использование LLM-специфичных исключений:

    >>> from src.shared.errors import ModelNotFoundError, TokenLimitExceededError
    >>>
    >>> raise ModelNotFoundError(model_name="gpt-4")
    >>> raise TokenLimitExceededError(tokens_used=5000, tokens_limit=4096)

    Использование маппера исключений:

    >>> from src.shared.errors import map_exception
    >>> import asyncpg
    >>>
    >>> try:
    ...     # Операция с БД
    ...     pass
    ... except asyncpg.UniqueViolationError as e:
    ...     raise map_exception(e)  # Автоматически преобразуется в ConflictError

"""

from src.shared.errors.base import AppException, ErrorResponse
from src.shared.errors.domain_errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
    NotImplementedError,
    RateLimitError,
    ServiceUnavailableError,
    TimeoutError,
    UnauthorizedError,
    ValidationError,
)
from src.shared.errors.llm_errors import (
    ContextLengthExceededError,
    GenerationFailedError,
    InvalidModelConfigError,
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderUnavailableError,
    TokenLimitExceededError,
)
from src.shared.errors.mapping import ExceptionMapper, exception_mapper, map_exception

__all__ = [
    "AppException",
    "BadRequestError",
    "ConflictError",
    "ContextLengthExceededError",
    "ErrorResponse",
    "ExceptionMapper",
    "ForbiddenError",
    "GenerationFailedError",
    "InternalServerError",
    "InvalidModelConfigError",
    "ModelNotFoundError",
    "NotFoundError",
    "NotImplementedError",
    "ProviderAuthenticationError",
    "ProviderUnavailableError",
    "RateLimitError",
    "ServiceUnavailableError",
    "TimeoutError",
    "TokenLimitExceededError",
    "UnauthorizedError",
    "ValidationError",
    "exception_mapper",
    "map_exception",
]
