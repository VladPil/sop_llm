"""Примеры использования модуля errors.

Этот файл содержит практические примеры использования системы исключений.
Может использоваться как справочник или для обучения.
"""

from typing import Any

from src.shared.errors import (
    AppException,
    GenerationFailedError,
    ModelNotFoundError,
    NotFoundError,
    ProviderUnavailableError,
    TokenLimitExceededError,
    ValidationError,
    map_exception,
)

# Пример 1: Базовое использование AppException


class CustomBusinessError(AppException):
    """Произошла кастомная бизнес-ошибка."""

    status_code = 400


def example_basic_exception() -> None:
    """Демонстрация базового использования."""
    # Автоматическая генерация error_code из имени класса
    error = CustomBusinessError()
    assert error.code == "custom_business_error"
    assert error.message == "Произошла кастомная бизнес-ошибка."
    assert error.status_code == 400

    # С кастомным сообщением
    error = CustomBusinessError(message="Детальное описание проблемы")
    assert error.message == "Детальное описание проблемы"

    # С дополнительными деталями
    error = CustomBusinessError(
        message="Ошибка обработки",
        details={"user_id": 123, "action": "update"},
    )
    assert error.details == {"user_id": 123, "action": "update"}

    # Сериализация в ErrorResponse
    response = error.to_response()
    assert response.error_code == "custom_business_error"
    assert response.message == "Ошибка обработки"
    assert response.details == {"user_id": 123, "action": "update"}


# Пример 2: Стандартные доменные ошибки


def example_domain_errors() -> None:
    """Демонстрация использования доменных ошибок."""
    # ValidationError
    try:
        raise ValidationError(
            message="Некорректный формат email",
            details={"field": "email", "value": "invalid"},
        )
    except ValidationError as e:
        assert e.status_code == 422
        assert e.code == "validation_error"

    # NotFoundError
    try:
        user_id = 123
        raise NotFoundError(
            message=f"Пользователь {user_id} не найден",
            details={"user_id": user_id},
        )
    except NotFoundError as e:
        assert e.status_code == 404
        assert e.code == "not_found_error"


# Пример 3: LLM-специфичные ошибки


def example_llm_errors() -> None:
    """Демонстрация использования LLM-ошибок."""
    # ModelNotFoundError с автоматическим сообщением
    try:
        raise ModelNotFoundError(model_name="gpt-4")
    except ModelNotFoundError as e:
        assert e.status_code == 404
        assert e.message == "Модель 'gpt-4' не найдена в реестре"
        assert e.details["model_name"] == "gpt-4"

    # TokenLimitExceededError с автоматическим сообщением
    try:
        raise TokenLimitExceededError(tokens_used=5000, tokens_limit=4096)
    except TokenLimitExceededError as e:
        assert e.status_code == 422
        assert e.message == "Превышен лимит токенов: 5000/4096"
        assert e.details["tokens_used"] == 5000
        assert e.details["tokens_limit"] == 4096

    # ProviderUnavailableError
    try:
        raise ProviderUnavailableError(provider_name="anthropic")
    except ProviderUnavailableError as e:
        assert e.status_code == 503
        assert e.message == "Провайдер 'anthropic' недоступен"
        assert e.details["provider"] == "anthropic"

    # GenerationFailedError с полной информацией
    try:
        raise GenerationFailedError(
            model_name="gpt-3.5-turbo",
            reason="Connection timeout",
        )
    except GenerationFailedError as e:
        assert e.status_code == 500
        assert "gpt-3.5-turbo" in e.message
        assert "Connection timeout" in e.message


# Пример 4: Маппинг инфраструктурных ошибок


def example_exception_mapping() -> None:
    """Демонстрация маппинга инфраструктурных исключений."""
    import asyncpg  # type: ignore[import-not-found]

    # PostgreSQL UniqueViolationError -> ConflictError
    try:
        db_error = asyncpg.UniqueViolationError("duplicate key value")
        raise map_exception(db_error)
    except AppException as e:
        assert e.__class__.__name__ == "ConflictError"
        assert e.status_code == 409
        assert "duplicate key value" in e.message


