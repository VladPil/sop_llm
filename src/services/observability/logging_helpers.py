"""Функции ручного логирования.

Функции для ручного логирования событий в Langfuse.
Используются когда автоматический трейсинг недоступен.
"""

from typing import Any

from loguru import logger

try:
    from langfuse.decorators import langfuse_context
except (ImportError, AttributeError):
    try:
        from langfuse.client import langfuse_context
    except ImportError:
        class DummyContext:
            def flush(self):
                pass
        langfuse_context = DummyContext()

from src.services.observability.utils import is_observability_enabled


def log_generation(
    model: str,
    input_text: str | list[dict],
    output_text: str,
    metadata: dict[str, Any] | None = None,
    usage: dict[str, int] | None = None,
    level: str = "DEFAULT",
) -> None:
    """Вручную логирует LLM generation событие в Langfuse.

    Используется когда автоматический трейсинг недоступен
    (например, для LocalProvider или кастомных реализаций).

    Args:
        model: Имя/идентификатор модели.
        input_text: Входной промпт или список сообщений.
        output_text: Сгенерированный вывод.
        metadata: Дополнительные метаданные (task_id, provider и т.д.).
        usage: Статистика использования токенов с ключами:
            - prompt_tokens: количество токенов в промпте
            - completion_tokens: количество токенов в ответе
            - total_tokens: общее количество токенов
        level: Уровень observation (DEFAULT, WARNING, ERROR).

    Example:
        >>> log_generation(
        ...     model="llama-7b",
        ...     input_text="What is Python?",
        ...     output_text="Python is a programming language...",
        ...     metadata={"provider": "local", "task_id": "123"},
        ...     usage={"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60}
        ... )

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
        logger.error(f"Не удалось залогировать генерацию в Langfuse: {e}")


def log_error(
    error: Exception,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Логирует error событие в текущий trace.

    Добавляет информацию об ошибке к текущему observation в Langfuse.
    Должна вызываться внутри активного trace context.

    Args:
        error: Произошедшее исключение.
        metadata: Дополнительный контекст об ошибке.

    Example:
        >>> try:
        ...     await risky_operation()
        ... except Exception as e:
        ...     log_error(e, metadata={"operation": "model_load", "model": "llama-7b"})
        ...     raise

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
        logger.error(f"Не удалось залогировать ошибку в Langfuse: {e}")
