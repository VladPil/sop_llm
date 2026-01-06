"""Настройки приложения SOP LLM.

Конфигурация загружается из переменных окружения через pydantic-settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Основные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    app_name: str = Field(default="SOP LLM Executor", description="Название приложения")
    app_env: str = Field(default="development", description="Окружение (development/production)")
    debug: bool = Field(default=True, description="Режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")

    # Server Settings
    server_host: str = Field(default="0.0.0.0", description="Хост сервера")
    server_port: int = Field(default=8000, description="Порт сервера")

    # Redis Settings (централизованный Redis из sop_infrastructure)
    redis_url: str = Field(default="redis://redis:6379/1", description="URL для подключения к Redis")
    redis_host: str = Field(default="redis", description="Хост Redis")
    redis_port: int = Field(default=6379, description="Порт Redis")
    redis_db: int = Field(default=1, description="Номер БД Redis (1 для sop_llm)")
    redis_password: str | None = Field(default=None, description="Пароль Redis")

    # Kafka Settings (для будущей интеграции)
    kafka_bootstrap_servers: str = Field(default="kafka:9092", description="Kafka bootstrap servers")

    session_ttl_seconds: int = Field(default=3600, description="TTL сессий в секундах")
    idempotency_ttl_seconds: int = Field(default=86400, description="TTL idempotency ключей в секундах")
    logs_max_recent: int = Field(default=100, description="Максимальное количество последних логов")

    webhook_timeout_seconds: int = Field(default=30, description="Таймаут webhook запросов")
    webhook_max_retries: int = Field(default=3, description="Количество повторов webhook")

    http_timeout_seconds: int = Field(default=60, description="Таймаут HTTP запросов")
    http_max_retries: int = Field(default=2, description="Количество повторов HTTP запросов")

    models_dir: str = Field(default="./models", description="Директория с моделями")
    default_context_window: int = Field(default=4096, description="Размер контекста по умолчанию")
    default_max_tokens: int = Field(default=2048, description="Максимум токенов генерации по умолчанию")

    gpu_index: int = Field(default=0, description="Индекс GPU для использования")
    max_vram_usage_percent: float = Field(default=90.0, description="Максимальный процент использования VRAM")
    vram_reserve_mb: int = Field(default=512, description="Резерв VRAM в МБ")

    # LLM Provider API Keys (используются через LiteLLM)
    openai_api_key: str | None = Field(default=None, description="API ключ OpenAI")
    anthropic_api_key: str | None = Field(default=None, description="API ключ Anthropic")
    gemini_api_key: str | None = Field(default=None, description="API ключ Google Gemini")
    mistral_api_key: str | None = Field(default=None, description="API ключ Mistral AI")
    cohere_api_key: str | None = Field(default=None, description="API ключ Cohere")

    # LiteLLM Configuration
    litellm_debug: bool = Field(default=False, description="Включить debug режим LiteLLM")
    litellm_drop_params: bool = Field(default=True, description="Автоматически удалять несовместимые параметры")
    litellm_max_retries: int = Field(default=3, description="Максимальное количество повторов LiteLLM")
    litellm_timeout: int = Field(default=600, description="Таймаут LiteLLM запросов (секунды)")

    # Langfuse Observability Configuration
    langfuse_enabled: bool = Field(default=True, description="Включить Langfuse observability")
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public API key")
    langfuse_secret_key: str | None = Field(default=None, description="Langfuse secret API key")
    langfuse_host: str = Field(default="http://langfuse:3000", description="Langfuse server URL (self-hosted)")

    enable_json_fixing: bool = Field(default=False, description="Включить JSON fixing")
    json_fixer_timeout: int = Field(default=30, description="Таймаут для JSON fixer")

    cors_allowed_origins: list[str] = Field(default=["*"], description="Разрешённые origins для CORS")


settings = Settings()
