"""Domain errors.

Доменные исключения приложения.
"""

from src.shared.errors.base import AppException


class NotFoundError(AppException):
    """Ресурс не найден."""

    status_code = 404
    code = "NOT_FOUND"


class ValidationError(AppException):
    """Ошибка валидации данных."""

    status_code = 422
    code = "VALIDATION_ERROR"


class ConflictError(AppException):
    """Конфликт данных."""

    status_code = 409
    code = "CONFLICT"


class ServiceUnavailableError(AppException):
    """Сервис недоступен."""

    status_code = 503
    code = "SERVICE_UNAVAILABLE"


class ModelNotLoadedError(ServiceUnavailableError):
    """Модель не загружена."""

    code = "MODEL_NOT_LOADED"

    def __init__(self, model_name: str) -> None:
        """Инициализация исключения.

        Args:
            model_name: Название модели.

        """
        super().__init__(
            message=f"Модель '{model_name}' не загружена",
            details={"model": model_name},
        )


class ProviderUnavailableError(ServiceUnavailableError):
    """Провайдер недоступен."""

    code = "PROVIDER_UNAVAILABLE"

    def __init__(self, provider_name: str, reason: str | None = None) -> None:
        """Инициализация исключения.

        Args:
            provider_name: Название провайдера.
            reason: Причина недоступности.

        """
        message = f"Провайдер '{provider_name}' недоступен"
        if reason:
            message += f": {reason}"

        super().__init__(
            message=message,
            details={"provider": provider_name, "reason": reason},
        )


class JSONParseError(ValidationError):
    """Ошибка парсинга JSON."""

    code = "JSON_PARSE_ERROR"

    def __init__(self, error: str) -> None:
        """Инициализация исключения.

        Args:
            error: Описание ошибки парсинга.

        """
        super().__init__(
            message=f"Не удалось распарсить JSON: {error}",
            details={"parse_error": error},
        )


class JSONFixFailedError(ValidationError):
    """Не удалось исправить JSON."""

    code = "JSON_FIX_FAILED"

    def __init__(self, attempts: int, original_error: str) -> None:
        """Инициализация исключения.

        Args:
            attempts: Количество попыток исправления.
            original_error: Исходная ошибка.

        """
        super().__init__(
            message=f"Не удалось исправить JSON после {attempts} попыток",
            details={"attempts": attempts, "original_error": original_error},
        )


class MemoryExceededError(ServiceUnavailableError):
    """Превышен лимит памяти."""

    code = "MEMORY_EXCEEDED"

    def __init__(self, current: float, threshold: float) -> None:
        """Инициализация исключения.

        Args:
            current: Текущее использование памяти в процентах.
            threshold: Порог использования памяти в процентах.

        """
        super().__init__(
            message=f"Превышен лимит памяти: {current:.1f}% (порог: {threshold:.1f}%)",
            details={"current": current, "threshold": threshold},
        )


class TaskNotFoundError(NotFoundError):
    """Задача не найдена."""

    code = "TASK_NOT_FOUND"

    def __init__(self, task_id: str) -> None:
        """Инициализация исключения.

        Args:
            task_id: Идентификатор задачи.

        """
        super().__init__(
            message=f"Задача с ID '{task_id}' не найдена",
            details={"task_id": task_id},
        )
