"""Context менеджеры для трейсинга.

Async context managers для создания traces и spans в Langfuse.
Обеспечивают автоматическое управление lifecycle трейсов.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger

try:
    from langfuse.decorators import langfuse_context
except (ImportError, AttributeError):
    try:
        from langfuse.client import langfuse_context  # type: ignore[attr-defined]
    except ImportError:
        class DummyContext:
            """Fallback when langfuse is not installed."""

            def flush(self) -> None:
                pass

            def update_current_trace(self, **kwargs: Any) -> None:
                return None

            def update_current_observation(self, **kwargs: Any) -> None:
                return None
        langfuse_context = DummyContext()

from src.services.observability.utils import is_observability_enabled, set_span_id, set_trace_id


@asynccontextmanager
async def trace_context(
    name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    input_data: Any = None,
    output_data: Any = None,
) -> AsyncGenerator[None, None]:
    """Создает новый Langfuse trace context.

    Используется для оборачивания обработки задач или HTTP запросов.
    Автоматически управляет lifecycle trace и сохраняет его ID в контексте.

    Args:
        name: Имя trace (например, "llm_task", "api_request").
        user_id: ID пользователя для привязки к trace.
        session_id: ID сессии для группировки связанных traces.
        metadata: Дополнительные метаданные (task_id, request_id и т.д.).
        tags: Теги для классификации traces.
        input_data: Входные данные для trace.
        output_data: Выходные данные для trace.

    Yields:
        None

    Example:
        >>> async with trace_context(
        ...     name="llm_task",
        ...     user_id="user123",
        ...     session_id="session456",
        ...     metadata={"task_id": "abc"},
        ... ):
        ...     result = await process_llm_request(...)

    """
    if not is_observability_enabled():
        yield
        return

    try:
        trace = langfuse_context.update_current_trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
            tags=tags or [],
            input=input_data,
            output=output_data,
        )

        set_trace_id(trace.id if trace else None)

        logger.debug(f"Trace начат: {name} (user={user_id}, session={session_id})")

    except Exception as e:
        logger.error(f"Ошибка инициализации trace_context: {e}")

    try:
        yield
    finally:
        set_trace_id(None)


@asynccontextmanager
async def span_context(
    name: str,
    metadata: dict[str, Any] | None = None,
    input_data: Any = None,
    output_data: Any = None,
) -> AsyncGenerator[None, None]:
    """Создает вложенный span внутри текущего trace.

    Используется для трейсинга под-операций внутри traced request.
    Spans образуют иерархию внутри одного trace.

    Args:
        name: Имя span (например, "load_model", "cache_lookup").
        metadata: Дополнительные метаданные для span.
        input_data: Входные данные операции.
        output_data: Выходные данные операции.

    Yields:
        None

    Example:
        >>> async with span_context(
        ...     name="load_model",
        ...     metadata={"model_name": "llama-7b"},
        ... ):
        ...     model = await load_model(...)

    """
    if not is_observability_enabled():
        yield
        return

    try:
        span = langfuse_context.update_current_observation(
            name=name,
            metadata=metadata or {},
            input=input_data,
            output=output_data,
        )

        set_span_id(span.id if span else None)

    except Exception as e:
        logger.error(f"Ошибка инициализации span_context: {e}")

    try:
        yield
    finally:
        set_span_id(None)
