"""Helper функции для структурированного логирования.

Предоставляет специализированные функции для логирования:
- LLM генераций (с параметрами, токенами, latency)
- Ошибок провайдеров (с retry информацией)
- PII sanitization для безопасного логирования
"""

import re
import time
from typing import Any

from loguru import logger

# Паттерны для обнаружения PII (Personally Identifiable Information)
PII_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "***@***.***"),
    # Phone numbers (различные форматы)
    (re.compile(r"\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b"), "***-***-****"),
    # Credit card numbers (основные форматы)
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "****-****-****-****"),
    # Social Security Numbers (SSN)
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***-**-****"),
    # IP addresses (можно считать PII в некоторых контекстах)
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "***.***.***.***"),
]


def sanitize_pii(text: str, mask: str = "***") -> str:
    """Удалить PII (Personally Identifiable Information) из текста.

    Заменяет emails, телефоны, кредитные карты и другую личную информацию
    на безопасные placeholder'ы.

    Args:
        text: Текст для sanitization
        mask: Строка для замены PII (по умолчанию "***")

    Returns:
        Текст с замаскированной личной информацией

    Example:
        >>> sanitize_pii("Contact: john@example.com, +1-555-123-4567")
        'Contact: ***@***.***., ***-***-****'

    """
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_credentials(data: dict[str, Any]) -> dict[str, Any]:
    """Удалить credentials (пароли, API ключи) из словаря.

    Рекурсивно проходит по словарю и заменяет чувствительные поля на '***'.

    Args:
        data: Словарь с данными

    Returns:
        Новый словарь с замаскированными credentials

    Example:
        >>> sanitize_credentials({"user": "admin", "password": "secret"})
        {'user': 'admin', 'password': '***'}

    """
    sensitive_keys = {
        "password",
        "pwd",
        "api_key",
        "apikey",
        "secret",
        "token",
        "auth",
        "authorization",
        "credentials",
        "private_key",
        "access_token",
        "refresh_token",
    }

    if not isinstance(data, dict):
        return data

    sanitized = {}
    for key, value in data.items():
        # Проверить если ключ содержит чувствительное слово
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            sanitized[key] = "***"
        elif isinstance(value, dict):
            # Рекурсивно sanitize вложенные словари
            sanitized[key] = sanitize_credentials(value)
        elif isinstance(value, list):
            # Sanitize элементы списка
            sanitized[key] = [sanitize_credentials(item) if isinstance(item, dict) else item for item in value]
        else:
            sanitized[key] = value

    return sanitized


def log_llm_generation(
    provider: str,
    model: str,
    prompt: str | list[dict],
    response: str | None = None,
    params: dict[str, Any] | None = None,
    usage: dict[str, int] | None = None,
    latency_ms: float | None = None,
    error: Exception | None = None,
    task_id: str | None = None,
) -> None:
    """Логировать LLM генерацию со всеми параметрами.

    Специализированная функция для логирования вызовов LLM с детальной информацией:
    - Provider и модель
    - Prompt (с PII sanitization)
    - Response (с PII sanitization)
    - Параметры генерации (temperature, max_tokens, etc.)
    - Token usage (prompt_tokens, completion_tokens, total_tokens)
    - Latency в миллисекундах
    - Ошибки (если есть)

    Args:
        provider: Имя провайдера (local, anthropic, openai, etc.)
        model: Имя модели (llama-7b, claude-3.5-sonnet, gpt-4, etc.)
        prompt: Входной prompt (строка или список сообщений)
        response: Ответ от модели
        params: Параметры генерации (temperature, max_tokens, etc.)
        usage: Token usage информация
        latency_ms: Время генерации в миллисекундах
        error: Исключение, если произошла ошибка
        task_id: ID задачи для корреляции

    Example:
        >>> log_llm_generation(
        ...     provider="anthropic",
        ...     model="claude-3.5-sonnet",
        ...     prompt="Translate: Hello",
        ...     response="Привет",
        ...     params={"temperature": 0.7},
        ...     usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        ...     latency_ms=234.5,
        ...     task_id="abc123"
        ... )

    """
    # Sanitize prompt и response для безопасного логирования
    from src.core.config import settings

    if settings.app_env == "production":
        if isinstance(prompt, str):
            prompt = sanitize_pii(prompt)
        if response:
            response = sanitize_pii(response)
        if params:
            params = sanitize_credentials(params)

    log_data = {
        "event": "llm_generation",
        "provider": provider,
        "model": model,
        "task_id": task_id,
    }

    # Добавить параметры если есть
    if params:
        log_data["params"] = params

    # Добавить usage если есть
    if usage:
        log_data["usage"] = usage

    # Добавить latency если есть
    if latency_ms is not None:
        log_data["latency_ms"] = round(latency_ms, 2)

    # Логировать в зависимости от результата
    if error:
        logger.error(
            f"LLM generation failed: {provider}/{model}",
            error=str(error),
            **log_data,
        )
    else:
        # В production логируем только метаданные, не полный промпт/ответ (может быть большим)
        if settings.app_env == "development":
            log_data["prompt_preview"] = (
                prompt[:200] + "..." if isinstance(prompt, str) and len(prompt) > 200 else prompt
            )
            if response:
                log_data["response_preview"] = response[:200] + "..." if len(response) > 200 else response

        logger.info(
            f"LLM generation completed: {provider}/{model}",
            **log_data,
        )


