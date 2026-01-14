"""Декораторы для автоматического трейсинга.

Декораторы для автоматического трейсинга функций и методов.
Упрощают интеграцию observability в существующий код.
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from src.services.observability.utils import is_observability_enabled

try:
    from langfuse.decorators import langfuse_context, observe
except (ImportError, AttributeError):
    # langfuse >= 3.0 moved these
    try:
        from langfuse import observe  # type: ignore[attr-defined]
        from langfuse.client import langfuse_context  # type: ignore[attr-defined]
    except ImportError:
        # Fallback - create dummy implementations
        class DummyContext:
            """Fallback when langfuse is not installed."""

            def flush(self) -> None:
                pass

            def update_current_observation(self, **kwargs: Any) -> None:
                return None
        langfuse_context = DummyContext()

        def observe(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func
            return decorator

F = TypeVar("F", bound=Callable[..., Any])


def trace_llm_generation(
    name: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable[[F], F]:
    """Декоратор для трейсинга LLM generation вызовов.

    Используется для LocalProvider или кастомных LLM вызовов,
    которые не трекаются автоматически через LiteLLM.

    Args:
        name: Имя операции (по умолчанию - имя функции).
        capture_input: Захватывать ли входные данные.
        capture_output: Захватывать ли выходные данные.

    Returns:
        Декорированная функция с трейсингом.

    Example:
        >>> @trace_llm_generation(name="local_llm_inference")
        ... async def generate(self, prompt: str, **kwargs) -> str:
        ...     return await self._generate(prompt, **kwargs)

    """

    def decorator(func: F) -> F:
        if not is_observability_enabled():
            return func

        @observe(name=name or func.__name__, capture_input=capture_input, capture_output=capture_output)
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return cast("F", wrapper)

    return decorator


def trace_operation(
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Декоратор для трейсинга любой async операции.

    Универсальный декоратор для трейсинга non-LLM операций
    (database queries, cache lookups, API calls и т.д.).

    Args:
        name: Имя операции (по умолчанию - имя функции).
        metadata: Дополнительные метаданные для операции.

    Returns:
        Декорированная функция с трейсингом.

    Example:
        >>> @trace_operation(name="redis_cache_lookup", metadata={"cache_type": "session"})
        ... async def get_from_cache(self, key: str) -> Any:
        ...     return await self.redis.get(key)

    """

    def decorator(func: F) -> F:
        if not is_observability_enabled():
            return func

        @observe(name=name or func.__name__)
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if metadata:
                langfuse_context.update_current_observation(metadata=metadata)
            return await func(*args, **kwargs)

        return cast("F", wrapper)

    return decorator
