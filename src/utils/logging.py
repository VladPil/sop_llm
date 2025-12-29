"""Logging Configuration для SOP LLM Executor.

Настройка Loguru с поддержкой:
- JSON формат для production
- Ротация логов
- Интеграция с Redis (для WebSocket мониторинга)
"""

import sys
from typing import Any

from loguru import logger

from config.settings import settings


def serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Сериализовать log record в JSON-совместимый формат.

    Args:
        record: Record от Loguru

    Returns:
        JSON-совместимый словарь

    """
    return {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        **record["extra"],
    }


def setup_logging() -> None:
    """Настроить Loguru для всего приложения.

    Конфигурация:
    - Development: human-readable в stdout
    - Production: JSON в файл с ротацией
    - Redis sink: для WebSocket мониторинга (опционально)
    """
    # Удалить дефолтный handler
    logger.remove()

    # Формат для development
    dev_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Формат для production (JSON)
    json_format = "{message}"

    if settings.app_env == "development":
        # Development: colorful stdout
        logger.add(
            sys.stdout,
            format=dev_format,
            level=settings.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # Production: JSON в stdout (для Docker logs)
        logger.add(
            sys.stdout,
            format=json_format,
            level=settings.log_level,
            serialize=True,  # JSON формат
            backtrace=False,
            diagnose=False,
        )

    # Опциональная ротация логов в файл (только если DEBUG)
    if settings.debug:
        logger.add(
            "logs/sop_llm_{time:YYYY-MM-DD}.log",
            format=json_format,
            level="DEBUG",
            rotation="50 MB",  # Ротация по размеру
            retention="7 days",  # Хранить 7 дней
            compression="zip",  # Сжатие старых логов
            serialize=True,
            backtrace=True,
            diagnose=True,
        )

    logger.info(
        "Logging настроен",
        env=settings.app_env,
        level=settings.log_level,
        debug=settings.debug,
    )


def get_logger() -> Any:
    """Получить настроенный logger instance.

    Returns:
        Loguru logger

    """
    return logger
