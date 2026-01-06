"""LLM-специфичные исключения.

Этот модуль содержит исключения, специфичные для работы с LLM моделями,
провайдерами и процессом генерации.
"""

from typing import Any
from src.shared.errors.base import AppException


class ModelNotFoundError(AppException):
    """Модель не найдена в реестре моделей."""

    status_code = 404

    def __init__(
        self,
        model_name: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация ошибки.

        Args:
            model_name: Название модели, которая не найдена.
            message: Описание ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if model_name:
            details["model_name"] = model_name
            if not message:
                message = f"Модель '{model_name}' не найдена в реестре"
        super().__init__(message=message, details=details)


class ProviderUnavailableError(AppException):
    """Провайдер LLM недоступен."""

    status_code = 503

    def __init__(
        self,
        provider_name: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация ошибки.

        Args:
            provider_name: Название провайдера.
            message: Описание ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if provider_name:
            details["provider"] = provider_name
            if not message:
                message = f"Провайдер '{provider_name}' недоступен"
        super().__init__(message=message, details=details)


class TokenLimitExceededError(AppException):
    """Превышен лимит токенов для модели."""

    status_code = 422

    def __init__(
        self,
        tokens_used: int | None = None,
        tokens_limit: int | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация ошибки.

        Args:
            tokens_used: Количество использованных токенов.
            tokens_limit: Максимальный лимит токенов.
            message: Описание ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if tokens_used is not None:
            details["tokens_used"] = tokens_used
        if tokens_limit is not None:
            details["tokens_limit"] = tokens_limit

        if not message and tokens_used and tokens_limit:
            message = f"Превышен лимит токенов: {tokens_used}/{tokens_limit}"

        super().__init__(message=message, details=details)


class GenerationFailedError(AppException):
    """Ошибка при генерации ответа моделью."""

    status_code = 500

    def __init__(
        self,
        model_name: str | None = None,
        reason: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация ошибки.

        Args:
            model_name: Название модели.
            reason: Причина ошибки генерации.
            message: Описание ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if model_name:
            details["model_name"] = model_name
        if reason:
            details["reason"] = reason

        if not message:
            if model_name and reason:
                message = f"Ошибка генерации модели '{model_name}': {reason}"
            elif model_name:
                message = f"Ошибка генерации модели '{model_name}'"
            else:
                message = "Ошибка при генерации ответа"

        super().__init__(message=message, details=details)


class InvalidModelConfigError(AppException):
    """Некорректная конфигурация модели."""

    status_code = 422

    def __init__(
        self,
        model_name: str | None = None,
        config_error: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация ошибки.

        Args:
            model_name: Название модели.
            config_error: Описание ошибки конфигурации.
            message: Описание ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if model_name:
            details["model_name"] = model_name
        if config_error:
            details["config_error"] = config_error

        if not message and model_name:
            message = f"Некорректная конфигурация модели '{model_name}'"

        super().__init__(message=message, details=details)


class ProviderAuthenticationError(AppException):
    """Ошибка аутентификации с провайдером LLM."""

    status_code = 401

    def __init__(
        self,
        provider_name: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация ошибки.

        Args:
            provider_name: Название провайдера.
            message: Описание ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if provider_name:
            details["provider"] = provider_name
            if not message:
                message = f"Ошибка аутентификации с провайдером '{provider_name}'"
        super().__init__(message=message, details=details)


class ContextLengthExceededError(AppException):
    """Превышена максимальная длина контекста модели."""

    status_code = 422

    def __init__(
        self,
        context_length: int | None = None,
        max_context: int | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Инициализация ошибки.

        Args:
            context_length: Текущая длина контекста.
            max_context: Максимальная длина контекста.
            message: Описание ошибки.
            details: Дополнительная информация.
        """
        details = details or {}
        if context_length is not None:
            details["context_length"] = context_length
        if max_context is not None:
            details["max_context"] = max_context

        if not message and context_length and max_context:
            message = f"Превышена длина контекста: {context_length}/{max_context}"

        super().__init__(message=message, details=details)
