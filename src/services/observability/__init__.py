"""Langfuse Observability Integration.

Модуль для distributed tracing, мониторинга и аналитики LLM операций.
Интегрируется с LiteLLM для автоматического трейсинга cloud провайдеров.

Архитектура модуля следует принципам SOLID:
- client.py: Инициализация и singleton управление Langfuse клиентом
- context.py: Context managers для trace/span lifecycle
- decorators.py: Декораторы для автоматического трейсинга
- integrations.py: Интеграция с внешними библиотеками (LiteLLM)
- logging_helpers.py: Ручное логирование событий
- utils.py: Вспомогательные функции

Example:
    Базовое использование:

    >>> # Инициализация при запуске приложения
    >>> from src.services.observability import initialize_langfuse, configure_litellm_callbacks
    >>> initialize_langfuse(
    ...     public_key="pk_xxx",
    ...     secret_key="sk_xxx",
    ...     host="https://cloud.langfuse.com"
    ... )
    >>> configure_litellm_callbacks()
    >>>
    >>> # Использование trace context
    >>> from src.services.observability import trace_context
    >>> async with trace_context(name="llm_task", user_id="user123"):
    ...     result = await process_task(...)
    >>>
    >>> # Использование декораторов
    >>> from src.services.observability import trace_llm_generation
    >>> @trace_llm_generation(name="local_inference")
    ... async def generate(prompt: str) -> str:
    ...     return await model.generate(prompt)

"""

# Client management
from src.services.observability.client import (
    flush_observations,
    get_langfuse_client,
    initialize_langfuse,
)

# Context managers
from src.services.observability.context import span_context, trace_context

# Decorators
from src.services.observability.decorators import trace_llm_generation, trace_operation

# Integrations
from src.services.observability.integrations import configure_litellm_callbacks

# Manual logging
from src.services.observability.logging_helpers import log_error, log_generation

# Utilities
from src.services.observability.utils import (
    get_current_span_id,
    get_current_trace_id,
    is_observability_enabled,
)

__all__ = [
    "configure_litellm_callbacks",
    "flush_observations",
    "get_current_span_id",
    "get_current_trace_id",
    "get_langfuse_client",
    "initialize_langfuse",
    "is_observability_enabled",
    "log_error",
    "log_generation",
    "span_context",
    "trace_context",
    "trace_llm_generation",
    "trace_operation",
]
