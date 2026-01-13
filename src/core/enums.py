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

    STOP = "stop"  # Нормальное завершение (stop sequence или EOS)
    LENGTH = "length"  # Достигнут max_tokens
    ERROR = "error"  # Ошибка во время генерации


class ProviderType(str, Enum):
    """Тип провайдера LLM."""

    LOCAL = "local"  # Локальный провайдер (llama.cpp)
    OPENAI = "openai"  # OpenAI API
    OPENAI_COMPATIBLE = "openai_compatible"  # OpenAI-совместимые API
    ANTHROPIC = "anthropic"  # Anthropic Claude API
    LITELLM = "litellm"  # LiteLLM (унифицированный облачный провайдер)
    EMBEDDING = "embedding"  # Sentence-transformers embedding модели
    CUSTOM = "custom"  # Кастомный провайдер


class HealthStatus(str, Enum):
    """Статус здоровья сервиса."""

    HEALTHY = "healthy"  # Все компоненты работают
    DEGRADED = "degraded"  # Есть проблемы, но сервис работает
    UNHEALTHY = "unhealthy"  # Критические проблемы


class ModelType(str, Enum):
    """Тип модели для специфичной обработки промптов."""

    LLAMA = "llama"  # LLaMA models (LLaMA 2, 3, etc.)
    MISTRAL = "mistral"  # Mistral models
    QWEN = "qwen"  # Qwen models
    PHI = "phi"  # Phi models
    GEMMA = "gemma"  # Gemma models
    GENERIC = "generic"  # Общий тип


class LogLevel(str, Enum):
    """Уровень логирования."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AppEnvironment(str, Enum):
    """Окружение приложения."""

    LOCAL = "local"  # Локальная разработка
    DEVELOPMENT = "development"  # Dev окружение
    STAGING = "staging"  # Staging окружение
    PRODUCTION = "production"  # Production окружение
