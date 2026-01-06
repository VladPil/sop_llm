"""Тесты для базового класса исключений AppException.

Покрывает:
- Автоматическую генерацию error_code из имени класса
- Извлечение сообщения из docstring
- Преобразование в ErrorResponse
- Работу с details
"""

import pytest

from src.shared.errors.base import AppException, ErrorResponse


class TestAppException:
    """Тесты для базового класса AppException."""

    def test_error_code_generation_simple(self):
        """Тестирует генерацию error_code из простого имени класса."""

        class SimpleError(AppException):
            """Простая ошибка."""

        error = SimpleError()
        assert error.code == "simple_error"

    def test_error_code_generation_complex(self):
        """Тестирует генерацию error_code из сложного CamelCase имени."""

        class VeryComplexCustomError(AppException):
            """Очень сложная кастомная ошибка."""

        error = VeryComplexCustomError()
        assert error.code == "very_complex_custom_error"

    def test_error_code_generation_single_word(self):
        """Тестирует генерацию error_code из одного слова."""

        class Error(AppException):
            """Ошибка."""

        error = Error()
        assert error.code == "error"

    def test_default_message_from_docstring(self):
        """Тестирует извлечение сообщения из docstring."""

        class CustomError(AppException):
            """Произошла кастомная ошибка."""

        error = CustomError()
        assert error.message == "Произошла кастомная ошибка."

    def test_default_message_from_multiline_docstring(self):
        """Тестирует извлечение первой строки из многострочного docstring."""

        class CustomError(AppException):
            """Произошла кастомная ошибка.

            Это дополнительное описание ошибки.
            Оно должно быть проигнорировано.
            """

        error = CustomError()
        assert error.message == "Произошла кастомная ошибка."

    def test_default_message_no_docstring(self):
        """Тестирует fallback на имя класса если нет docstring."""

        class CustomError(AppException):
            pass

        error = CustomError()
        assert error.message == "CustomError"

    def test_custom_message_overrides_docstring(self):
        """Тестирует что кастомное сообщение переопределяет docstring."""

        class CustomError(AppException):
            """Сообщение из docstring."""

        error = CustomError(message="Кастомное сообщение")
        assert error.message == "Кастомное сообщение"

    def test_details_empty_by_default(self):
        """Тестирует что details пустой словарь по умолчанию."""

        class CustomError(AppException):
            """Ошибка."""

        error = CustomError()
        assert error.details == {}

    def test_details_from_constructor(self):
        """Тестирует передачу details через конструктор."""

        class CustomError(AppException):
            """Ошибка."""

        details = {"field": "value", "count": 42}
        error = CustomError(details=details)
        assert error.details == details

    def test_status_code_default(self):
        """Тестирует дефолтный status_code = 500."""

        class CustomError(AppException):
            """Ошибка."""

        error = CustomError()
        assert error.status_code == 500

    def test_status_code_custom(self):
        """Тестирует кастомный status_code."""

        class CustomError(AppException):
            """Ошибка."""

            status_code = 400

        error = CustomError()
        assert error.status_code == 400

    def test_to_response_basic(self):
        """Тестирует преобразование в ErrorResponse."""

        class CustomError(AppException):
            """Произошла ошибка."""

            status_code = 400

        error = CustomError()
        response = error.to_response()

        assert isinstance(response, ErrorResponse)
        assert response.error_code == "custom_error"
        assert response.message == "Произошла ошибка."
        assert response.details is None

    def test_to_response_with_details(self):
        """Тестирует преобразование в ErrorResponse с details."""

        class CustomError(AppException):
            """Произошла ошибка."""

        error = CustomError(details={"field": "value"})
        response = error.to_response()

        assert response.details == {"field": "value"}

    def test_to_response_with_custom_message(self):
        """Тестирует ErrorResponse с кастомным сообщением."""

        class CustomError(AppException):
            """Docstring message."""

        error = CustomError(message="Custom message")
        response = error.to_response()

        assert response.message == "Custom message"

    def test_repr(self):
        """Тестирует строковое представление исключения."""

        class CustomError(AppException):
            """Ошибка."""

        error = CustomError(message="Test error")
        repr_str = repr(error)

        assert "CustomError" in repr_str
        assert "custom_error" in repr_str
        assert "Test error" in repr_str

    def test_str_returns_message(self):
        """Тестирует что str() возвращает сообщение."""

        class CustomError(AppException):
            """Ошибка."""

        error = CustomError(message="Test error message")
        assert str(error) == "Test error message"

    def test_exception_can_be_raised(self):
        """Тестирует что исключение можно поднять и поймать."""

        class CustomError(AppException):
            """Ошибка."""

        with pytest.raises(CustomError) as exc_info:
            raise CustomError(message="Test error")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.code == "custom_error"

    def test_inheritance_chain(self):
        """Тестирует что AppException наследуется от Exception."""

        class CustomError(AppException):
            """Ошибка."""

        error = CustomError()
        assert isinstance(error, Exception)
        assert isinstance(error, AppException)


class TestErrorResponse:
    """Тесты для схемы ErrorResponse."""

    def test_error_response_creation(self):
        """Тестирует создание ErrorResponse."""
        response = ErrorResponse(
            error_code="test_error", message="Test message", details={"key": "value"}
        )

        assert response.error_code == "test_error"
        assert response.message == "Test message"
        assert response.details == {"key": "value"}

    def test_error_response_without_details(self):
        """Тестирует создание ErrorResponse без details."""
        response = ErrorResponse(error_code="test_error", message="Test message")

        assert response.error_code == "test_error"
        assert response.message == "Test message"
        assert response.details is None

    def test_error_response_serialization(self):
        """Тестирует JSON сериализацию ErrorResponse."""
        response = ErrorResponse(
            error_code="test_error", message="Test message", details={"key": "value"}
        )

        data = response.model_dump()
        assert data["error_code"] == "test_error"
        assert data["message"] == "Test message"
        assert data["details"] == {"key": "value"}

    def test_error_response_json_schema(self):
        """Тестирует JSON схему ErrorResponse."""
        schema = ErrorResponse.model_json_schema()

        assert "error_code" in schema["properties"]
        assert "message" in schema["properties"]
        assert "details" in schema["properties"]
        assert "error_code" in schema["required"]
        assert "message" in schema["required"]
