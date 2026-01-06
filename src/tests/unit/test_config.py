"""Unit тесты для config.py."""

import os
from unittest.mock import patch

import pytest

from src.config import Settings


class TestSettings:
    """Тесты для Settings."""

    def test_default_values(self) -> None:
        """Тест значений по умолчанию."""
        settings = Settings()

        # Application settings
        assert settings.app_name == "SOP LLM Executor"
        assert settings.app_env == "development"
        assert settings.debug is True
        assert settings.log_level == "INFO"

        # Server settings
        assert settings.server_host == "0.0.0.0"
        assert settings.server_port == 8000

        # Redis defaults
        assert settings.redis_host == "redis"
        assert settings.redis_port == 6379
        assert settings.redis_db == 1

    def test_environment_variable_override(self) -> None:
        """Тест переопределения через переменные окружения."""
        with patch.dict(
            os.environ,
            {
                "APP_NAME": "Test App",
                "APP_ENV": "production",
                "DEBUG": "false",
                "LOG_LEVEL": "ERROR",
                "SERVER_PORT": "9000",
                "REDIS_DB": "5",
            },
        ):
            settings = Settings()

            assert settings.app_name == "Test App"
            assert settings.app_env == "production"
            assert settings.debug is False
            assert settings.log_level == "ERROR"
            assert settings.server_port == 9000
            assert settings.redis_db == 5

    def test_redis_url_construction(self) -> None:
        """Тест построения Redis URL."""
        settings = Settings()

        # Default без пароля
        expected_url = "redis://redis:6379/1"
        assert settings.redis_url == expected_url

    def test_kafka_settings(self) -> None:
        """Тест настроек Kafka."""
        with patch.dict(
            os.environ,
            {"KAFKA_BOOTSTRAP_SERVERS": "kafka1:9092,kafka2:9092"},
        ):
            settings = Settings()

            assert settings.kafka_bootstrap_servers == "kafka1:9092,kafka2:9092"

    def test_llm_settings(self) -> None:
        """Тест настроек LLM."""
        settings = Settings()

        assert settings.default_context_window == 4096
        assert settings.default_max_tokens == 2048
        assert settings.models_dir == "./models"

    def test_api_keys_optional(self) -> None:
        """Тест что API ключи опциональны."""
        settings = Settings()

        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None
        assert settings.openai_compatible_api_key is None

    def test_cors_settings(self) -> None:
        """Тест настроек CORS."""
        settings = Settings()

        assert settings.cors_allowed_origins == ["*"]

        # С переопределением
        with patch.dict(
            os.environ,
            {"CORS_ALLOWED_ORIGINS": '["http://localhost:3000", "http://example.com"]'},
        ):
            settings = Settings()
            # Pydantic может парсить JSON из строки для list[str]
            assert isinstance(settings.cors_allowed_origins, list)
