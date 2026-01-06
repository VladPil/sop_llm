"""Тесты для ExceptionMapper - маппинг инфраструктурных исключений в доменные.

Покрывает:
- Маппинг Redis исключений
- Маппинг LiteLLM исключений
- Регистрацию кастомных маппингов
- Обработку неизвестных исключений
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
from src.shared.errors.mapping import ExceptionMapper, map_exception


class TestExceptionMapperRedis:
    """Тесты маппинга Redis исключений."""

    def test_connection_error(self):
        """Тестирует маппинг Redis ConnectionError в ServiceUnavailableError."""
        mapper = ExceptionMapper()
        redis_error = redis.exceptions.ConnectionError("connection refused")

        domain_error = mapper.map(redis_error)

        assert isinstance(domain_error, ServiceUnavailableError)
        assert "connection refused" in domain_error.message
        assert domain_error.details["original_exception"] == "ConnectionError"

    def test_timeout_error(self):
        """Тестирует маппинг Redis TimeoutError в TimeoutError."""
        mapper = ExceptionMapper()
        redis_error = redis.exceptions.TimeoutError("operation timeout")

        domain_error = mapper.map(redis_error)

        assert isinstance(domain_error, TimeoutError)
        assert "operation timeout" in domain_error.message

    def test_generic_redis_error(self):
        """Тестирует маппинг generic RedisError в ServiceUnavailableError."""
        mapper = ExceptionMapper()
        redis_error = redis.exceptions.RedisError("redis error")

        domain_error = mapper.map(redis_error)

        assert isinstance(domain_error, ServiceUnavailableError)


class TestExceptionMapperLiteLLM:
    """Тесты маппинга LiteLLM исключений."""

    def test_not_found_error(self):
        """Тестирует маппинг LiteLLM NotFoundError в ModelNotFoundError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.NotFoundError(
            message="model not found", model="gpt-5", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, ModelNotFoundError)
        assert "model not found" in domain_error.message

    def test_authentication_error(self):
        """Тестирует маппинг AuthenticationError в ProviderAuthenticationError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.AuthenticationError(
            message="invalid api key", model="gpt-4", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, ProviderAuthenticationError)
        assert "invalid api key" in domain_error.message

    def test_rate_limit_error(self):
        """Тестирует маппинг RateLimitError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.RateLimitError(
            message="rate limit exceeded", model="claude-3", llm_provider="anthropic"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, RateLimitError)

    def test_service_unavailable_error(self):
        """Тестирует маппинг ServiceUnavailableError в ProviderUnavailableError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.ServiceUnavailableError(
            message="service down", model="gpt-4", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, ProviderUnavailableError)

    def test_timeout(self):
        """Тестирует маппинг Timeout в TimeoutError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.Timeout(
            message="request timeout", model="gpt-4", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, TimeoutError)

    def test_context_window_exceeded_error(self):
        """Тестирует маппинг ContextWindowExceededError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.ContextWindowExceededError(
            message="context too long", model="gpt-4", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, ContextLengthExceededError)

    def test_bad_request_error(self):
        """Тестирует маппинг BadRequestError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.BadRequestError(
            message="bad request", model="gpt-4", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, BadRequestError)

    def test_api_error(self):
        """Тестирует маппинг generic APIError в GenerationFailedError."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.APIError(
            status_code=500, message="api error", model="gpt-4", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert isinstance(domain_error, GenerationFailedError)


class TestExceptionMapperGeneral:
    """Общие тесты ExceptionMapper."""

    def test_app_exception_passthrough(self):
        """Тестирует что AppException возвращается как есть."""
        mapper = ExceptionMapper()
        app_error = BadRequestError(message="Test error")

        domain_error = mapper.map(app_error)

        assert domain_error is app_error
        assert isinstance(domain_error, BadRequestError)

    def test_unknown_exception_mapped_to_internal_server_error(self):
        """Тестирует что неизвестное исключение мапится в InternalServerError."""
        mapper = ExceptionMapper()
        unknown_error = ValueError("unknown error")

        domain_error = mapper.map(unknown_error)

        assert isinstance(domain_error, InternalServerError)
        assert "unknown error" in domain_error.message
        assert domain_error.details["original_exception"] == "ValueError"
        assert domain_error.details["original_message"] == "unknown error"

    def test_register_custom_mapping(self):
        """Тестирует регистрацию кастомного маппинга."""
        mapper = ExceptionMapper()

        class CustomInfraError(Exception):
            pass

        class CustomDomainError(AppException):
            status_code = 418

        mapper.register(CustomInfraError, CustomDomainError)

        custom_error = CustomInfraError("test error")
        domain_error = mapper.map(custom_error)

        assert isinstance(domain_error, CustomDomainError)
        assert "test error" in domain_error.message

    def test_extract_litellm_metadata(self):
        """Тестирует извлечение метаданных из LiteLLM исключения."""
        mapper = ExceptionMapper()
        llm_error = litellm.exceptions.APIError(
            status_code=500, message="test error", model="gpt-4", llm_provider="openai"
        )

        domain_error = mapper.map(llm_error)

        assert domain_error.details.get("model_name") == "gpt-4"
        assert domain_error.details.get("provider") == "openai"


class TestMapExceptionUtility:
    """Тесты для утилиты map_exception."""

    def test_map_exception_uses_global_mapper(self):
        """Тестирует что map_exception использует глобальный маппер."""
        redis_error = redis.exceptions.ConnectionError("connection refused")

        domain_error = map_exception(redis_error)

        assert isinstance(domain_error, ServiceUnavailableError)

    def test_map_exception_with_litellm_error(self):
        """Тестирует map_exception с LiteLLM ошибкой."""
        llm_error = litellm.exceptions.RateLimitError(
            message="rate limit", model="gpt-4", llm_provider="openai"
        )

        domain_error = map_exception(llm_error)

        assert isinstance(domain_error, RateLimitError)

    def test_map_exception_with_unknown_error(self):
        """Тестирует map_exception с неизвестной ошибкой."""
        unknown_error = RuntimeError("unexpected error")

        domain_error = map_exception(unknown_error)

        assert isinstance(domain_error, InternalServerError)
        assert "unexpected error" in domain_error.message


class TestExceptionMapperEdgeCases:
    """Тесты edge cases для ExceptionMapper."""

    def test_exception_with_empty_message(self):
        """Тестирует маппинг исключения с пустым сообщением."""
        mapper = ExceptionMapper()
        error = ValueError("")

        domain_error = mapper.map(error)

        assert isinstance(domain_error, InternalServerError)
        # InternalServerError имеет дефолтное сообщение если оригинальное пустое
        assert domain_error.message is not None

    def test_multiple_mappings_dont_interfere(self):
        """Тестирует что создание нескольких мапперов не мешает друг другу."""
        mapper1 = ExceptionMapper()
        mapper2 = ExceptionMapper()

        class CustomError1(Exception):
            pass

        class CustomDomainError1(AppException):
            status_code = 418

        mapper1.register(CustomError1, CustomDomainError1)

        # mapper2 не должен иметь этот маппинг
        custom_error = CustomError1("test")
        result1 = mapper1.map(custom_error)
        result2 = mapper2.map(custom_error)

        assert isinstance(result1, CustomDomainError1)
        assert isinstance(result2, InternalServerError)  # Неизвестная ошибка для mapper2
