"""Тесты для LLM-специфичных исключений.

Покрывает:
- ModelNotFoundError с автоматическим формированием сообщения
- ProviderUnavailableError с информацией о провайдере
- TokenLimitExceededError с лимитами токенов
- GenerationFailedError с причиной ошибки
- InvalidModelConfigError с описанием ошибки конфигурации
- ProviderAuthenticationError
- ContextLengthExceededError
"""

import pytest

from src.shared.errors.llm_errors import (
    ContextLengthExceededError,
    GenerationFailedError,
    InvalidModelConfigError,
    ModelNotFoundError,
    ProviderAuthenticationError,
    ProviderUnavailableError,
    TokenLimitExceededError,
)


class TestModelNotFoundError:
    """Тесты для ModelNotFoundError."""

    def test_status_code(self):
        """Проверяет что status_code = 404."""
        error = ModelNotFoundError()
        assert error.status_code == 404

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ModelNotFoundError()
        assert error.code == "model_not_found_error"

    def test_without_model_name(self):
        """Проверяет создание ошибки без model_name."""
        error = ModelNotFoundError()
        assert error.details == {}

    def test_with_model_name(self):
        """Проверяет создание ошибки с model_name."""
        error = ModelNotFoundError(model_name="llama-7b")
        assert error.details["model_name"] == "llama-7b"
        assert "llama-7b" in error.message

    def test_auto_message_generation(self):
        """Проверяет автоматическую генерацию сообщения."""
        error = ModelNotFoundError(model_name="gpt-4")
        assert "gpt-4" in error.message
        assert "не найдена" in error.message.lower()

    def test_custom_message_overrides_auto(self):
        """Проверяет что кастомное сообщение переопределяет автогенерацию."""
        error = ModelNotFoundError(model_name="llama-7b", message="Custom error message")
        assert error.message == "Custom error message"
        assert error.details["model_name"] == "llama-7b"

    def test_with_additional_details(self):
        """Проверяет дополнительные details."""
        error = ModelNotFoundError(
            model_name="llama-7b", details={"provider": "local", "registry": "main"}
        )
        assert error.details["model_name"] == "llama-7b"
        assert error.details["provider"] == "local"
        assert error.details["registry"] == "main"


class TestProviderUnavailableError:
    """Тесты для ProviderUnavailableError."""

    def test_status_code(self):
        """Проверяет что status_code = 503."""
        error = ProviderUnavailableError()
        assert error.status_code == 503

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ProviderUnavailableError()
        assert error.code == "provider_unavailable_error"

    def test_without_provider_name(self):
        """Проверяет создание ошибки без provider_name."""
        error = ProviderUnavailableError()
        assert error.details == {}

    def test_with_provider_name(self):
        """Проверяет создание ошибки с provider_name."""
        error = ProviderUnavailableError(provider_name="anthropic")
        assert error.details["provider"] == "anthropic"
        assert "anthropic" in error.message

    def test_auto_message_generation(self):
        """Проверяет автоматическую генерацию сообщения."""
        error = ProviderUnavailableError(provider_name="openai")
        assert "openai" in error.message.lower()
        assert "недоступен" in error.message.lower()

    def test_custom_message(self):
        """Проверяет кастомное сообщение."""
        error = ProviderUnavailableError(
            provider_name="anthropic", message="API is down for maintenance"
        )
        assert error.message == "API is down for maintenance"
        assert error.details["provider"] == "anthropic"


