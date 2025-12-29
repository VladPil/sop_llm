"""Logging configuration.

Настройка логирования через Loguru.
"""

import logging
import sys
from pathlib import Path

from loguru import logger

from src.core.config import settings
from src.shared.errors.context import get_trace_id


class InterceptHandler(logging.Handler):
    """Обработчик для перехвата логов стандартной библиотеки logging."""

    def emit(self, record: logging.LogRecord) -> None:
        """Перехват и отправка логов в Loguru.

        Args:
            record: Запись лога из стандартного logging.

        """
        # Получаем уровень логирования
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Получаем глубину стека
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Логируем через Loguru
        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def setup_logger() -> None:
    """Настроить логирование приложения."""
    # Удаляем стандартный обработчик Loguru
    logger.remove()

    # Патчер для добавления trace_id в extra
    def trace_id_patcher(record: dict) -> None:
        """Добавить trace_id в запись лога.

        Args:
            record: Запись лога.

        """
        record["extra"]["trace_id"] = get_trace_id() or "no-trace"

    # Настраиваем Loguru с патчером
    logger.configure(patcher=trace_id_patcher)

    # Формат для текстового вывода
    text_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "trace_id=<yellow>{extra[trace_id]}</yellow> | "
        "<level>{message}</level>"
    )

    # Формат для JSON
    json_format = (
        "{{"
        '"time": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
        '"level": "{level}", '
        '"name": "{name}", '
        '"function": "{function}", '
        '"line": {line}, '
        '"trace_id": "{extra[trace_id]}", '
        '"message": "{message}"'
        "}}"
    )

    format_string = json_format if settings.log.format == "json" else text_format

    # Добавляем вывод в stdout
    logger.add(
        sys.stdout,
        format=format_string,
        level=settings.log.level,
        colorize=settings.log.format != "json",
        backtrace=True,
        diagnose=settings.debug,
    )

    # Создаем директорию для логов
    log_path = Path(settings.log.file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Добавляем вывод в файл
    logger.add(
        settings.log.file_path,
        format=json_format,  # Файл всегда в JSON
        level=settings.log.level,
        rotation=settings.log.rotation,
        retention=settings.log.retention,
        compression="zip",
        backtrace=True,
        diagnose=settings.debug,
    )

    # Перехватываем логи сторонних библиотек
    configure_third_party_loggers()

    logger.info(
        "Logger initialized",
        level=settings.log.level,
        format=settings.log.format,
        file=settings.log.file_path,
    )


def configure_third_party_loggers() -> None:
    """Настроить логирование сторонних библиотек."""
    # Библиотеки для перехвата
    loggers_to_intercept = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "transformers",
        "torch",
        "httpx",
        "anthropic",
    ]

    # Отключаем дублирование логов
    logging.getLogger("uvicorn.access").propagate = False

    # Перехватываем логи
    for logger_name in loggers_to_intercept:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    # Устанавливаем уровни для шумных библиотек
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
