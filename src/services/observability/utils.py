"""Utility Functions for Observability.

Вспомогательные функции для работы с observability:
проверка состояния, получение контекстных данных.
"""

import contextvars

from src.services.observability.client import get_langfuse_client

# Context variables для хранения текущих trace/span ID
_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)


def is_observability_enabled() -> bool:
    """Проверяет, включен ли observability.

    Returns:
        True, если Langfuse клиент инициализирован и активен.

    Example:
        >>> if is_observability_enabled():
        ...     log_generation(...)
    """
    return get_langfuse_client() is not None


def get_current_trace_id() -> str | None:
    """Возвращает ID текущего trace из контекста.

    Returns:
        ID активного trace или None.

    Example:
        >>> trace_id = get_current_trace_id()
        >>> if trace_id:
        ...     logger.info(f"Current trace: {trace_id}")
    """
    return _trace_id_var.get()


def get_current_span_id() -> str | None:
    """Возвращает ID текущего span из контекста.

    Returns:
        ID активного span или None.

    Example:
        >>> span_id = get_current_span_id()
        >>> if span_id:
        ...     logger.info(f"Current span: {span_id}")
    """
    return _span_id_var.get()


def set_trace_id(trace_id: str | None) -> None:
    """Устанавливает ID текущего trace в контекст.

    Args:
        trace_id: ID trace для сохранения в контексте.

    Note:
        Используется внутренне context managers.
    """
    _trace_id_var.set(trace_id)


def set_span_id(span_id: str | None) -> None:
    """Устанавливает ID текущего span в контекст.

    Args:
        span_id: ID span для сохранения в контексте.

    Note:
        Используется внутренне context managers.
    """
    _span_id_var.set(span_id)
