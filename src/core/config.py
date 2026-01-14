"""Настройки приложения SOP LLM.

Конфигурация загружается из переменных окружения через pydantic-settings.
Все значения ОБЯЗАТЕЛЬНЫ и должны быть заданы в .env файле или окружении.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.enums import AppEnvironment, LogLevel


class ApplicationSettings(BaseSettings):
    """Основные настройки приложения."""

    app_name: str = Field(description="Название приложения")
    app_version: str = Field(default="1.0.0", description="Версия приложения")
    app_env: AppEnvironment = Field(description="Окружение (local/development/staging/production)")
    debug: bool = Field(description="Режим отладки")
    log_level: LogLevel = Field(description="Уровень логирования")


class ServerSettings(BaseSettings):
    """Настройки сервера."""

    server_host: str = Field(description="Хост сервера")
    server_port: int = Field(description="Порт сервера")


class RedisSettings(BaseSettings):
    """Настройки Redis (централизованный Redis из sop_infrastructure)."""

    redis_url: str = Field(description="URL для подключения к Redis")
    redis_host: str = Field(description="Хост Redis")
    redis_port: int = Field(description="Порт Redis")
    redis_db: int = Field(description="Номер БД Redis (1 для sop_llm)")
    redis_password: str | None = Field(default=None, description="Пароль Redis (опционально)")


class KafkaSettings(BaseSettings):
    """Настройки Kafka (для будущей интеграции)."""

    kafka_bootstrap_servers: str = Field(description="Kafka bootstrap servers")


class SessionSettings(BaseSettings):
    """Настройки сессий и кэширования."""

    session_ttl_seconds: int = Field(description="TTL сессий в секундах")
    idempotency_ttl_seconds: int = Field(description="TTL idempotency ключей в секундах")
    logs_max_recent: int = Field(description="Максимальное количество последних логов")


class WebhookSettings(BaseSettings):
    """Настройки webhook'ов."""

    webhook_timeout_seconds: int = Field(description="Таймаут webhook запросов")
    webhook_max_retries: int = Field(description="Количество повторов webhook")


class HttpSettings(BaseSettings):
    """Настройки HTTP клиента."""

    http_timeout_seconds: int = Field(description="Таймаут HTTP запросов")
    http_max_retries: int = Field(description="Количество повторов HTTP запросов")


class ModelSettings(BaseSettings):
    """Настройки моделей."""

    models_dir: str = Field(description="Директория с моделями")
    default_context_window: int = Field(description="Размер контекста по умолчанию")
    default_max_tokens: int = Field(description="Максимум токенов генерации по умолчанию")


class GPUSettings(BaseSettings):
    """Настройки GPU."""

    gpu_index: int = Field(description="Индекс GPU для использования")
    max_vram_usage_percent: float = Field(description="Максимальный процент использования VRAM")
    vram_reserve_mb: int = Field(description="Резерв VRAM в МБ")


class LLMProviderKeys(BaseSettings):
    """API ключи для LLM провайдеров (используются через LiteLLM)."""

    openai_api_key: str | None = Field(default=None, description="API ключ OpenAI")
    anthropic_api_key: str | None = Field(default=None, description="API ключ Anthropic")
    gemini_api_key: str | None = Field(default=None, description="API ключ Google Gemini")
    mistral_api_key: str | None = Field(default=None, description="API ключ Mistral AI")
    cohere_api_key: str | None = Field(default=None, description="API ключ Cohere")


class LiteLLMSettings(BaseSettings):
    """Настройки LiteLLM."""

    litellm_debug: bool = Field(description="Включить debug режим LiteLLM")
    litellm_drop_params: bool = Field(description="Автоматически удалять несовместимые параметры")
    litellm_max_retries: int = Field(description="Максимальное количество повторов LiteLLM")
    litellm_timeout: int = Field(description="Таймаут LiteLLM запросов (секунды)")


class LangfuseSettings(BaseSettings):
    """Настройки Langfuse Observability."""

    langfuse_enabled: bool = Field(description="Включить Langfuse observability")
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public API key")
    langfuse_secret_key: str | None = Field(default=None, description="Langfuse secret API key")
    langfuse_host: str = Field(description="Langfuse server URL (self-hosted)")


class HuggingFaceSettings(BaseSettings):
    """Настройки HuggingFace Hub для загрузки моделей."""

    hf_token: str | None = Field(default=None, description="HuggingFace токен для приватных репозиториев")
    hf_presets_dir: str = Field(default="config/model_presets", description="Директория с YAML пресетами моделей")
    hf_auto_download: bool = Field(default=True, description="Автоматически скачивать модели при регистрации")


class JSONFixingSettings(BaseSettings):
    """Настройки JSON fixing."""

    enable_json_fixing: bool = Field(description="Включить JSON fixing")
    json_fixer_timeout: int = Field(description="Таймаут для JSON fixer")


class CORSSettings(BaseSettings):
    """Настройки CORS."""

    cors_allowed_origins: list[str] = Field(description="Разрешённые origins для CORS")


class Settings(
    ApplicationSettings,
    ServerSettings,
    RedisSettings,
    KafkaSettings,
    SessionSettings,
    WebhookSettings,
    HttpSettings,
    ModelSettings,
    GPUSettings,
    LLMProviderKeys,
    LiteLLMSettings,
    LangfuseSettings,
    HuggingFaceSettings,
    JSONFixingSettings,
    CORSSettings,
):
    """Объединённые настройки приложения.

    Наследует все настройки из отдельных классов.
    Все значения загружаются из переменных окружения.
    """

    model_config = SettingsConfigDict(
        env_file=".env",  # Используется только для локального запуска без Docker
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
