"""Patchers для интеграции Langfuse trace_id в логи.

Обеспечивает автоматическое добавление trace_id и span_id из Langfuse
в каждую запись лога для корреляции логов с distributed tracing.
"""

from typing import Any

from loguru import logger


def langfuse_patcher(record: dict[str, Any]) -> None:
    """Patch Loguru record для добавления Langfuse trace_id и span_id.

    Этот patcher автоматически добавляет trace_id и span_id из Langfuse context
    в каждую запись лога. Это позволяет коррелировать логи с traces в Langfuse UI.

    Алгоритм работы:
    1. Получает текущий trace_id из Langfuse context через observability модуль
    2. Получает текущий span_id из Langfuse context (если в span)
    3. Добавляет их в record["extra"] для использования в форматтерах
    4. Если trace недоступен, использует fallback "NO_TRACE"

    Args:
        record: Loguru record dictionary, который будет модифицирован in-place

    Example:
        # После настройки patcher в Loguru:
        logger.info("Processing request")  # Автоматически содержит trace_id

        # В JSON формате:
        {
            "timestamp": "2024-01-06T12:34:56.789",
            "level": "INFO",
            "message": "Processing request",
            "trace_id": "abc123...",  # <- Добавлено автоматически
            "span_id": "xyz789..."    # <- Добавлено автоматически
        }

    """
    try:
        # Импортируем здесь чтобы избежать circular imports
        from src.services.observability import get_current_span_id, get_current_trace_id

        # Получить trace_id из Langfuse context
        trace_id = get_current_trace_id()
        if trace_id:
            record["extra"]["trace_id"] = trace_id
        else:
            record["extra"]["trace_id"] = "NO_TRACE"

        # Получить span_id из Langfuse context (если внутри span)
        span_id = get_current_span_id()
        if span_id:
            record["extra"]["span_id"] = span_id

    except ImportError:
        # Если observability модуль недоступен, используем fallback
        record["extra"]["trace_id"] = "NO_TRACE"
    except Exception as e:
        # В случае любой ошибки, не прерываем логирование
        # Просто добавляем fallback значение
        record["extra"]["trace_id"] = "NO_TRACE"
        record["extra"]["patcher_error"] = str(e)


def install_langfuse_patcher() -> None:
    """Установить Langfuse patcher в Loguru.

    Этот patcher будет автоматически вызываться для каждой записи лога
    перед её обработкой форматтером.

    Вызывается один раз при настройке логирования в setup_logging().

    Example:
        >>> install_langfuse_patcher()
        >>> logger.info("Test")  # trace_id добавится автоматически

    """
    logger.configure(patcher=langfuse_patcher)


def opentelemetry_patcher(record: dict[str, Any]) -> None:
    """Patch Loguru record для добавления OpenTelemetry trace context.

    Альтернативный patcher для интеграции с OpenTelemetry вместо Langfuse.
    Добавляет trace_id и span_id из OpenTelemetry context.

    Note:
        В текущей архитектуре используется Langfuse, но этот patcher
        предоставляется для возможной будущей интеграции с OpenTelemetry.

    Args:
        record: Loguru record dictionary, который будет модифицирован in-place

    """
    try:
        from opentelemetry import trace

        # Получить текущий span из OpenTelemetry context
        span = trace.get_current_span()
        if span and span.is_recording():
            span_context = span.get_span_context()
            if span_context.is_valid:
                # Конвертировать trace_id и span_id в hex формат
                trace_id = format(span_context.trace_id, "032x")
                span_id = format(span_context.span_id, "016x")

                record["extra"]["trace_id"] = trace_id
                record["extra"]["span_id"] = span_id
            else:
                record["extra"]["trace_id"] = "NO_TRACE"
        else:
            record["extra"]["trace_id"] = "NO_TRACE"

    except ImportError:
        record["extra"]["trace_id"] = "NO_TRACE"
    except Exception as e:
        record["extra"]["trace_id"] = "NO_TRACE"
        record["extra"]["patcher_error"] = str(e)


def install_opentelemetry_patcher() -> None:
    """Установить OpenTelemetry patcher в Loguru.

    Note:
        Не используется в текущей архитектуре (используется Langfuse).
        Предоставляется для возможной будущей интеграции.

    """
    logger.configure(patcher=opentelemetry_patcher)
