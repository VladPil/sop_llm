"""Базовый интерфейс для всех LLM провайдеров.

Следует принципам SOLID и определяет контракт для всех провайдеров.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any


class ProviderCapability(str, Enum):
    """Возможности провайдера.

    Используется для проверки поддерживаемых функций.
    """

    TEXT_GENERATION = "text_generation"
    CHAT_COMPLETION = "chat_completion"
    EMBEDDINGS = "embeddings"
    STREAMING = "streaming"
    FUNCTION_CALLING = "function_calling"
    JSON_MODE = "json_mode"
    VISION = "vision"


class BaseLLMProvider(ABC):
    """Базовый абстрактный класс для всех LLM провайдеров.

    Принципы:
    - Single Responsibility: только определение интерфейса провайдера
    - Open/Closed: закрыт для модификации, открыт для расширения
    - Liskov Substitution: все наследники взаимозаменяемы
    - Interface Segregation: минимальный необходимый интерфейс
    - Dependency Inversion: зависимость от абстракции
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Инициализация провайдера.

        Args:
            config: Конфигурация провайдера (из providers.yaml)

        """
        self.config = config
        self._is_initialized = False

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Уникальное имя провайдера.

        Returns:
            Имя провайдера (например: "local", "claude", "lm_studio")

        """

    @property
    @abstractmethod
    def capabilities(self) -> list[ProviderCapability]:
        """Список поддерживаемых возможностей провайдера.

        Returns:
            Список capabilities (например: [TEXT_GENERATION, STREAMING])

        """

    @abstractmethod
    async def initialize(self) -> None:
        """Инициализация провайдера.

        Выполняется один раз при старте приложения.

        Должна включать:
        - Загрузку моделей (для локальных)
        - Установку соединений (для API)
        - Проверку доступности
        - Установку self._is_initialized = True

        Raises:
            Exception: Если инициализация не удалась

        """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        expected_format: str = "text",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Генерация текста.

        Args:
            prompt: Текстовый промпт
            model: Имя модели (опционально, использует default из конфига)
            max_tokens: Максимальное количество токенов для генерации
            temperature: Температура генерации (0.0 - 1.0)
            top_p: Nucleus sampling параметр
            expected_format: Ожидаемый формат ответа ("text" или "json")
            **kwargs: Дополнительные параметры специфичные для провайдера

        Returns:
            Унифицированный словарь с результатом:
            {
                "text": str,                      # Сгенерированный текст
                "model": str,                     # Имя использованной модели
                "tokens": {                       # Информация о токенах
                    "input": int,
                    "output": int,
                    "total": int
                },
                "finish_reason": str,             # Причина завершения (stop, length, etc.)
                "metadata": Dict[str, Any]        # Дополнительная информация
            }

        Raises:
            RuntimeError: Если провайдер не инициализирован
            Exception: При ошибке генерации

        """

    async def generate_streaming(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming генерация текста.

        Опциональный метод. Провайдеры без поддержки streaming
        могут raise NotImplementedError или возвращать результат одним чанком.

        Args:
            prompt: Текстовый промпт
            model: Имя модели
            **kwargs: Дополнительные параметры

        Yields:
            Словари с частями текста:
            {
                "text": str,                  # Часть сгенерированного текста
                "finish_reason": Optional[str] # Если это последний чанк
            }

        Raises:
            NotImplementedError: Если streaming не поддерживается

        """
        msg = f"Provider {self.provider_name} does not support streaming"
        raise NotImplementedError(
            msg
        )

    @abstractmethod
    def is_available(self) -> bool:
        """Проверка доступности провайдера.

        Returns:
            True если провайдер доступен и готов к использованию

        """

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Получение статистики провайдера.

        Returns:
            Словарь со статистикой (может быть специфичным для каждого провайдера):
            {
                "provider": str,
                "is_available": bool,
                "total_requests": int,
                ... другие метрики
            }

        """

    async def cleanup(self) -> None:
        """Очистка ресурсов при завершении работы провайдера.

        Опциональный метод. Может включать:
        - Закрытие соединений
        - Освобождение памяти
        - Сохранение состояния
        """

    def has_capability(self, capability: ProviderCapability) -> bool:
        """Проверка поддержки конкретной возможности.

        Args:
            capability: Проверяемая возможность

        Returns:
            True если провайдер поддерживает эту возможность

        """
        return capability in self.capabilities

    @property
    def is_initialized(self) -> bool:
        """Проверка инициализации провайдера.

        Returns:
            True если провайдер инициализирован

        """
        return self._is_initialized