def log_provider_error(
    provider: str,
    operation: str,
    error: Exception,
    context: dict[str, Any] | None = None,
    retry_count: int = 0,
    will_retry: bool = False,
) -> None:
    """Логировать ошибку провайдера с контекстом.

    Специализированная функция для логирования ошибок при работе с LLM провайдерами.
    Включает retry информацию и контекст для debugging.

    Args:
        provider: Имя провайдера (local, anthropic, openai, etc.)
        operation: Операция которая завершилась ошибкой (generate, load_model, etc.)
        error: Исключение
        context: Дополнительный контекст (model_name, task_id, etc.)
        retry_count: Текущий номер попытки
        will_retry: Будет ли выполнена повторная попытка

    Example:
        >>> log_provider_error(
        ...     provider="anthropic",
        ...     operation="generate",
        ...     error=APIError("Rate limit exceeded"),
        ...     context={"model": "claude-3.5-sonnet", "task_id": "abc123"},
        ...     retry_count=1,
        ...     will_retry=True
        ... )

    """
    log_data = {
        "event": "provider_error",
        "provider": provider,
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "retry_count": retry_count,
        "will_retry": will_retry,
    }

    # Добавить контекст если есть
    if context:
        # Sanitize credentials в контексте
        from src.core.config import settings

        if settings.app_env == "production":
            context = sanitize_credentials(context)
        log_data["context"] = context

    if will_retry:
        logger.warning(
            f"Provider error (will retry {retry_count + 1}): {provider}/{operation}",
            **log_data,
        )
    else:
        logger.error(
            f"Provider error (final): {provider}/{operation}",
            **log_data,
        )


class LogExecutionTime:
    """Context manager для логирования времени выполнения операции.

    Example:
        >>> with LogExecutionTime("model_loading", model="llama-7b"):
        ...     model = load_model("llama-7b")
        # Логирует: "Operation completed: model_loading (1234.56ms)"

    """

    def __init__(self, operation: str, **extra_fields: Any) -> None:
        """Инициализировать context manager.

        Args:
            operation: Название операции
            **extra_fields: Дополнительные поля для логирования

        """
        self.operation = operation
        self.extra_fields = extra_fields
        self.start_time = 0.0

    def __enter__(self) -> "LogExecutionTime":
        """Начать измерение времени."""
        self.start_time = time.perf_counter()
        logger.debug(f"Operation started: {self.operation}", **self.extra_fields)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Завершить измерение и залогировать результат."""
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000

        log_data = {
            "operation": self.operation,
            "latency_ms": round(elapsed_ms, 2),
            **self.extra_fields,
        }

        if exc_type is not None:
            logger.error(
                f"Operation failed: {self.operation} ({elapsed_ms:.2f}ms)",
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                **log_data,
            )
        else:
            logger.info(
                f"Operation completed: {self.operation} ({elapsed_ms:.2f}ms)",
                **log_data,
            )


def log_streaming_chunk(
    provider: str,
    model: str,
    chunk_size: int,
    total_chunks: int,
    task_id: str | None = None,
) -> None:
    """Логировать chunk в streaming генерации.

    Args:
        provider: Имя провайдера
        model: Имя модели
        chunk_size: Размер текущего chunk в символах
        total_chunks: Общее количество chunk'ов на данный момент
        task_id: ID задачи

    """
    logger.debug(
        f"Streaming chunk: {provider}/{model}",
        event="streaming_chunk",
        provider=provider,
        model=model,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        task_id=task_id,
    )
