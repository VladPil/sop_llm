"""SOP LLM - Configuration.

Конфигурация приложения через Pydantic Settings.
Строгая типизация, валидация форматов и централизованное управление.
"""

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseModel):
    """Настройки сервера (Uvicorn/Gunicorn)."""

    host: str = Field(default="0.0.0.0", description="Хост")
    port: int = Field(default=8023, description="Порт")
    workers: int = Field(default=1, ge=1, description="Количество воркеров")
    timeout: int = Field(default=60, description="Таймаут воркера")
    reload: bool = Field(default=False, description="Режим автоперезагрузки")

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        """Валидация порта.

        Args:
            value: Номер порта для проверки.

        Returns:
            Проверенное значение порта.

        Raises:
            ValueError: Если порт вне допустимого диапазона.

        """
        if not 1 <= value <= 65535:
            msg = f"Порт ({value}) должен быть в диапазоне 1-65535"
            raise ValueError(msg)
        return value


class RedisSettings(BaseModel):
    """Настройки Redis."""

    host: str = Field(default="localhost", description="Redis хост")
    port: int = Field(default=6379, description="Redis порт")
    db: int = Field(default=0, ge=0, le=15, description="Redis database index")
    password: str | None = Field(default=None, description="Redis пароль")
    pool_min: int = Field(default=1, ge=1, description="Минимальный размер пула")
    pool_max: int = Field(default=50, ge=1, description="Максимальный размер пула")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        """Валидация пароля Redis.

        Args:
            value: Пароль для проверки.

        Returns:
            None если пароль пустой, иначе возвращает значение без изменений.

        """
        if value and len(value) == 0:
            return None
        return value

    @field_validator("pool_max")
    @classmethod
    def validate_pool_max(cls, value: int, info: ValidationInfo) -> int:
        """Валидация максимального размера пула соединений.

        Args:
            value: Значение pool_max для проверки.
            info: Информация о валидации.

        Returns:
            Проверенное значение pool_max.

        Raises:
            ValueError: Если pool_max меньше pool_min.

        """
        if "pool_min" in info.data and value < info.data["pool_min"]:
            msg = f"pool_max ({value}) должен быть >= pool_min"
            raise ValueError(msg)
        return value

    @property
    def url(self) -> str:
        """URL для подключения к Redis.

        Returns:
            Строка подключения для Redis.

        """
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class CacheSettings(BaseModel):
    """Настройки кэширования."""

    enabled: bool = Field(default=True, description="Включить кэширование")
    ttl: int = Field(default=600, ge=0, description="TTL кэша в секундах")
    prefix: str = Field(default="sop_llm:", description="Префикс ключей кэша")


class LLMSettings(BaseModel):
    """Настройки LLM моделей."""

    models_cache_dir: str = Field(
        default="~/.cache/huggingface/hub",
        description="Директория для кэша моделей",
    )
    default_model: str = Field(
        default="Qwen/Qwen2.5-3B-Instruct",
        description="Модель LLM по умолчанию",
    )
    default_embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Модель embeddings по умолчанию",
    )
    max_concurrent_requests: int = Field(
        default=2,
        ge=1,
        description="Максимум одновременных запросов к LLM",
    )
    max_tokens_per_request: int = Field(
        default=4096,
        ge=1,
        description="Максимум токенов в запросе",
    )
    request_timeout: int = Field(
        default=60,
        ge=1,
        description="Таймаут запроса в секундах",
    )
    memory_threshold_percent: float = Field(
        default=90.0,
        ge=0.0,
        le=100.0,
        description="Порог использования памяти в процентах",
    )


class JSONFixerSettings(BaseModel):
    """Настройки исправления JSON."""

    enabled: bool = Field(
        default=True,
        description="Включить исправление некорректного JSON",
    )
    model: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct",
        description="Модель для исправления JSON",
    )
    load_in_8bit: bool = Field(
        default=True,
        description="Использовать 8-bit quantization",
    )
    timeout: int = Field(
        default=30,
        ge=1,
        description="Таймаут исправления в секундах",
    )
    max_attempts: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Максимум попыток исправления",
    )


class ClaudeSettings(BaseModel):
    """Настройки Claude API."""

    api_key: str | None = Field(
        default=None,
        description="API ключ Anthropic",
    )
    model: str = Field(
        default="claude-3-haiku-20240307",
        description="Модель Claude",
    )
    max_concurrent_requests: int = Field(
        default=5,
        ge=1,
        description="Максимум одновременных запросов",
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str | None) -> str | None:
        """Валидация API ключа.

        Args:
            value: API ключ для проверки.

        Returns:
            None если ключ пустой, иначе возвращает значение без изменений.

        """
        if value and len(value) < 10:
            msg = "API ключ слишком короткий"
            raise ValueError(msg)
        return value


class QueueSettings(BaseModel):
    """Настройки очереди задач."""

    name: str = Field(default="sop_llm_tasks", description="Имя очереди")
    max_retries: int = Field(default=3, ge=0, description="Максимум повторов")
    retry_delay: int = Field(default=5, ge=0, description="Задержка повтора в секундах")


class LogSettings(BaseModel):
    """Настройки логирования."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Уровень логирования",
    )
    format: Literal["json", "text"] = Field(
        default="json",
        description="Формат логов",
    )
    file_path: str = Field(
        default="logs/sop-llm.log",
        description="Путь к файлу логов",
    )
    rotation: str = Field(
        default="10 MB",
        description="Ротация логов",
    )
    retention: str = Field(
        default="10 days",
        description="Время хранения логов",
    )

    @property
    def format_string(self) -> str:
        """Формат строки логирования для Loguru.

        Returns:
            Строка формата логирования.

        """
        if self.format == "json":
            return "{message}"
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )


class Settings(BaseSettings):
    """Главные настройки приложения.

    Все настройки загружаются из переменных окружения с префиксом SOP__.
    Пример: SOP__SERVER__HOST=0.0.0.0
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_prefix="SOP__",
        extra="ignore",
        protected_namespaces=(),
    )

    app_name: str = Field(default="SOP LLM Service", description="Название приложения")
    environment: Literal["local", "dev", "prod"] = Field(
        default="local",
        description="Окружение",
    )
    debug: bool = Field(default=False, description="Режим отладки")

    server: ServerSettings = Field(default_factory=ServerSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    json_fixer: JSONFixerSettings = Field(default_factory=JSONFixerSettings)
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    log: LogSettings = Field(default_factory=LogSettings)


# Глобальный объект настроек (singleton)
settings = Settings()
