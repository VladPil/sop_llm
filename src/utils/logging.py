"""SOP LLM - Logging Configuration.

Настройка Loguru для структурированного логирования.
Следует принципам наблюдаемости и отладки.

Этот модуль настраивает единый логгер для всего приложения:
- Loguru для собственных логов (красивый формат, цвета, структурированность)
- Перехват логов сторонних библиотек (uvicorn, fastapi) и перенаправление в Loguru
"""

import logging
import sys

from loguru import logger

from src.config import settings


class InterceptHandler(logging.Handler):
    """Handler для перехвата логов стандартного logging и перенаправления в Loguru.

    Многие библиотеки (uvicorn, fastapi) используют стандартный модуль logging.
    Чтобы все логи были в едином формате Loguru, мы перехватываем их через этот handler.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Обработка одной записи лога из стандартного logging.

        Этот метод вызывается автоматически при каждом логе из библиотеки
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


def setup_logging() -> None:
    """Настроить Loguru для всего приложения.

    Конфигурация:
    - Development: human-readable в stdout с цветами
    - Production: JSON формат для structured logging
    - Перехват сторонних логгеров (uvicorn, fastapi, redis)
    """
    logger.remove()

    dev_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    if settings.app_env == "development":
        logger.add(
            sys.stdout,
            format=dev_format,
            level=settings.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # Production: JSON формат через serialize=True
        logger.add(
            sys.stdout,
            format="{message}",
            level=settings.log_level,
            serialize=True,
            backtrace=True,
            diagnose=False,
            enqueue=True,
        )

    configure_third_party_loggers()

    logger.info("Логгер настроен", extra={"level": settings.log_level, "env": settings.app_env})


def configure_third_party_loggers() -> None:
    """Настройка логирования для сторонних библиотек.

    Что делает эта функция:
    1. Перехватывает логи от библиотек (uvicorn, fastapi, redis)
    2. Перенаправляет их в Loguru для единого формата
    3. Устанавливает уровни логирования (чтобы не засорять логи)

    Зачем это нужно:
    - Библиотеки используют стандартный logging, мы используем Loguru
    - Хотим видеть ВСЕ логи в одном красивом формате Loguru
    - Нужно контролировать verbosity
    """
    logging.root.handlers = []
    logging.root.setLevel(logging.INFO)

    loggers_to_configure = [
        "",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "redis",
        "httpx",
    ]

    for logger_name in loggers_to_configure:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers.clear()
        logging_logger.addHandler(InterceptHandler())
        logging_logger.propagate = False

        if logger_name in {"uvicorn.access", "httpx"}:
            logging_logger.setLevel(logging.WARNING if settings.app_env == "production" else logging.INFO)
        else:
            logging_logger.setLevel(logging.INFO)

    logger.debug("Сторонние логгеры настроены")


def get_logger(name: str | None = None):
    """Получить настроенный logger instance.

    Args:
        name: Имя логгера (обычно __name__ модуля)

    Returns:
        Настроенный Loguru logger

    """
    if name:
        return logger.bind(name=name)
    return logger