class TestTokenLimitExceededError:
    """Тесты для TokenLimitExceededError."""

    def test_status_code(self):
        """Проверяет что status_code = 422."""
        error = TokenLimitExceededError()
        assert error.status_code == 422

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = TokenLimitExceededError()
        assert error.code == "token_limit_exceeded_error"

    def test_without_tokens(self):
        """Проверяет создание ошибки без информации о токенах."""
        error = TokenLimitExceededError()
        assert error.details == {}

    def test_with_tokens_used(self):
        """Проверяет передачу tokens_used."""
        error = TokenLimitExceededError(tokens_used=5000)
        assert error.details["tokens_used"] == 5000

    def test_with_tokens_limit(self):
        """Проверяет передачу tokens_limit."""
        error = TokenLimitExceededError(tokens_limit=4096)
        assert error.details["tokens_limit"] == 4096

    def test_with_both_tokens(self):
        """Проверяет передачу обоих параметров токенов."""
        error = TokenLimitExceededError(tokens_used=5000, tokens_limit=4096)
        assert error.details["tokens_used"] == 5000
        assert error.details["tokens_limit"] == 4096

    def test_auto_message_generation(self):
        """Проверяет автоматическую генерацию сообщения."""
        error = TokenLimitExceededError(tokens_used=5000, tokens_limit=4096)
        assert "5000" in error.message
        assert "4096" in error.message
        assert "превышен" in error.message.lower()

    def test_custom_message(self):
        """Проверяет кастомное сообщение."""
        error = TokenLimitExceededError(
            tokens_used=5000, tokens_limit=4096, message="Token quota exceeded"
        )
        assert error.message == "Token quota exceeded"


class TestGenerationFailedError:
    """Тесты для GenerationFailedError."""

    def test_status_code(self):
        """Проверяет что status_code = 500."""
        error = GenerationFailedError()
        assert error.status_code == 500

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = GenerationFailedError()
        assert error.code == "generation_failed_error"

    def test_without_params(self):
        """Проверяет создание ошибки без параметров."""
        error = GenerationFailedError()
        assert error.details == {}
        assert "ошибка" in error.message.lower()

    def test_with_model_name(self):
        """Проверяет передачу model_name."""
        error = GenerationFailedError(model_name="claude-3")
        assert error.details["model_name"] == "claude-3"
        assert "claude-3" in error.message

    def test_with_reason(self):
        """Проверяет передачу reason."""
        error = GenerationFailedError(reason="timeout")
        assert error.details["reason"] == "timeout"

    def test_with_model_and_reason(self):
        """Проверяет передачу model_name и reason."""
        error = GenerationFailedError(model_name="gpt-4", reason="rate limit")
        assert error.details["model_name"] == "gpt-4"
        assert error.details["reason"] == "rate limit"
        assert "gpt-4" in error.message
        assert "rate limit" in error.message

    def test_auto_message_with_model_only(self):
        """Проверяет автогенерацию сообщения только с model_name."""
        error = GenerationFailedError(model_name="claude-3")
        assert "claude-3" in error.message
        assert "ошибка генерации" in error.message.lower()

    def test_custom_message(self):
        """Проверяет кастомное сообщение."""
        error = GenerationFailedError(
            model_name="gpt-4", reason="timeout", message="Generation timeout"
        )
        assert error.message == "Generation timeout"


class TestInvalidModelConfigError:
    """Тесты для InvalidModelConfigError."""

    def test_status_code(self):
        """Проверяет что status_code = 422."""
        error = InvalidModelConfigError()
        assert error.status_code == 422

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = InvalidModelConfigError()
        assert error.code == "invalid_model_config_error"

    def test_without_params(self):
        """Проверяет создание ошибки без параметров."""
        error = InvalidModelConfigError()
        assert error.details == {}

    def test_with_model_name(self):
        """Проверяет передачу model_name."""
        error = InvalidModelConfigError(model_name="llama-7b")
        assert error.details["model_name"] == "llama-7b"
        assert "llama-7b" in error.message

    def test_with_config_error(self):
        """Проверяет передачу config_error."""
        error = InvalidModelConfigError(config_error="missing temperature parameter")
        assert error.details["config_error"] == "missing temperature parameter"

    def test_with_both_params(self):
        """Проверяет передачу обоих параметров."""
        error = InvalidModelConfigError(model_name="gpt-4", config_error="invalid max_tokens")
        assert error.details["model_name"] == "gpt-4"
        assert error.details["config_error"] == "invalid max_tokens"

    def test_auto_message_generation(self):
        """Проверяет автогенерацию сообщения."""
        error = InvalidModelConfigError(model_name="claude-3")
        assert "claude-3" in error.message
        assert "конфигурац" in error.message.lower()


