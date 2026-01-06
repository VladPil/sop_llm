"""Маппинг инфраструктурных исключений на доменные.

Этот модуль содержит `ExceptionMapper` для преобразования исключений
инфраструктурного слоя (БД, кэш, внешние API) в доменные исключения.
"""

from typing import Type
import asyncpg
import redis.exceptions
import litellm.exceptions
from src.shared.errors.base import AppException
from src.shared.errors.domain_errors import (
    ConflictError,
    ServiceUnavailableError,
    RateLimitError,
    BadRequestError,
    InternalServerError,
    UnauthorizedError,
    TimeoutError,
)
from src.shared.errors.llm_errors import (
    ModelNotFoundError,
    ProviderUnavailableError,
    TokenLimitExceededError,
    GenerationFailedError,
    ProviderAuthenticationError,
    ContextLengthExceededError,
)


class ExceptionMapper:
    """Маппер для преобразования инфраструктурных исключений в доменные.

    Преобразует исключения от внешних библиотек (asyncpg, redis, litellm)
    в доменные исключения приложения.

    Examples:
        >>> mapper = ExceptionMapper()
        >>> try:
        ...     # Операция с БД
        ...     pass
        ... except Exception as e:
        ...     domain_error = mapper.map(e)
        ...     raise domain_error
    """

    # Маппинг PostgreSQL ошибок
    _POSTGRES_MAPPING: dict[Type[Exception], Type[AppException]] = {
        asyncpg.UniqueViolationError: ConflictError,
        asyncpg.ForeignKeyViolationError: ConflictError,
        asyncpg.IntegrityConstraintViolationError: ConflictError,
        asyncpg.PostgresConnectionError: ServiceUnavailableError,
        asyncpg.TooManyConnectionsError: ServiceUnavailableError,
        asyncpg.InvalidSQLStatementNameError: BadRequestError,
        asyncpg.UndefinedTableError: BadRequestError,
        asyncpg.PostgresError: ServiceUnavailableError,
    }

    # Маппинг Redis ошибок
    _REDIS_MAPPING: dict[Type[Exception], Type[AppException]] = {
        redis.exceptions.ConnectionError: ServiceUnavailableError,
        redis.exceptions.TimeoutError: TimeoutError,
        redis.exceptions.RedisError: ServiceUnavailableError,
    }

    # Маппинг LiteLLM ошибок
    _LITELLM_MAPPING: dict[Type[Exception], Type[AppException]] = {
        litellm.exceptions.NotFoundError: ModelNotFoundError,
        litellm.exceptions.AuthenticationError: ProviderAuthenticationError,
        litellm.exceptions.RateLimitError: RateLimitError,
        litellm.exceptions.ServiceUnavailableError: ProviderUnavailableError,
        litellm.exceptions.Timeout: TimeoutError,
        litellm.exceptions.ContextWindowExceededError: ContextLengthExceededError,
        litellm.exceptions.BadRequestError: BadRequestError,
        litellm.exceptions.APIError: GenerationFailedError,
    }

    def __init__(self) -> None:
        """Инициализация маппера."""
        self._mapping: dict[Type[Exception], Type[AppException]] = {
            **self._POSTGRES_MAPPING,
            **self._REDIS_MAPPING,
            **self._LITELLM_MAPPING,
        }

    def map(self, exception: Exception) -> AppException:
        """Преобразует исключение в доменное.

        Args:
            exception: Исходное исключение.

        Returns:
            AppException: Доменное исключение.

        Examples:
            >>> mapper = ExceptionMapper()
            >>> db_error = asyncpg.UniqueViolationError("duplicate key")
            >>> domain_error = mapper.map(db_error)
            >>> isinstance(domain_error, ConflictError)
            True
        """
        # Если уже доменное исключение, возвращаем как есть
        if isinstance(exception, AppException):
            return exception

        # Ищем подходящий маппинг
        for exc_type, domain_exc_type in self._mapping.items():
            if isinstance(exception, exc_type):
                return self._create_domain_exception(
                    domain_exc_type,
                    exception,
                )

        # Если маппинг не найден, оборачиваем в InternalServerError
        return InternalServerError(
            message=str(exception),
            details={
                "original_exception": exception.__class__.__name__,
                "original_message": str(exception),
            },
        )

    def _create_domain_exception(
        self,
        domain_exc_type: Type[AppException],
        original_exc: Exception,
    ) -> AppException:
        """Создает доменное исключение из исходного.

        Args:
            domain_exc_type: Тип доменного исключения.
            original_exc: Исходное исключение.

        Returns:
            AppException: Экземпляр доменного исключения.
        """
        message = str(original_exc)
        details = {
            "original_exception": original_exc.__class__.__name__,
        }

        # Для LiteLLM исключений извлекаем дополнительную информацию
        if isinstance(original_exc, litellm.exceptions.APIError):
            if hasattr(original_exc, "model"):
                details["model_name"] = original_exc.model
            if hasattr(original_exc, "llm_provider"):
                details["provider"] = original_exc.llm_provider

        # Для PostgreSQL исключений извлекаем детали
        if isinstance(original_exc, asyncpg.PostgresError):
            if hasattr(original_exc, "detail"):
                details["db_detail"] = original_exc.detail
            if hasattr(original_exc, "constraint_name"):
                details["constraint"] = original_exc.constraint_name

        return domain_exc_type(message=message, details=details)

    def register(
        self,
        exception_type: Type[Exception],
        domain_exception_type: Type[AppException],
    ) -> None:
        """Регистрирует новый маппинг исключения.

        Args:
            exception_type: Тип исключения для маппинга.
            domain_exception_type: Тип доменного исключения.

        Examples:
            >>> mapper = ExceptionMapper()
            >>> class CustomError(Exception):
            ...     pass
            >>> class CustomDomainError(AppException):
            ...     status_code = 400
            >>> mapper.register(CustomError, CustomDomainError)
        """
        self._mapping[exception_type] = domain_exception_type


# Глобальный экземпляр маппера
exception_mapper = ExceptionMapper()


def map_exception(exception: Exception) -> AppException:
    """Утилита для быстрого маппинга исключений.

    Args:
        exception: Исходное исключение.

    Returns:
        AppException: Доменное исключение.

    Examples:
        >>> try:
        ...     # Операция с БД
        ...     pass
        ... except Exception as e:
        ...     raise map_exception(e)
    """
    return exception_mapper.map(exception)
