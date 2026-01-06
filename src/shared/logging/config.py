"""Конфигурация Loguru с интеграцией Langfuse.

Настройка структурированного логирования с автоматической интеграцией
Langfuse trace_id для корреляции логов с distributed tracing.

Основные функции:
- setup_logging() - основная функция настройки логирования
- configure_third_party_loggers() - перехват логов сторонних библиотек
- get_logger() - получение настроенного logger instance
"""

import logging
import sys
from typing import Any

from loguru import logger

from src.core.config import settings
from src.shared.logging.formatters import json_formatter
from src.shared.logging.patchers import install_langfuse_patcher


class InterceptHandler(logging.Handler):
    """Handler для перехвата логов стандартного logging и перенаправления в Loguru.

    Многие библиотеки (uvicorn, fastapi, litellm, anthropic, openai) используют
    стандартный модуль logging. Чтобы все логи были в едином формате Loguru,
    мы перехватываем их через этот handler.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Обработка одной записи лога из стандартного logging.

        Этот метод вызывается автоматически при каждом логе из библиотеки,
        использующей стандартный logging (например uvicorn.info("Starting server")).

        Алгоритм работы:
        1. Получаем уровень лога (INFO, ERROR и т.д.) из record
        2. Определяем глубину стека вызовов для правильного отображения файла и строки
        3. Перенаправляем лог в Loguru с сохранением всей контекстной информации

        Args:
            record: Запись лога из стандартного logging со всей информацией

        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Вычислить правильную глубину стека для отображения источника лога
        frame = logging.currentframe()
        depth = 2

        if frame:
            while frame.f_code.co_filename == logging.__file__:
                if frame.f_back:
                    frame = frame.f_back
                    depth += 1
                else:
                    break

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def custom_serializer(record: dict[str, Any]) -> str:
    """Custom serializer для Loguru в production режиме.

    Использует json_formatter для создания structured JSON логов с trace_id.

    Args:
        record: Loguru record dictionary

    Returns:
        JSON строка для structured logging

    """
    return json_formatter(record)


def setup_logging() -> None:
    """Настроить Loguru для всего приложения с интеграцией Langfuse.

    Конфигурация:
    - Development: human-readable в stdout с цветами и trace_id
    - Production: JSON формат для Loki structured logging с trace_id
    - Перехват сторонних логгеров (uvicorn, fastapi, litellm, anthropic, openai, redis)
    - PII sanitization в production
    - Автоматическое добавление trace_id через Langfuse patcher

    Вызывается один раз при старте приложения в app.py.

    Example:
        >>> setup_logging()
        >>> logger = get_logger(__name__)
        >>> logger.info("Test message")  # trace_id добавится автоматически

    """
    # Удалить дефолтный handler Loguru
    logger.remove()

    # Установить Langfuse patcher для автоматического добавления trace_id
    install_langfuse_patcher()

    if settings.app_env == "development":
        # Development: красивый формат с цветами и trace_id
        dev_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        )

        # Добавить trace_id в формат если доступен
        dev_format += " | <yellow>[{extra[trace_id]}]</yellow> - <level>{message}</level>"

        logger.add(
            sys.stdout,
            format=dev_format,
            level=settings.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # Production: JSON формат для structured logging с trace_id
        # serialize=True автоматически создает JSON с полями:
        # - timestamp (ISO format)
        # - level
        # - message
        # - module, function, line
        # - extra (включая trace_id и span_id от Langfuse patcher)
        logger.add(
            sys.stdout,
            format="{message}",
            level=settings.log_level,
            serialize=True,  # Автоматический JSON формат
            backtrace=True,
            diagnose=False,  # В production не показываем переменные (security)
            enqueue=True,  # Асинхронное логирование для лучшей производительности
        )

    # Настроить перехват логов сторонних библиотек
    configure_third_party_loggers()

    logger.info(
        "Логирование настроено с Langfuse интеграцией",
        level=settings.log_level,
        env=settings.app_env,
        service="sop_llm",
        langfuse_enabled=settings.langfuse_enabled,
    )


def configure_third_party_loggers() -> None:
    """Настройка логирования для сторонних библиотек.

    Что делает эта функция:
    1. Перехватывает логи от библиотек (uvicorn, fastapi, litellm, anthropic, openai, redis)
    2. Перенаправляет их в Loguru для единого формата
    3. Устанавливает уровни логирования (чтобы не засорять логи)

    Зачем это нужно:
    - Библиотеки используют стандартный logging, мы используем Loguru
    - Хотим видеть ВСЕ логи в одном красивом формате Loguru
    - Нужно контролировать verbosity (особенно для httpx и uvicorn.access)
    - Автоматически добавлять trace_id даже в логи библиотек
    """
    # Очистить root logger
    logging.root.handlers = []
    logging.root.setLevel(logging.INFO)

    # Список логгеров для настройки
    loggers_to_configure = [
        "",  # Root logger
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "redis",
        "httpx",
        "litellm",  # LiteLLM proxy для cloud providers
        "anthropic",  # Claude API
        "openai",  # OpenAI API
        "langfuse",  # Langfuse observability
    ]

    for logger_name in loggers_to_configure:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers.clear()
        logging_logger.addHandler(InterceptHandler())
        logging_logger.propagate = False

        # Настроить уровень логирования в зависимости от библиотеки
        if logger_name in {"uvicorn.access", "httpx"}:
            # Access логи только WARNING+ в production для уменьшения noise
            logging_logger.setLevel(logging.WARNING if settings.app_env == "production" else logging.INFO)
        elif logger_name == "litellm":
            # LiteLLM может быть очень verbose, контролируем через settings
            if settings.litellm_debug:
                logging_logger.setLevel(logging.DEBUG)
            else:
                logging_logger.setLevel(logging.INFO)
        else:
            logging_logger.setLevel(logging.INFO)

    logger.debug("Сторонние логгеры настроены с Loguru перехватом")


def get_logger(name: str | None = None):
    """Получить настроенный logger instance.

    Args:
        name: Имя логгера (обычно __name__ модуля)

    Returns:
        Настроенный Loguru logger с Langfuse интеграцией

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing task", task_id="abc123")
        # Автоматически добавит trace_id из Langfuse context

    """
    if name:
        return logger.bind(name=name)
    return logger
