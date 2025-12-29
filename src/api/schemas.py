"""SOP LLM - API Schemas.

Pydantic схемы для API запросов и ответов.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from src.core.constants import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
)

# ==================== Enums ====================


class TaskType(str, Enum):
    """Тип задачи."""

    GENERATE = "generate"
    EMBEDDING = "embedding"
    SIMILARITY = "similarity"


class ModelProvider(str, Enum):
    """Провайдер модели."""

    LOCAL = "local"
    CLAUDE = "claude"
    LM_STUDIO = "lm_studio"


class SimilarityMethod(str, Enum):
    """Метод вычисления схожести."""

    COSINE = "cosine"  # Косинусное сходство
    EUCLIDEAN = "euclidean"  # Евклидово расстояние
    MANHATTAN = "manhattan"  # Манхэттенское расстояние
    JACCARD = "jaccard"  # Коэффициент Жаккара
    PEARSON = "pearson"  # Корреляция Пирсона
    DOT_PRODUCT = "dot_product"  # Скалярное произведение
    ALL = "all"  # Все методы


class TaskStatus(str, Enum):
    """Статус задачи."""

    PENDING = TASK_STATUS_PENDING
    PROCESSING = TASK_STATUS_PROCESSING
    COMPLETED = TASK_STATUS_COMPLETED
    FAILED = TASK_STATUS_FAILED


# ==================== Request Schemas ====================


class TaskRequest(BaseModel):
    """Запрос на создание задачи.

    Attributes:
        text: Входной текст для обработки.
        task_type: Тип задачи (generate/embedding).
        model: Имя модели (опционально).
        provider: Провайдер модели.
        parameters: Дополнительные параметры генерации.
        use_cache: Использовать кэш для результатов.
        expected_format: Ожидаемый формат ответа.
        json_schema: JSON Schema для валидации.
        preprocess_text: Предобработка текста перед отправкой.

    """

    text: str = Field(
        ...,
        description="Входной текст",
        min_length=1,
        max_length=10000,
    )

    task_type: TaskType = Field(
        ...,
        description="Тип задачи",
    )

    model: str | None = Field(
        None,
        description="Имя модели (опционально, используется default)",
    )

    provider: ModelProvider = Field(
        ModelProvider.LOCAL,
        description="Провайдер модели (local/claude/lm_studio)",
    )

    parameters: dict[str, Any] | None = Field(
        default_factory=dict,
        description="Дополнительные параметры генерации",
    )

    use_cache: bool = Field(
        True,
        description="Использовать кэш для результатов",
    )

    expected_format: Literal["text", "json"] | None = Field(
        "text",
        description="Ожидаемый формат ответа (text или json)",
    )

    json_schema: dict[str, Any] | None = Field(
        None,
        description="JSON Schema для валидации ответа (если expected_format='json')",
    )

    preprocess_text: bool | str | None = Field(
        False,
        description=(
            "Предобработка текста перед отправкой в LLM. "
            'Может быть: false (выкл), true/"standard" (стандартная), '
            '"minimal" (минимальная), "aggressive" (агрессивная)'
        ),
    )

    @field_validator("preprocess_text")
    @classmethod
    def validate_preprocess_text(cls, v: bool | str | None) -> bool | str:
        """Валидация параметра предобработки.

        Args:
            v: Значение для валидации.

        Returns:
            Валидированное значение.

        Raises:
            ValueError: Если значение некорректно.

        """
        if v is False or v is None:
            return False
        if v is True:
            return "standard"
        if isinstance(v, str):
            if v.lower() in ["minimal", "standard", "aggressive"]:
                return v.lower()
            raise ValueError(
                "preprocess_text должен быть 'minimal', 'standard' или 'aggressive'"
            )
        raise ValueError("preprocess_text должен быть bool или строкой")

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: dict[str, Any] | None) -> dict[str, Any]:
        """Валидация параметров.

        Args:
            v: Значение для валидации.

        Returns:
            Валидированные параметры.

        Raises:
            ValueError: Если параметры некорректны.

        """
        if v is None:
            return {}

        # Проверяем max_tokens
        if "max_tokens" in v and v["max_tokens"] > DEFAULT_MAX_TOKENS:
            msg = f"max_tokens не может быть больше {DEFAULT_MAX_TOKENS}"
            raise ValueError(msg)

        # Проверяем temperature
        if "temperature" in v and not (0 <= v["temperature"] <= 2):
            raise ValueError("temperature должен быть от 0 до 2")

        return v

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "examples": [
                {
                    "text": "Напиши короткую историю про кота",
                    "task_type": "generate",
                    "model": "qwen",
                    "provider": "local",
                    "parameters": {
                        "max_tokens": 512,
                        "temperature": DEFAULT_TEMPERATURE,
                    },
                    "use_cache": True,
                    "expected_format": "text",
                },
                {
                    "text": "Извлеки из текста имя, возраст и город. Текст: 'Меня зовут Алексей, мне 25 лет, живу в Москве'",
                    "task_type": "generate",
                    "model": "qwen",
                    "provider": "local",
                    "parameters": {
                        "max_tokens": 256,
                        "temperature": 0.3,
                    },
                    "use_cache": True,
                    "expected_format": "json",
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                            "city": {"type": "string"},
                        },
                        "required": ["name", "age", "city"],
                    },
                },
            ]
        }


class SimilarityRequest(BaseModel):
    """Запрос на вычисление сходства.

    Attributes:
        text1: Первый текст для сравнения.
        text2: Второй текст для сравнения.
        model: Имя embedding модели.
        method: Метод вычисления схожести.
        use_cache: Использовать кэш для результатов.
        preprocess_text: Предобработка текстов.

    """

    text1: str = Field(
        ...,
        description="Первый текст",
        min_length=1,
        max_length=10000,
    )

    text2: str = Field(
        ...,
        description="Второй текст",
        min_length=1,
        max_length=10000,
    )

    model: str | None = Field(
        None,
        description="Имя embedding модели",
    )

    method: SimilarityMethod = Field(
        SimilarityMethod.COSINE,
        description="Метод вычисления схожести",
    )

    use_cache: bool = Field(
        True,
        description="Использовать кэш для результатов",
    )

    preprocess_text: bool | str | None = Field(
        False,
        description=(
            "Предобработка текстов перед вычислением сходства. "
            'Может быть: false (выкл), true/"standard" (стандартная), '
            '"minimal" (минимальная), "aggressive" (агрессивная)'
        ),
    )


# ==================== Response Schemas ====================


class TokenInfo(BaseModel):
    """Информация о токенах.

    Attributes:
        input: Количество входных токенов.
        output: Количество выходных токенов.
        total: Общее количество токенов.

    """

    input: int = Field(..., description="Количество входных токенов")
    output: int = Field(..., description="Количество выходных токенов")
    total: int = Field(..., description="Общее количество токенов")


class GenerationResult(BaseModel):
    """Результат генерации текста.

    Attributes:
        text: Сгенерированный текст.
        provider: Использованный провайдер.
        model: Название модели.
        tokens: Информация о токенах.
        was_fixed: Был ли JSON исправлен.
        fix_attempts: Количество попыток исправления.

    """

    text: str = Field(..., description="Сгенерированный текст")
    provider: str = Field(..., description="Использованный провайдер")
    model: str = Field(..., description="Название модели")
    tokens: TokenInfo = Field(..., description="Информация о токенах")
    was_fixed: bool | None = Field(
        None,
        description="Был ли JSON исправлен",
    )
    fix_attempts: int | None = Field(
        None,
        description="Количество попыток исправления JSON",
    )


class EmbeddingResult(BaseModel):
    """Результат embedding.

    Attributes:
        embedding: Вектор embedding.
        dimension: Размерность вектора.

    """

    embedding: list[float] = Field(..., description="Вектор embedding")
    dimension: int = Field(..., description="Размерность вектора")


class TaskCreatedResponse(BaseModel):
    """Ответ при создании задачи.

    Attributes:
        task_id: ID созданной задачи.
        status: Начальный статус задачи.
        message: Информационное сообщение.

    """

    task_id: str = Field(..., description="ID созданной задачи")
    status: TaskStatus = Field(..., description="Начальный статус задачи")
    message: str = Field(..., description="Информационное сообщение")


class TaskResponse(BaseModel):
    """Ответ с информацией о задаче.

    Attributes:
        task_id: ID задачи.
        status: Статус задачи.
        result: Результат выполнения.
        error: Сообщение об ошибке.
        created_at: Время создания задачи.
        completed_at: Время завершения задачи.
        duration_ms: Длительность выполнения в миллисекундах.
        request: Оригинальный запрос.
        processing_details: Детали обработки задачи.
        from_cache: Был ли результат получен из кеша.

    """

    task_id: str = Field(..., description="ID задачи")
    status: TaskStatus = Field(..., description="Статус задачи")
    result: GenerationResult | EmbeddingResult | dict[str, Any] | None = Field(
        None,
        description="Результат выполнения (если completed)",
    )
    error: str | None = Field(
        None,
        description="Сообщение об ошибке (если failed)",
    )
    created_at: datetime | None = Field(
        None,
        description="Время создания задачи",
    )
    completed_at: datetime | None = Field(
        None,
        description="Время завершения задачи",
    )
    duration_ms: float | None = Field(
        None,
        description="Длительность выполнения в миллисекундах",
    )
    request: TaskRequest | None = Field(
        None,
        description="Оригинальный запрос",
    )
    processing_details: dict[str, Any] | None = Field(
        None,
        description="Детали обработки задачи",
    )
    from_cache: bool | None = Field(
        None,
        description="Был ли результат получен из кеша",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "task_id": "d05c76a5-1a97-4da8-ba32-c8f3bc480f07",
                "status": "completed",
                "result": {
                    "text": "Привет! Как дела?",
                    "provider": "local",
                    "model": "Qwen/Qwen2.5-3B-Instruct",
                    "tokens": {
                        "input": 10,
                        "output": 15,
                        "total": 25,
                    },
                },
                "created_at": "2025-11-11T16:51:02.257441",
                "completed_at": "2025-11-11T16:51:02.257442",
                "duration_ms": 1500.0,
            }
        }


class HealthResponse(BaseModel):
    """Ответ health check.

    Attributes:
        status: Общий статус системы.
        timestamp: Unix timestamp.
        components: Статусы отдельных компонентов.

    """

    status: Literal["healthy", "degraded", "unhealthy", "warning"] = Field(
        ...,
        description="Общий статус системы",
    )
    timestamp: float = Field(..., description="Unix timestamp")
    components: dict[str, Any] = Field(
        ...,
        description="Статусы отдельных компонентов",
    )


class ModelInfo(BaseModel):
    """Информация о модели.

    Attributes:
        name: Название модели.
        type: Тип модели.
        loaded: Загружена ли модель.
        device: Устройство (cpu/cuda).
        stats: Статистика использования.

    """

    name: str = Field(..., description="Название модели")
    type: Literal["llm", "embedding", "json_fixer"] = Field(
        ..., description="Тип модели"
    )
    loaded: bool = Field(..., description="Загружена ли модель")
    device: str = Field(..., description="Устройство (cpu/cuda)")
    stats: dict[str, Any] | None = Field(
        None,
        description="Статистика использования",
    )


class ModelsListResponse(BaseModel):
    """Список моделей.

    Attributes:
        models: Список моделей.

    """

    models: list[ModelInfo] = Field(..., description="Список моделей")


class MetricsResponse(BaseModel):
    """Метрики Prometheus.

    Attributes:
        llm: Метрики LLM.
        embedding: Метрики Embedding.
        json_fixer: Метрики JSON Fixer.
        cache: Метрики кэша.
        system: Системные метрики.

    """

    llm: dict[str, Any] = Field(..., description="Метрики LLM")
    embedding: dict[str, Any] = Field(..., description="Метрики Embedding")
    json_fixer: dict[str, Any] = Field(..., description="Метрики JSON Fixer")
    cache: dict[str, Any] = Field(..., description="Метрики кэша")
    system: dict[str, Any] = Field(..., description="Системные метрики")


class ProviderInfo(BaseModel):
    """Информация о провайдере.

    Attributes:
        name: Имя провайдера.
        is_available: Доступность провайдера.
        capabilities: Список возможностей провайдера.
        is_default: Является ли провайдер default.

    """

    name: str = Field(..., description="Имя провайдера")
    is_available: bool = Field(..., description="Доступность провайдера")
    capabilities: list[str] = Field(
        ...,
        description="Список возможностей провайдера",
    )
    is_default: bool = Field(
        False,
        description="Является ли провайдер default",
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "local",
                "is_available": True,
                "capabilities": ["text_generation", "chat_completion", "json_mode"],
                "is_default": True,
            }
        }


class ProvidersListResponse(BaseModel):
    """Список доступных провайдеров.

    Attributes:
        providers: Список провайдеров.
        total: Общее количество провайдеров.

    """

    providers: list[ProviderInfo] = Field(
        ...,
        description="Список провайдеров",
    )
    total: int = Field(..., description="Общее количество провайдеров")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "providers": [
                    {
                        "name": "local",
                        "is_available": True,
                        "capabilities": ["text_generation", "chat_completion"],
                        "is_default": True,
                    },
                    {
                        "name": "claude",
                        "is_available": True,
                        "capabilities": ["text_generation", "streaming", "vision"],
                        "is_default": False,
                    },
                    {
                        "name": "lm_studio",
                        "is_available": False,
                        "capabilities": ["text_generation", "streaming"],
                        "is_default": False,
                    },
                ],
                "total": 3,
            }
        }
