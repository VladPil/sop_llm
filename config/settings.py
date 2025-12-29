"""SOP LLM Executor - Configuration Settings.

Pydantic Settings для управления конфигурацией через env vars.
Следует ТЗ: Dumb Executor паттерн.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Главные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =================================================================
    # Application
    # =================================================================
    app_name: str = Field(default="SOP LLM Executor", description="Название приложения")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Окружение"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Уровень логирования"
    )
    debug: bool = Field(default=False, description="Режим отладки")

    # =================================================================
    # Server
    # =================================================================
    server_host: str = Field(default="0.0.0.0", description="Хост сервера")
    server_port: int = Field(default=8023, ge=1, le=65535, description="Порт сервера")

    @field_validator("server_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Валидация порта."""
        if not 1 <= v <= 65535:
            msg = f"Порт должен быть в диапазоне 1-65535, получено: {v}"
            raise ValueError(msg)
        return v

    # =================================================================
    # Redis
    # =================================================================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL подключения к Redis"
    )

    @property
    def redis_host(self) -> str:
        """Извлечь host из redis_url."""
        # redis://host:port/db
        url = self.redis_url.replace("redis://", "")
        return url.split(":")[0]

    @property
    def redis_port(self) -> int:
        """Извлечь port из redis_url."""
        url = self.redis_url.replace("redis://", "")
        port_db = url.split(":")[1]
        return int(port_db.split("/")[0])

    @property
    def redis_db(self) -> int:
        """Извлечь db из redis_url."""
        return int(self.redis_url.split("/")[-1])

    # =================================================================
    # GPU / Hardware (только для local provider)
    # =================================================================
    gpu_index: int = Field(default=0, ge=0, description="Индекс GPU (CUDA)")
    max_vram_usage_percent: int = Field(
        default=95,
        ge=50,
        le=100,
        description="Максимальный процент использования VRAM"
    )
    vram_reserve_mb: int = Field(
        default=1024,
        ge=0,
        description="Резерв VRAM в MB (для системы)"
    )

    # =================================================================
    # Local Models
    # =================================================================
    models_dir: str = Field(default="/app/models", description="Директория с GGUF моделями")
    default_context_window: int = Field(
        default=4096,
        ge=512,
        description="Размер контекстного окна по умолчанию"
    )
    default_max_tokens: int = Field(
        default=2048,
        ge=1,
        description="Максимум токенов в ответе по умолчанию"
    )
    default_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Температура генерации по умолчанию"
    )

    # =================================================================
    # Sessions
    # =================================================================
    session_ttl_hours: int = Field(
        default=24,
        ge=1,
        description="TTL сессий в часах"
    )
    idempotency_ttl_hours: int = Field(
        default=24,
        ge=1,
        description="TTL idempotency ключей в часах"
    )

    @property
    def session_ttl_seconds(self) -> int:
        """TTL сессий в секундах."""
        return self.session_ttl_hours * 3600

    @property
    def idempotency_ttl_seconds(self) -> int:
        """TTL idempotency в секундах."""
        return self.idempotency_ttl_hours * 3600

    # =================================================================
    # Webhooks
    # =================================================================
    webhook_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout webhook запросов"
    )
    webhook_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Максимум повторов webhook"
    )

    # =================================================================
    # Provider Defaults
    # =================================================================
    default_provider: Literal["local", "openai_compatible", "anthropic", "openai", "custom"] = Field(
        default="local",
        description="Провайдер по умолчанию"
    )

    # OpenAI
    openai_api_key: str | None = Field(default=None, description="OpenAI API ключ")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI base URL"
    )

    # Anthropic (Claude)
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API ключ")

    # OpenAI-Compatible (LM Studio, vLLM, Ollama, etc.)
    openai_compatible_base_url: str = Field(
        default="http://localhost:1234/v1",
        description="OpenAI-compatible API base URL"
    )
    openai_compatible_api_key: str = Field(
        default="not-needed",
        description="API ключ для OpenAI-compatible (если нужен)"
    )

    # OpenRouter
    openrouter_api_key: str | None = Field(default=None, description="OpenRouter API ключ")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter base URL"
    )

    # Together AI
    together_api_key: str | None = Field(default=None, description="Together AI API ключ")
    together_base_url: str = Field(
        default="https://api.together.xyz/v1",
        description="Together AI base URL"
    )

    # =================================================================
    # HTTP Client Settings (для remote providers)
    # =================================================================
    http_timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=600,
        description="Timeout HTTP запросов"
    )
    http_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Максимум повторов HTTP запросов"
    )

    # =================================================================
    # Monitoring
    # =================================================================
    gpu_stats_interval_seconds: int = Field(
        default=2,
        ge=1,
        le=60,
        description="Интервал обновления GPU статистики (для WebSocket)"
    )
    logs_max_recent: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Максимум последних логов в Redis"
    )

    # =================================================================
    # Queue
    # =================================================================
    queue_max_size: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Максимальный размер очереди задач"
    )


# Singleton instance
settings = Settings()
