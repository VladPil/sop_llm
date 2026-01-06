"""Langfuse Observability Integration.

Provides distributed tracing, monitoring, and analytics for LLM operations.
Integrates with LiteLLM for automatic cloud provider tracing.
"""

import contextvars
import functools
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe
from loguru import logger

# Context variable for storing current trace/span ID
_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)

# Global Langfuse client instance
_langfuse_client: Langfuse | None = None


def initialize_langfuse(
    public_key: str,
    secret_key: str,
    host: str = "http://localhost:3000",
    enabled: bool = True,
) -> Langfuse:
    """Initialize Langfuse client for observability.

    Args:
        public_key: Langfuse public API key
        secret_key: Langfuse secret API key
        host: Langfuse server URL (self-hosted or cloud)
        enabled: Enable/disable Langfuse tracking

    Returns:
        Initialized Langfuse client
    """
    global _langfuse_client

    if not enabled:
        logger.warning("Langfuse observability is disabled")
        _langfuse_client = None
        return None

    try:
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            enabled=enabled,
        )
        logger.info(f"Langfuse client initialized: {host}")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        _langfuse_client = None
        raise


def get_langfuse_client() -> Langfuse | None:
    """Get the global Langfuse client instance."""
    return _langfuse_client


def is_observability_enabled() -> bool:
    """Check if observability is enabled."""
    return _langfuse_client is not None


def configure_litellm_callbacks() -> None:
    """Configure LiteLLM to send traces to Langfuse automatically.

    This enables automatic tracing for all cloud LLM API calls.
    """
    if not is_observability_enabled():
        logger.warning("Skipping LiteLLM callback configuration - Langfuse not initialized")
        return

    try:
        import litellm

        # Enable Langfuse callback for automatic tracing
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

        logger.info("LiteLLM callbacks configured for Langfuse tracing")
    except Exception as e:
        logger.error(f"Failed to configure LiteLLM callbacks: {e}")


@asynccontextmanager
async def trace_context(
    name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> AsyncGenerator[None, None]:
    """Create a new Langfuse trace context.

    Use this to wrap task processing or request handling.

    Example:
        async with trace_context(
            name="llm_task",
            user_id="user123",
            session_id="session456",
            metadata={"task_id": "abc"},
        ):
            result = await process_llm_request(...)
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
        )

        # Store trace ID in context variable
        _trace_id_var.set(trace.id if trace else None)

        logger.debug(f"Trace started: {name} (user={user_id}, session={session_id})")
        yield

    except Exception as e:
        logger.error(f"Error in trace_context: {e}")
        # Continue execution even if tracing fails
        yield
    finally:
        _trace_id_var.set(None)


@asynccontextmanager
async def span_context(
    name: str,
    metadata: dict[str, Any] | None = None,
    input_data: Any = None,
    output_data: Any = None,
) -> AsyncGenerator[None, None]:
    """Create a nested span within current trace.

    Use this for sub-operations within a traced request.

    Example:
        async with span_context(
            name="load_model",
            metadata={"model_name": "llama-7b"},
        ):
            model = await load_model(...)
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

        _span_id_var.set(span.id if span else None)
        yield

    except Exception as e:
        logger.error(f"Error in span_context: {e}")
        yield
    finally:
        _span_id_var.set(None)


def get_current_trace_id() -> str | None:
    """Get current trace ID from context."""
    return _trace_id_var.get()


def get_current_span_id() -> str | None:
    """Get current span ID from context."""
    return _span_id_var.get()


F = TypeVar("F", bound=Callable[..., Any])


def trace_llm_generation(
    name: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
) -> Callable[[F], F]:
    """Decorator to trace LLM generation calls.

    Use this for LocalProvider or custom LLM calls that aren't tracked by LiteLLM.

    Example:
        @trace_llm_generation(name="local_llm_inference")
        async def generate(self, prompt: str, **kwargs) -> str:
            return await self._generate(prompt, **kwargs)
    """
    def decorator(func: F) -> F:
        if not is_observability_enabled():
            return func

        @observe(name=name or func.__name__, capture_input=capture_input, capture_output=capture_output)
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def trace_operation(
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator to trace any async operation.

    General-purpose tracing for non-LLM operations.

    Example:
        @trace_operation(name="redis_cache_lookup", metadata={"cache_type": "session"})
        async def get_from_cache(self, key: str) -> Any:
            return await self.redis.get(key)
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

        return wrapper
    return decorator


def log_generation(
    model: str,
    input_text: str | list[dict],
    output_text: str,
    metadata: dict[str, Any] | None = None,
    usage: dict[str, int] | None = None,
    level: str = "DEFAULT",
) -> None:
    """Manually log an LLM generation event to Langfuse.

    Use when automatic tracing isn't available (e.g., LocalProvider).

    Args:
        model: Model name/identifier
        input_text: Input prompt or messages
        output_text: Generated output
        metadata: Additional metadata (task_id, provider, etc.)
        usage: Token usage dict with 'prompt_tokens', 'completion_tokens', 'total_tokens'
        level: Observation level (DEFAULT, WARNING, ERROR)
    """
    if not is_observability_enabled():
        return

    try:
        langfuse_context.generation(
            name="llm_generation",
            model=model,
            input=input_text,
            output=output_text,
            metadata=metadata or {},
            usage=usage,
            level=level,
        )
    except Exception as e:
        logger.error(f"Failed to log generation to Langfuse: {e}")


def log_error(
    error: Exception,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log an error event to current trace.

    Args:
        error: The exception that occurred
        metadata: Additional context about the error
    """
    if not is_observability_enabled():
        return

    try:
        langfuse_context.update_current_observation(
            level="ERROR",
            status_message=str(error),
            metadata=metadata or {},
        )
    except Exception as e:
        logger.error(f"Failed to log error to Langfuse: {e}")


def flush_observations() -> None:
    """Flush all pending observations to Langfuse server.

    Call this before application shutdown to ensure all traces are sent.
    """
    if not is_observability_enabled():
        return

    try:
        _langfuse_client.flush()
        logger.info("Langfuse observations flushed")
    except Exception as e:
        logger.error(f"Failed to flush Langfuse observations: {e}")
