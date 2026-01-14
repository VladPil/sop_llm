"""Модуль структурированного логирования с интеграцией Langfuse.

Предоставляет единый интерфейс для логирования во всем приложении:
- Автоматическая интеграция с Langfuse trace_id
- JSON формат для production structured logging
- Human-readable формат для development
- Специализированные функции для LLM логирования
- PII sanitization для безопасности

Основное использование:
    >>> from src.shared.logging import setup_logging, get_logger
    >>> setup_logging()  # Вызвать один раз при старте
    >>> logger = get_logger(__name__)
    >>> logger.info("Test message")  # trace_id добавится автоматически

Для LLM операций:
    >>> from src.shared.logging import log_llm_generation, log_provider_error
    >>> log_llm_generation(
    ...     provider="anthropic",
    ...     model="claude-3.5-sonnet",
    ...     prompt="Hello",
    ...     response="Hi!",
    ...     usage={"total_tokens": 15},
    ...     latency_ms=234.5
    ... )
"""

from src.shared.logging.config import (
    InterceptHandler,
    configure_third_party_loggers,
    get_logger,
    setup_logging,
)
from src.shared.logging.formatters import (
    console_formatter,
    json_formatter,
    sanitize_sensitive_data,
)
from src.shared.logging.helpers import (
    LogExecutionTime,
    log_llm_generation,
    log_provider_error,
    log_streaming_chunk,
    sanitize_credentials,
    sanitize_pii,
)
from src.shared.logging.patchers import (
    install_langfuse_patcher,
    install_opentelemetry_patcher,
    langfuse_patcher,
    opentelemetry_patcher,
)

__all__ = [
    "InterceptHandler",
    "LogExecutionTime",
    "configure_third_party_loggers",
    "console_formatter",
    "get_logger",
    "install_langfuse_patcher",
    "install_opentelemetry_patcher",
    "json_formatter",
    "langfuse_patcher",
    "log_llm_generation",
    "log_provider_error",
    "log_streaming_chunk",
    "opentelemetry_patcher",
    "sanitize_credentials",
    "sanitize_pii",
    "sanitize_sensitive_data",
    "setup_logging",
]