# Пример 5: Интеграция с FastAPI


def example_fastapi_integration() -> dict[str, Any]:
    """Пример обработчика ошибок для FastAPI."""
    from fastapi import Request
    from fastapi.responses import JSONResponse

    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Обработчик доменных исключений.

        Args:
            request: FastAPI запрос.
            exc: Доменное исключение.

        Returns:
            JSONResponse: HTTP ответ с деталями ошибки.

        """
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response().model_dump(),
        )

    # Пример использования в endpoint
    async def get_user_endpoint(user_id: int) -> dict[str, Any]:
        """Получение пользователя."""
        user = None  # await get_user_from_db(user_id)

        if not user:
            raise NotFoundError(
                message=f"Пользователь {user_id} не найден",
                details={"user_id": user_id},
            )

        return {"id": user_id, "name": "John"}

    return {"handler": app_exception_handler, "endpoint": get_user_endpoint}


# Пример 6: Расширение ExceptionMapper


def example_custom_mapping() -> None:
    """Демонстрация регистрации кастомного маппинга."""
    from src.shared.errors import exception_mapper

    # Кастомная инфраструктурная ошибка
    class CustomInfraError(Exception):
        """Кастомная инфраструктурная ошибка."""

    # Кастомная доменная ошибка
    class CustomDomainError(AppException):
        """Кастомная доменная ошибка."""

        status_code = 503

    # Регистрация маппинга
    exception_mapper.register(CustomInfraError, CustomDomainError)

    # Использование
    try:
        infra_error = CustomInfraError("Infrastructure failure")
        raise map_exception(infra_error)
    except CustomDomainError as e:
        assert e.status_code == 503
        assert "Infrastructure failure" in e.message


# Пример 7: Обработка ошибок в сервисном слое


async def example_service_layer() -> None:
    """Пример обработки ошибок в сервисном слое."""

    async def generate_completion(
        model_name: str,
        prompt: str,
        max_tokens: int = 4096,
    ) -> str:
        """Генерация completion с обработкой ошибок.

        Args:
            model_name: Название модели.
            prompt: Промпт для генерации.
            max_tokens: Максимальное количество токенов.

        Returns:
            str: Сгенерированный текст.

        Raises:
            ModelNotFoundError: Модель не найдена.
            TokenLimitExceededError: Превышен лимит токенов.
            GenerationFailedError: Ошибка генерации.

        """
        # Проверка модели
        available_models = ["gpt-3.5-turbo", "gpt-4"]
        if model_name not in available_models:
            raise ModelNotFoundError(model_name=model_name)

        # Проверка лимита токенов
        estimated_tokens = len(prompt) // 4  # Упрощенная оценка
        if estimated_tokens > max_tokens:
            raise TokenLimitExceededError(
                tokens_used=estimated_tokens,
                tokens_limit=max_tokens,
            )

        # Симуляция генерации
        try:
            # response = await llm_client.generate(...)
            return "Generated text"
        except Exception as e:
            raise GenerationFailedError(
                model_name=model_name,
                reason=str(e),
            ) from e


if __name__ == "__main__":
    # Запуск всех примеров
    print("1. Базовое использование AppException")
    example_basic_exception()
    print("   OK\n")

    print("2. Стандартные доменные ошибки")
    example_domain_errors()
    print("   OK\n")

    print("3. LLM-специфичные ошибки")
    example_llm_errors()
    print("   OK\n")

    print("4. Маппинг инфраструктурных ошибок")
    example_exception_mapping()
    print("   OK\n")

    print("5. Интеграция с FastAPI")
    example_fastapi_integration()
    print("   OK\n")

    print("6. Расширение ExceptionMapper")
    example_custom_mapping()
    print("   OK\n")

    print("Все примеры выполнены успешно!")
