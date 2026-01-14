"""Provider Registry для SOP LLM Executor.

Централизованное хранилище providers с lazy loading.
Поддерживает как LLM providers, так и Embedding providers.
"""

from typing import TYPE_CHECKING, Any

from src.providers.base import ModelInfo
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.services.model_presets.loader import ModelPresetsLoader

logger = get_logger()


class ProviderRegistry:
    """Registry для управления LLM и Embedding providers.

    Паттерн: Registry + Singleton + Lazy Loading
    - Хранит зарегистрированные providers
    - Lazy loading: создаёт providers при первом запросе из пресетов
    - Обеспечивает единую точку доступа к providers
    - Поддерживает LLM и Embedding providers
    """

    def __init__(self) -> None:
        """Инициализировать пустой registry."""
        self._providers: dict[str, Any] = {}
        self._presets_loader: ModelPresetsLoader | None = None

    def set_presets_loader(self, loader: "ModelPresetsLoader") -> None:
        """Установить ссылку на ModelPresetsLoader для lazy loading.

        Args:
            loader: Инициализированный ModelPresetsLoader

        """
        self._presets_loader = loader
        logger.info("ProviderRegistry: presets_loader установлен")

    def register(self, name: str, provider: Any) -> None:
        """Зарегистрировать provider.

        Args:
            name: Название provider (например, "qwen2.5-7b-instruct")
            provider: Instance provider'а (LLMProvider или EmbeddingProvider)

        Raises:
            ValueError: Если provider с таким именем уже зарегистрирован

        """
        if name in self._providers:
            msg = f"Provider '{name}' уже зарегистрирован"
            raise ValueError(msg)

        # Проверить базовые требования: должен иметь хотя бы один из методов
        has_generate = hasattr(provider, "generate")
        has_embeddings = hasattr(provider, "generate_embeddings")

        if not has_generate and not has_embeddings:
            msg = f"Provider '{name}' должен реализовать generate() или generate_embeddings()"
            raise TypeError(msg)

        self._providers[name] = provider

        provider_kind = "embedding" if has_embeddings and not has_generate else "llm"
        logger.info("Provider зарегистрирован", name=name, provider_type=type(provider).__name__, kind=provider_kind)

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

    def get(self, name: str) -> Any:
        """Получить provider по имени (без lazy loading).

        Args:
            name: Название provider

        Returns:
            Provider instance (LLMProvider или EmbeddingProvider)

        Raises:
            KeyError: Если provider не найден

        """
        if name not in self._providers:
            available = ", ".join(self._providers.keys()) or "нет доступных"
            msg = f"Provider '{name}' не найден. Доступные: {available}"
            raise KeyError(msg)

        return self._providers[name]

    def get_or_create(self, name: str) -> Any:
        """Получить provider или создать из пресета (lazy loading).

        Основной метод для получения LLM провайдеров.
        Если провайдер уже зарегистрирован - возвращает его.
        Иначе ищет пресет и создаёт провайдер автоматически.

        Args:
            name: Название модели/провайдера (должно совпадать с именем пресета)

        Returns:
            Provider instance

        Raises:
            KeyError: Если провайдер не найден и пресет не существует
            RuntimeError: Если presets_loader не установлен

        """
        # Если уже зарегистрирован - вернуть
        if name in self._providers:
            return self._providers[name]

        # Lazy loading: создать из пресета
        if self._presets_loader is None:
            msg = "presets_loader не установлен. Вызовите set_presets_loader() в lifespan."
            raise RuntimeError(msg)

        # Ищем в облачных пресетах
        preset = self._presets_loader.get_cloud_preset(name)
        if preset is None:
            available_presets = self._presets_loader.list_cloud_names()
            available = ", ".join(available_presets) or "нет доступных"
            msg = f"Модель '{name}' не найдена в пресетах. Доступные: {available}"
            raise KeyError(msg)

        # Создать provider из пресета
        provider = self._create_cloud_provider(preset)
        self._providers[name] = provider

        logger.info(
            "Provider создан lazy loading",
            name=name,
            provider_type=type(provider).__name__,
        )

        return provider

    def _create_cloud_provider(self, preset: Any) -> Any:
        """Создать LiteLLMProvider из CloudModelPreset.

        Args:
            preset: CloudModelPreset с конфигурацией

        Returns:
            LiteLLMProvider instance

        """
        from src.providers.litellm_provider import LiteLLMProvider

        config = preset.to_register_config()
        return LiteLLMProvider(**config)

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

        Note:
            Embedding провайдеры пропускаются (они не имеют get_model_info).

        """
        models_info: dict[str, ModelInfo] = {}

        for name, provider in self._providers.items():
            # Пропустить embedding провайдеры
            if not hasattr(provider, "get_model_info"):
                continue

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


def set_provider_registry(registry: ProviderRegistry) -> None:
    """Установить глобальный provider registry.

    Используется для тестирования и замены registry.

    Args:
        registry: Новый экземпляр ProviderRegistry

    """
    global provider_registry
    provider_registry = registry
    logger.info("ProviderRegistry установлен глобально")
