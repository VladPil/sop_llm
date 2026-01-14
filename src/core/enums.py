"""Enums для SOP LLM Executor.

Централизованное хранилище всех enum'ов проекта.
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Статус задачи генерации."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FinishReason(str, Enum):
    """Причина завершения генерации."""

    STOP = "stop"
    LENGTH = "length"
    ERROR = "error"


class ProviderType(str, Enum):
    """Тип провайдера LLM."""

    LOCAL = "local"
    OLLAMA = "ollama"
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC = "anthropic"
    LITELLM = "litellm"
    EMBEDDING = "embedding"
    CUSTOM = "custom"


class HealthStatus(str, Enum):
    """Статус здоровья сервиса."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ModelType(str, Enum):
    """Тип модели для специфичной обработки промптов."""

    LLAMA = "llama"
    MISTRAL = "mistral"
    QWEN = "qwen"
    PHI = "phi"
    GEMMA = "gemma"
    GENERIC = "generic"


class LogLevel(str, Enum):
    """Уровень логирования."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AppEnvironment(str, Enum):
    """Окружение приложения."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