class TestProviderAuthenticationError:
    """Тесты для ProviderAuthenticationError."""

    def test_status_code(self):
        """Проверяет что status_code = 401."""
        error = ProviderAuthenticationError()
        assert error.status_code == 401

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ProviderAuthenticationError()
        assert error.code == "provider_authentication_error"

    def test_without_provider_name(self):
        """Проверяет создание ошибки без provider_name."""
        error = ProviderAuthenticationError()
        assert error.details == {}

    def test_with_provider_name(self):
        """Проверяет передачу provider_name."""
        error = ProviderAuthenticationError(provider_name="anthropic")
        assert error.details["provider"] == "anthropic"
        assert "anthropic" in error.message

    def test_auto_message_generation(self):
        """Проверяет автогенерацию сообщения."""
        error = ProviderAuthenticationError(provider_name="openai")
        assert "openai" in error.message.lower()
        assert "аутентификац" in error.message.lower()


class TestContextLengthExceededError:
    """Тесты для ContextLengthExceededError."""

    def test_status_code(self):
        """Проверяет что status_code = 422."""
        error = ContextLengthExceededError()
        assert error.status_code == 422

    def test_error_code(self):
        """Проверяет автогенерацию error_code."""
        error = ContextLengthExceededError()
        assert error.code == "context_length_exceeded_error"

    def test_without_params(self):
        """Проверяет создание ошибки без параметров."""
        error = ContextLengthExceededError()
        assert error.details == {}

    def test_with_context_length(self):
        """Проверяет передачу context_length."""
        error = ContextLengthExceededError(context_length=10000)
        assert error.details["context_length"] == 10000

    def test_with_max_context(self):
        """Проверяет передачу max_context."""
        error = ContextLengthExceededError(max_context=8192)
        assert error.details["max_context"] == 8192

    def test_with_both_params(self):
        """Проверяет передачу обоих параметров."""
        error = ContextLengthExceededError(context_length=10000, max_context=8192)
        assert error.details["context_length"] == 10000
        assert error.details["max_context"] == 8192

    def test_auto_message_generation(self):
        """Проверяет автогенерацию сообщения."""
        error = ContextLengthExceededError(context_length=10000, max_context=8192)
        assert "10000" in error.message
        assert "8192" in error.message
        assert "превышен" in error.message.lower()

    def test_custom_message(self):
        """Проверяет кастомное сообщение."""
        error = ContextLengthExceededError(
            context_length=10000, max_context=8192, message="Context window too large"
        )
        assert error.message == "Context window too large"


class TestLLMErrorsInheritance:
    """Тесты наследования и общих характеристик LLM ошибок."""

    def test_all_errors_can_be_raised(self):
        """Проверяет что все LLM ошибки можно поднять."""
        errors = [
            ModelNotFoundError,
            ProviderUnavailableError,
            TokenLimitExceededError,
            GenerationFailedError,
            InvalidModelConfigError,
            ProviderAuthenticationError,
            ContextLengthExceededError,
        ]

        for error_class in errors:
            with pytest.raises(error_class):
                raise error_class(message="Test error")

    def test_all_errors_to_response(self):
        """Проверяет что все LLM ошибки преобразуются в ErrorResponse."""
        errors = [
            ModelNotFoundError(model_name="test"),
            ProviderUnavailableError(provider_name="test"),
            TokenLimitExceededError(tokens_used=100, tokens_limit=50),
            GenerationFailedError(model_name="test", reason="error"),
            InvalidModelConfigError(model_name="test"),
            ProviderAuthenticationError(provider_name="test"),
            ContextLengthExceededError(context_length=100, max_context=50),
        ]

        for error in errors:
            response = error.to_response()
            assert response.error_code is not None
            assert response.message is not None
            assert isinstance(response.error_code, str)
            assert isinstance(response.message, str)
