"""Provider Registry для SOP LLM Executor.

Централизованное хранилище providers с динамической регистрацией.
"""

from src.providers.base import LLMProvider, ModelInfo
from src.shared.logging import get_logger

logger = get_logger()


class ProviderRegistry:
    """Registry для управления LLM providers.

    Паттерн: Registry + Singleton
    - Хранит зарегистрированные providers
    - Поддерживает динамическую регистрацию
    - Обеспечивает единую точку доступа к providers
    """

    def __init__(self) -> None:
        """Инициализировать пустой registry."""
        self._providers: dict[str, LLMProvider] = {}

    def register(self, name: str, provider: LLMProvider) -> None:
        """Зарегистрировать provider.

        Args:
            name: Название provider (например, "qwen2.5-7b-instruct")
            provider: Instance provider'а

        Raises:
            ValueError: Если provider с таким именем уже зарегистрирован

        """
        if name in self._providers:
            msg = f"Provider '{name}' уже зарегистрирован"
            raise ValueError(msg)

        # Проверить, что provider реализует Protocol
        if not isinstance(provider, LLMProvider):
            msg = f"Provider '{name}' не реализует LLMProvider Protocol"
            raise TypeError(msg)

        self._providers[name] = provider

        logger.info("Provider зарегистрирован", name=name, provider_type=type(provider).__name__)

    def unregister(self, name: str) -> None:
        """Удалить provider из registry.

        Args:
            name: Название provider

        Raises:
            KeyError: Если provider не найден

        """
        if name not in self._providers:
            msg = f"Provider '{name}' не найден в registry"
            raise KeyError(msg)

        del self._providers[name]

        logger.info("Provider удалён из registry", name=name)

    def get(self, name: str) -> LLMProvider:
        """Получить provider по имени.

        Args:
            name: Название provider

        Returns:
            Provider instance

        Raises:
            KeyError: Если provider не найден

        """
        if name not in self._providers:
            available = ", ".join(self._providers.keys()) or "нет доступных"
            msg = f"Provider '{name}' не найден. Доступные: {available}"
            raise KeyError(msg)

        return self._providers[name]

    def list_providers(self) -> list[str]:
        """Получить список всех зарегистрированных providers.

        Returns:
            Список названий providers

        """
        return list(self._providers.keys())

    async def get_all_models_info(self) -> dict[str, ModelInfo]:
        """Получить метаданные всех зарегистрированных моделей.

        Returns:
            Словарь {model_name: ModelInfo}

        """
        models_info: dict[str, ModelInfo] = {}

        for name, provider in self._providers.items():
            try:
                info = await provider.get_model_info()
                models_info[name] = info
            except Exception as e:
                logger.exception(
                    "Не удалось получить info для модели",
                    model=name,
                    error=str(e),
                )

        return models_info

    async def health_check_all(self) -> dict[str, bool]:
        """Проверить доступность всех providers.

        Returns:
            Словарь {provider_name: is_healthy}

        """
        health_status: dict[str, bool] = {}

        for name, provider in self._providers.items():
            try:
                is_healthy = await provider.health_check()
                health_status[name] = is_healthy
            except Exception as e:
                logger.exception(
                    "Health check failed для provider",
                    provider=name,
                    error=str(e),
                )
                health_status[name] = False

        return health_status

    async def cleanup_all(self) -> None:
        """Очистить ресурсы всех providers (при shutdown)."""
        for name, provider in self._providers.items():
            try:
                await provider.cleanup()
                logger.info("Provider cleanup выполнен", name=name)
            except Exception as e:
                logger.exception(
                    "Ошибка cleanup для provider",
                    provider=name,
                    error=str(e),
                )

    def __len__(self) -> int:
        """Количество зарегистрированных providers."""
        return len(self._providers)

    def __contains__(self, name: str) -> bool:
        """Проверить, зарегистрирован ли provider."""
        return name in self._providers


provider_registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    """Получить глобальный provider registry.

    Returns:
        Singleton instance ProviderRegistry

    """
    return provider_registry
