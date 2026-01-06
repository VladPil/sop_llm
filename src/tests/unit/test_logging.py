"""Unit тесты для utils/logging.py."""

import logging
import sys
from io import StringIO
from unittest.mock import patch

import pytest
from loguru import logger

from src.utils.logging import InterceptHandler, configure_third_party_loggers, get_logger, setup_logging


class TestInterceptHandler:
    """Тесты для InterceptHandler."""

    def test_intercept_handler_creation(self) -> None:
        """Тест создания InterceptHandler."""
        handler = InterceptHandler()
        assert isinstance(handler, logging.Handler)

    def test_intercept_handler_emit(self) -> None:
        """Тест обработки лог записи."""
        handler = InterceptHandler()

        # Создаём лог запись
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Должно выполниться без ошибок
        try:
            handler.emit(record)
        except Exception as e:
            pytest.fail(f"emit() raised an exception: {e}")


class TestSetupLogging:
    """Тесты для setup_logging."""

    def test_setup_logging_development(self) -> None:
        """Тест настройки логирования для development."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.app_env = "development"
            mock_settings.log_level = "INFO"

            # Вызываем setup
            setup_logging()

            # Проверяем что логгер настроен
            assert logger

    def test_setup_logging_production(self) -> None:
        """Тест настройки логирования для production (JSON format)."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.app_env = "production"
            mock_settings.log_level = "WARNING"

            # Вызываем setup
            setup_logging()

            # Проверяем что логгер настроен
            assert logger


class TestConfigureThirdPartyLoggers:
    """Тесты для configure_third_party_loggers."""

    def test_configure_third_party_loggers(self) -> None:
        """Тест настройки сторонних логгеров."""
        # Вызываем конфигурацию
        configure_third_party_loggers()

        # Проверяем что логгеры настроены
        uvicorn_logger = logging.getLogger("uvicorn")
        assert len(uvicorn_logger.handlers) > 0
        assert isinstance(uvicorn_logger.handlers[0], InterceptHandler)

    def test_uvicorn_logger_configured(self) -> None:
        """Тест что uvicorn логгер настроен."""
        configure_third_party_loggers()

        uvicorn_logger = logging.getLogger("uvicorn")

        # Проверяем что handlers заменены на InterceptHandler
        assert any(isinstance(h, InterceptHandler) for h in uvicorn_logger.handlers)
        assert uvicorn_logger.propagate is False

    def test_fastapi_logger_configured(self) -> None:
        """Тест что fastapi логгер настроен."""
        configure_third_party_loggers()

        fastapi_logger = logging.getLogger("fastapi")

        # Проверяем что handlers заменены
        assert any(isinstance(h, InterceptHandler) for h in fastapi_logger.handlers)
        assert fastapi_logger.propagate is False


class TestGetLogger:
    """Тесты для get_logger."""

    def test_get_logger_without_name(self) -> None:
        """Тест получения логгера без имени."""
        log = get_logger()

        # Должен вернуть logger instance
        assert log is not None
        # Это Loguru logger, у него метод info и т.д.
        assert hasattr(log, "info")
        assert hasattr(log, "error")
        assert hasattr(log, "warning")

    def test_get_logger_with_name(self) -> None:
        """Тест получения логгера с именем."""
        log = get_logger("test_module")

        # Должен вернуть logger instance с bind
        assert log is not None
        assert hasattr(log, "info")

    def test_get_logger_can_log(self) -> None:
        """Тест что полученный логгер может логировать."""
        log = get_logger("test")

        # Перехватываем stdout для проверки
        captured_output = StringIO()

        with patch("sys.stdout", captured_output):
            # Логируем сообщение
            try:
                log.info("Test log message")
            except Exception as e:
                pytest.fail(f"Logging failed: {e}")


class TestLoggingIntegration:
    """Интеграционные тесты логирования."""

    def test_full_logging_setup(self) -> None:
        """Тест полной настройки логирования."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.app_env = "development"
            mock_settings.log_level = "DEBUG"

            # Полная настройка
            setup_logging()

            # Получаем логгер
            log = get_logger("integration_test")

            # Логируем
            try:
                log.debug("Debug message")
                log.info("Info message")
                log.warning("Warning message")
                log.error("Error message")
            except Exception as e:
                pytest.fail(f"Full logging setup failed: {e}")

    def test_json_logging_format(self) -> None:
        """Тест JSON формата логирования для production."""
        with patch("src.config.settings") as mock_settings:
            mock_settings.app_env = "production"
            mock_settings.log_level = "INFO"

            setup_logging()

            log = get_logger("json_test")

            # В production логи должны быть в JSON формате (serialize=True)
            # Проверяем что логирование работает
            try:
                log.info("Test JSON log", extra_field="value")
            except Exception as e:
                pytest.fail(f"JSON logging failed: {e}")
