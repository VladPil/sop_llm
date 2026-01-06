"""Тесты для стандартных доменных исключений.

Покрывает:
- Все стандартные доменные исключения
- Правильные HTTP status codes
- Автоматическую генерацию error_code
- Извлечение сообщений из docstring
"""

import pytest

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


class TestValidationError:
    """Тесты для ValidationError."""

    def test_status_code(self):
        """Проверяет что status_code = 422."""
        error = ValidationError()
        assert error.status_code == 422

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ValidationError()
        assert error.code == "validation_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = ValidationError()
        assert "валидации" in error.message.lower()

    def test_custom_message(self):
        """Проверяет кастомное сообщение."""
        error = ValidationError(message="Invalid field: email")
        assert error.message == "Invalid field: email"

    def test_with_details(self):
        """Проверяет передачу details."""
        details = {"field": "email", "error": "invalid format"}
        error = ValidationError(details=details)
        assert error.details == details


class TestNotFoundError:
    """Тесты для NotFoundError."""

    def test_status_code(self):
        """Проверяет что status_code = 404."""
        error = NotFoundError()
        assert error.status_code == 404

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = NotFoundError()
        assert error.code == "not_found_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = NotFoundError()
        assert "не найден" in error.message.lower()


class TestConflictError:
    """Тесты для ConflictError."""

    def test_status_code(self):
        """Проверяет что status_code = 409."""
        error = ConflictError()
        assert error.status_code == 409

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ConflictError()
        assert error.code == "conflict_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = ConflictError()
        assert "конфликт" in error.message.lower()


class TestServiceUnavailableError:
    """Тесты для ServiceUnavailableError."""

    def test_status_code(self):
        """Проверяет что status_code = 503."""
        error = ServiceUnavailableError()
        assert error.status_code == 503

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ServiceUnavailableError()
        assert error.code == "service_unavailable_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = ServiceUnavailableError()
        assert "недоступ" in error.message.lower()


class TestRateLimitError:
    """Тесты для RateLimitError."""

    def test_status_code(self):
        """Проверяет что status_code = 429."""
        error = RateLimitError()
        assert error.status_code == 429

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = RateLimitError()
        assert error.code == "rate_limit_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = RateLimitError()
        assert "лимит" in error.message.lower()


class TestUnauthorizedError:
    """Тесты для UnauthorizedError."""

    def test_status_code(self):
        """Проверяет что status_code = 401."""
        error = UnauthorizedError()
        assert error.status_code == 401

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = UnauthorizedError()
        assert error.code == "unauthorized_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = UnauthorizedError()
        assert "аутентификац" in error.message.lower()


class TestForbiddenError:
    """Тесты для ForbiddenError."""

    def test_status_code(self):
        """Проверяет что status_code = 403."""
        error = ForbiddenError()
        assert error.status_code == 403

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ForbiddenError()
        assert error.code == "forbidden_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = ForbiddenError()
        assert "запрещен" in error.message.lower()


class TestBadRequestError:
    """Тесты для BadRequestError."""

    def test_status_code(self):
        """Проверяет что status_code = 400."""
        error = BadRequestError()
        assert error.status_code == 400

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = BadRequestError()
        assert error.code == "bad_request_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = BadRequestError()
        assert "некорректн" in error.message.lower()


class TestInternalServerError:
    """Тесты для InternalServerError."""

    def test_status_code(self):
        """Проверяет что status_code = 500."""
        error = InternalServerError()
        assert error.status_code == 500

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = InternalServerError()
        assert error.code == "internal_server_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = InternalServerError()
        assert "внутренн" in error.message.lower()


class TestNotImplementedError:
    """Тесты для NotImplementedError."""

    def test_status_code(self):
        """Проверяет что status_code = 501."""
        error = NotImplementedError()
        assert error.status_code == 501

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = NotImplementedError()
        assert error.code == "not_implemented_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = NotImplementedError()
        assert "не реализован" in error.message.lower()


class TestTimeoutError:
    """Тесты для TimeoutError."""

    def test_status_code(self):
        """Проверяет что status_code = 504."""
        error = TimeoutError()
        assert error.status_code == 504

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = TimeoutError()
        assert error.code == "timeout_error"

    def test_default_message(self):
        """Проверяет извлечение сообщения из docstring."""
        error = TimeoutError()
        assert "время" in error.message.lower()


class TestDomainErrorsInheritance:
    """Тесты наследования и общих характеристик доменных ошибок."""

    def test_all_errors_have_unique_status_codes(self):
        """Проверяет что каждая ошибка имеет соответствующий HTTP статус код."""
        error_status_map = {
            ValidationError: 422,
            NotFoundError: 404,
            ConflictError: 409,
            ServiceUnavailableError: 503,
            RateLimitError: 429,
            UnauthorizedError: 401,
            ForbiddenError: 403,
            BadRequestError: 400,
            InternalServerError: 500,
            NotImplementedError: 501,
            TimeoutError: 504,
        }

        for error_class, expected_status in error_status_map.items():
            error = error_class()
            assert (
                error.status_code == expected_status
            ), f"{error_class.__name__} has wrong status_code"

    def test_all_errors_can_be_raised_and_caught(self):
        """Проверяет что все ошибки можно поднять и поймать."""
        errors = [
            ValidationError,
            NotFoundError,
            ConflictError,
            ServiceUnavailableError,
            RateLimitError,
            UnauthorizedError,
            ForbiddenError,
            BadRequestError,
            InternalServerError,
            NotImplementedError,
            TimeoutError,
        ]

        for error_class in errors:
            with pytest.raises(error_class):
                raise error_class(message="Test error")

    def test_all_errors_to_response(self):
        """Проверяет что все ошибки могут быть преобразованы в ErrorResponse."""
        errors = [
            ValidationError(),
            NotFoundError(),
            ConflictError(),
            ServiceUnavailableError(),
            RateLimitError(),
            UnauthorizedError(),
            ForbiddenError(),
            BadRequestError(),
            InternalServerError(),
            NotImplementedError(),
            TimeoutError(),
        ]

        for error in errors:
            response = error.to_response()
            assert response.error_code is not None
            assert response.message is not None
            assert isinstance(response.error_code, str)
            assert isinstance(response.message, str)
