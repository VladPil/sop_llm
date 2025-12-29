"""Factory паттерн для создания и регистрации LLM провайдеров.

Следует Open/Closed Principle - можно расширять без модификации.
"""

from typing import Dict, List, Optional, Type

from src.modules.llm.providers.base import BaseLLMProvider


class LLMProviderFactory:
    """Фабрика для создания провайдеров.

    Использует Registry Pattern для динамической регистрации провайдеров.

    Принципы:
    - Open/Closed: новые провайдеры добавляются через регистрацию
    - Single Responsibility: только создание и управление провайдерами
    """

    _providers: Dict[str, Type[BaseLLMProvider]] = {}

    @classmethod
    def register(
        cls, provider_name: str, provider_class: Type[BaseLLMProvider]
    ) -> None:
        """Регистрация нового провайдера в фабрике.

        Args:
            provider_name: Уникальное имя провайдера
            provider_class: Класс провайдера (должен наследовать BaseLLMProvider)

        Raises:
            TypeError: Если класс не наследует BaseLLMProvider
        """
        if provider_name in cls._providers:
            # Разрешаем перезапись для development/testing
            # В production можно сделать raise ValueError
            pass

        if not issubclass(provider_class, BaseLLMProvider):
            raise TypeError(
                f"Provider class {provider_class.__name__} must inherit from BaseLLMProvider"
            )

        cls._providers[provider_name] = provider_class

    @classmethod
    def create(cls, provider_name: str, config: Dict) -> BaseLLMProvider:
        """Создание экземпляра провайдера.

        Args:
            provider_name: Имя провайдера
            config: Конфигурация провайдера

        Returns:
            Экземпляр провайдера

        Raises:
            ValueError: Если провайдер не зарегистрирован
        """
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available providers: {available}"
            )

        provider_class = cls._providers[provider_name]
        return provider_class(config)

    @classmethod
    def list_providers(cls) -> List[str]:
        """Получение списка зарегистрированных провайдеров.

        Returns:
            Список имён провайдеров
        """
        return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, provider_name: str) -> bool:
        """Проверка регистрации провайдера.

        Args:
            provider_name: Имя провайдера

        Returns:
            True если провайдер зарегистрирован
        """
        return provider_name in cls._providers

    @classmethod
    def get_provider_class(
        cls, provider_name: str
    ) -> Optional[Type[BaseLLMProvider]]:
        """Получение класса провайдера без создания экземпляра.

        Args:
            provider_name: Имя провайдера

        Returns:
            Класс провайдера или None если не зарегистрирован
        """
        return cls._providers.get(provider_name)

    @classmethod
    def clear_registry(cls) -> None:
        """Очистка реестра провайдеров.

        Используется в основном для тестирования.
        """
        cls._providers.clear()


def register_provider(name: str):
    """Декоратор для автоматической регистрации провайдера в фабрике.

    Использование:
        @register_provider("my_provider")
        class MyProvider(BaseLLMProvider):
            ...

    Args:
        name: Уникальное имя провайдера

    Returns:
        Декоратор функция
    """

    def decorator(cls: Type[BaseLLMProvider]) -> Type[BaseLLMProvider]:
        LLMProviderFactory.register(name, cls)
        return cls

    return decorator
