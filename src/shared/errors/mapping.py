"""Маппинг инфраструктурных исключений на доменные.

Этот модуль содержит `ExceptionMapper` для преобразования исключений
инфраструктурного слоя (кэш, внешние API) в доменные исключения.
"""


import litellm.exceptions
import redis.exceptions

from src.shared.errors.base import AppException
from src.shared.errors.domain_errors import (
    BadRequestError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    TimeoutError,
)
from src.shared.errors.llm_errors import (
    ContextLengthExceededError,
    GenerationFailedError,
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderUnavailableError,
)


class ExceptionMapper:
    """Маппер для преобразования инфраструктурных исключений в доменные.

    Преобразует исключения от внешних библиотек (redis, litellm)
    в доменные исключения приложения.

    Examples:
        >>> mapper = ExceptionMapper()
        >>> try:
        ...     # Операция с кэшем или LLM
        ...     pass
        ... except Exception as e:
        ...     domain_error = mapper.map(e)
        ...     raise domain_error

    """

    _REDIS_MAPPING: dict[type[Exception], type[AppException]] = {
        redis.exceptions.ConnectionError: ServiceUnavailableError,
        redis.exceptions.TimeoutError: TimeoutError,
        redis.exceptions.RedisError: ServiceUnavailableError,
    }

    _LITELLM_MAPPING: dict[type[Exception], type[AppException]] = {
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
        self._mapping: dict[type[Exception], type[AppException]] = {
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
            >>> redis_error = redis.exceptions.ConnectionError("connection failed")
            >>> domain_error = mapper.map(redis_error)
            >>> isinstance(domain_error, ServiceUnavailableError)
            True

        """
        if isinstance(exception, AppException):
            return exception

        for exc_type, domain_exc_type in self._mapping.items():
            if isinstance(exception, exc_type):
                return self._create_domain_exception(
                    domain_exc_type,
                    exception,
                )

        return InternalServerError(
            message=str(exception),
            details={
                "original_exception": exception.__class__.__name__,
                "original_message": str(exception),
            },
        )

    def _create_domain_exception(
        self,
        domain_exc_type: type[AppException],
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

        if isinstance(original_exc, litellm.exceptions.APIError):
            if hasattr(original_exc, "model"):
                details["model_name"] = original_exc.model
            if hasattr(original_exc, "llm_provider"):
                details["provider"] = original_exc.llm_provider

        return domain_exc_type(message=message, details=details)

    def register(
        self,
        exception_type: type[Exception],
        domain_exception_type: type[AppException],
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
        ...     # Операция с кэшем или LLM
        ...     pass
        ... except Exception as e:
        ...     raise map_exception(e)

    """
    return exception_mapper.map(exception)
