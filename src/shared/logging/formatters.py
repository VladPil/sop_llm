"""Форматтеры логов для Loguru.

Предоставляет форматтеры для структурированного логирования:
- JSON формат для production (structured logging с trace_id)
- Human-readable формат для development
- Sanitization для чувствительных данных (PII, credentials)
"""

import re
from typing import Any

import orjson


# Паттерны для sanitization чувствительных данных
SENSITIVE_PATTERNS = [
    (re.compile(r'"(password|pwd)"\s*:\s*"[^"]*"', re.IGNORECASE), r'"\1": "***"'),
    (re.compile(r'"(api_key|apikey|secret|token|auth)"\s*:\s*"[^"]*"', re.IGNORECASE), r'"\1": "***"'),
    (re.compile(r"'(password|pwd)'\s*:\s*'[^']*'", re.IGNORECASE), r"'\1': '***'"),
    (re.compile(r"'(api_key|apikey|secret|token|auth)'\s*:\s*'[^']*'", re.IGNORECASE), r"'\1': '***'"),
    (re.compile(r"(password|pwd|api_key|apikey|secret|token|auth)=\S+", re.IGNORECASE), r"\1=***"),
]


def sanitize_sensitive_data(text: str) -> str:
    """Удалить чувствительные данные из строки.

    Заменяет пароли, API ключи, токены и другие credentials на '***'.

    Args:
        text: Текст для sanitization

    Returns:
        Текст с замаскированными чувствительными данными
    """
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def json_formatter(record: dict[str, Any]) -> str:
    """JSON форматтер для production structured logging.

    Создает JSON запись лога с полями:
    - timestamp (ISO 8601)
    - level (INFO, ERROR, etc.)
    - logger (имя модуля)
    - message (сообщение лога)
    - trace_id (Langfuse trace ID, если доступен)
    - span_id (Langfuse span ID, если доступен)
    - extra (дополнительные поля из logger.bind() или logger.info(..., key=value))
    - exception (traceback, если есть)

    Args:
        record: Loguru record dictionary

    Returns:
        JSON строка для structured logging
    """
    # Базовые поля
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
    }

    # Добавить trace_id и span_id из extra (добавляется через patcher)
    extra = record.get("extra", {})
    if "trace_id" in extra:
        log_entry["trace_id"] = extra["trace_id"]
    if "span_id" in extra:
        log_entry["span_id"] = extra["span_id"]

    # Добавить все дополнительные поля из logger.bind() или logger.info(..., key=value)
    for key, value in extra.items():
        if key not in {"trace_id", "span_id"}:
            log_entry[key] = value

    # Добавить exception информацию, если есть
    if record["exception"] is not None:
        exception_info = record["exception"]
        log_entry["exception"] = {
            "type": exception_info.type.__name__ if exception_info.type else None,
            "value": str(exception_info.value) if exception_info.value else None,
            "traceback": record.get("exception", {}).get("traceback", None),
        }

    # Сериализовать в JSON через orjson (быстрее стандартного json)
    json_str = orjson.dumps(log_entry).decode("utf-8")

    # Sanitize чувствительные данные в production
    from src.config import settings

    if settings.app_env == "production":
        json_str = sanitize_sensitive_data(json_str)

    return json_str


def console_formatter(record: dict[str, Any]) -> str:
    """Human-readable форматтер для development.

    Создает читабельный лог с цветами и trace_id (если доступен).

    Формат:
    2024-01-06 12:34:56.789 | INFO     | module:function:42 | [trace_id] - Message

    Args:
        record: Loguru record dictionary

    Returns:
        Отформатированная строка для консоли
    """
    # Базовый формат с цветами (Loguru сам обрабатывает цветовые теги)
    base_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
    )

    # Добавить trace_id, если доступен
    extra = record.get("extra", {})
    if "trace_id" in extra:
        trace_id = extra["trace_id"]
        base_format += f" | <yellow>[{trace_id[:8]}]</yellow>"

    # Завершить формат сообщением
    base_format += " - <level>{message}</level>"

    # Если есть исключение, добавить его
    if record["exception"] is not None:
        base_format += "\n{exception}"

    return base_format


def get_formatter(env: str = "development") -> str:
    """Получить форматтер в зависимости от окружения.

    Args:
        env: Окружение приложения (development/production)

    Returns:
        Строка форматтера для Loguru
    """
    if env == "production":
        # Для production используем JSON форматтер через serialize=True в Loguru
        # json_formatter используется как custom serializer
        return "{message}"  # Loguru сам сериализует через serialize=True
    return console_formatter({})  # Вернуть шаблон форматтера
