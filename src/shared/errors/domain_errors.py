"""Стандартные доменные исключения приложения.

Этот модуль содержит набор часто используемых доменных исключений,
соответствующих распространенным HTTP статус-кодам.
"""

from src.shared.errors.base import AppException


class ValidationError(AppException):
    """Ошибка валидации входных данных."""

    status_code = 422


class NotFoundError(AppException):
    """Запрашиваемый ресурс не найден."""

    status_code = 404


class ConflictError(AppException):
    """Конфликт с текущим состоянием ресурса."""

    status_code = 409


class ServiceUnavailableError(AppException):
    """Сервис временно недоступен."""

    status_code = 503


class RateLimitError(AppException):
    """Превышен лимит запросов."""

    status_code = 429


class UnauthorizedError(AppException):
    """Требуется аутентификация."""

    status_code = 401


class ForbiddenError(AppException):
    """Доступ запрещен."""

    status_code = 403


class BadRequestError(AppException):
    """Некорректный запрос."""

    status_code = 400


class InternalServerError(AppException):
    """Внутренняя ошибка сервера."""

    status_code = 500


class NotImplementedError(AppException):
    """Функциональность не реализована."""

    status_code = 501


class TimeoutError(AppException):
    """Превышено время ожидания операции."""

    status_code = 504
