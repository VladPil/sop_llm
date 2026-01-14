"""Embedding Manager - управление embedding моделями с FIFO eviction.

Lazy loading embedding моделей с автоматическим вытеснением
при нехватке VRAM (First In First Out).
"""

from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from src.providers.embedding import SentenceTransformerProvider
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.core.model_presets import EmbeddingModelPreset
    from src.services.model_presets.loader import ModelPresetsLoader

logger = get_logger()

EMBEDDING_VRAM_REQUIREMENTS: dict[str, int] = {
    "multilingual-e5-large": 2200,
    "multilingual-e5-base": 1100,
    "multilingual-e5-small": 500,
    "all-MiniLM-L6-v2": 300,
    "all-mpnet-base-v2": 500,
    "paraphrase-multilingual-MiniLM-L12-v2": 500,
    "bge-m3": 2500,
    "bge-large-en-v1.5": 1500,
    "bge-base-en-v1.5": 500,
    "jina-embeddings-v2-base-en": 600,
    "jina-embeddings-v2-small-en": 400,
}

DEFAULT_VRAM_REQUIREMENT_MB = 1000


class EmbeddingManager:
    """Менеджер embedding моделей с lazy loading и FIFO eviction.

    Особенности:
    - Lazy loading: модели загружаются при первом запросе
    - FIFO eviction: при нехватке VRAM удаляется самая старая модель
    - Интеграция с VRAMMonitor для отслеживания памяти
    - Поддержка device selection (cuda/cpu)

    Example:
        >>> manager = EmbeddingManager(presets_loader, device="cuda")
        >>> provider = await manager.get_or_load("multilingual-e5-large")
        >>> embeddings = await provider.generate_embeddings(["text1", "text2"])

    """

    def __init__(
        self,
        presets_loader: "ModelPresetsLoader",
        device: str = "cuda",
        max_loaded_models: int = 5,
    ) -> None:
        """Инициализация EmbeddingManager.

        Args:
            presets_loader: Загрузчик пресетов моделей
            device: Устройство для моделей ('cuda', 'cpu')
            max_loaded_models: Максимум загруженных моделей (soft limit)

        """
        self._presets_loader = presets_loader
        self._device = device
        self._max_loaded_models = max_loaded_models
        self._loaded_models: OrderedDict[str, SentenceTransformerProvider] = OrderedDict()
        self._vram_monitor: Any = None

        logger.info(
            "EmbeddingManager инициализирован",
            device=device,
            max_loaded=max_loaded_models,
        )

    def set_vram_monitor(self, monitor: Any) -> None:
        """Установить VRAMMonitor для отслеживания VRAM.

        Args:
            monitor: Экземпляр VRAMMonitor

        """
        self._vram_monitor = monitor
        logger.info("EmbeddingManager: VRAMMonitor установлен")

    async def get_or_load(self, model_name: str) -> SentenceTransformerProvider:
        """Получить или загрузить embedding модель.

        Основной метод для получения embedding провайдеров.
        При необходимости выполняет FIFO eviction.

        Args:
            model_name: Имя модели (должно совпадать с именем пресета)

        Returns:
            Загруженный SentenceTransformerProvider

        Raises:
            KeyError: Если пресет модели не найден
            RuntimeError: Если не удалось загрузить модель

        """
        if model_name in self._loaded_models:
            self._loaded_models.move_to_end(model_name)
            logger.debug("Embedding модель уже загружена", model=model_name)
            return self._loaded_models[model_name]

        preset = self._presets_loader.get_embedding_preset(model_name)
        if preset is None:
            available = self._presets_loader.list_embedding_names()
            msg = f"Embedding модель '{model_name}' не найдена. Доступные: {', '.join(available)}"
            raise KeyError(msg)

        required_mb = self._get_vram_requirement(model_name)
        await self._ensure_vram_available(required_mb)

        provider = await self._load_model(preset)
        self._loaded_models[model_name] = provider

        logger.info(
            "Embedding модель загружена",
            model=model_name,
            loaded_count=len(self._loaded_models),
        )

        return provider

    def _get_vram_requirement(self, model_name: str) -> int:
        """Получить требуемый VRAM для модели.

        Args:
            model_name: Имя модели

        Returns:
            Требуемый VRAM в MB

        """
        return EMBEDDING_VRAM_REQUIREMENTS.get(model_name, DEFAULT_VRAM_REQUIREMENT_MB)

    async def _ensure_vram_available(self, required_mb: int) -> None:
        """Обеспечить наличие свободного VRAM, выполнив eviction если нужно.

        Args:
            required_mb: Требуемый VRAM в MB

        """
        if self._vram_monitor is None or self._device == "cpu":
            while len(self._loaded_models) >= self._max_loaded_models:
                await self._evict_oldest()
            return

        eviction_attempts = 0
        max_evictions = len(self._loaded_models)

        while eviction_attempts < max_evictions:
            if self._vram_monitor.can_allocate(required_mb):
                return

            if not self._loaded_models:
                logger.warning(
                    "Недостаточно VRAM и нечего выгружать",
                    required_mb=required_mb,
                )
                return

            await self._evict_oldest()
            eviction_attempts += 1

        logger.warning(
            "Выполнено максимум eviction попыток",
            attempts=eviction_attempts,
            required_mb=required_mb,
        )

    async def _evict_oldest(self) -> None:
        """Выгрузить самую старую модель (FIFO).

        Удаляет первый элемент из OrderedDict.
        """
        if not self._loaded_models:
            return

        oldest_name, oldest_provider = self._loaded_models.popitem(last=False)
        logger.info("FIFO eviction: выгрузка embedding модели", model=oldest_name)

        try:
            await oldest_provider.cleanup()
        except Exception as e:
            logger.warning(
                "Ошибка cleanup при eviction",
                model=oldest_name,
                error=str(e),
            )

    async def _load_model(self, preset: "EmbeddingModelPreset") -> SentenceTransformerProvider:
        """Загрузить модель по пресету.

        Args:
            preset: Пресет embedding модели

        Returns:
            Загруженный provider

        """
        provider = SentenceTransformerProvider(
            model_name=preset.huggingface_repo,
            device=self._device,
            normalize_embeddings=True,
        )

        await provider.load()
        return provider

    async def unload(self, model_name: str) -> bool:
        """Выгрузить конкретную модель.

        Args:
            model_name: Имя модели для выгрузки

        Returns:
            True если модель была выгружена, False если не была загружена

        """
        if model_name not in self._loaded_models:
            return False

        provider = self._loaded_models.pop(model_name)

        try:
            await provider.cleanup()
            logger.info("Embedding модель выгружена", model=model_name)
            return True
        except Exception as e:
            logger.warning(
                "Ошибка при выгрузке embedding модели",
                model=model_name,
                error=str(e),
            )
            return False

    async def cleanup(self) -> None:
        """Выгрузить все модели."""
        logger.info("EmbeddingManager cleanup: выгрузка всех моделей")

        for model_name in list(self._loaded_models.keys()):
            await self.unload(model_name)

    def list_loaded(self) -> list[str]:
        """Получить список загруженных моделей (в порядке FIFO).

        Returns:
            Список имён загруженных моделей

        """
        return list(self._loaded_models.keys())

    def get_info(self) -> dict[str, Any]:
        """Получить информацию о состоянии менеджера.

        Returns:
            Словарь с метаданными

        """
        loaded_info = {}
        for name, provider in self._loaded_models.items():
            loaded_info[name] = provider.get_info()

        return {
            "device": self._device,
            "max_loaded_models": self._max_loaded_models,
            "loaded_count": len(self._loaded_models),
            "loaded_models": self.list_loaded(),
            "models_info": loaded_info,
        }


_embedding_manager: EmbeddingManager | None = None


def get_embedding_manager() -> EmbeddingManager:
    """Получить глобальный EmbeddingManager instance.

    Raises:
        RuntimeError: Если менеджер не инициализирован

    Returns:
        EmbeddingManager instance

    """
    if _embedding_manager is None:
        msg = "EmbeddingManager не инициализирован. Вызовите set_embedding_manager() в lifespan."
        raise RuntimeError(msg)
    return _embedding_manager


def set_embedding_manager(manager: EmbeddingManager) -> None:
    """Установить глобальный EmbeddingManager instance.

    Args:
        manager: Инициализированный EmbeddingManager

    """
    global _embedding_manager
    _embedding_manager = manager
    logger.info("EmbeddingManager установлен глобально")
