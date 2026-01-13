"""Model Presets Loader - загрузка YAML пресетов.

Single Responsibility: только загрузка и парсинг YAML файлов.
Не выполняет скачивание моделей или проверку совместимости.
"""

from pathlib import Path

import yaml

from src.core.model_presets import (
    CloudModelPreset,
    EmbeddingModelPreset,
    LocalModelPreset,
)
from src.shared.logging import get_logger

logger = get_logger()


class ModelPresetsLoader:
    """Загрузчик YAML пресетов моделей.

    Single Responsibility: только загрузка и парсинг YAML файлов.

    Example:
        >>> loader = ModelPresetsLoader(Path("config/model_presets"))
        >>> loader.load()
        >>> preset = loader.get_local_preset("qwen2.5-7b-instruct")
        >>> print(preset.huggingface_repo)
        'Qwen/Qwen2.5-7B-Instruct-GGUF'

    """

    def __init__(self, presets_dir: Path) -> None:
        """Инициализировать загрузчик.

        Args:
            presets_dir: Путь к директории с YAML файлами пресетов

        """
        self._presets_dir = presets_dir
        self._local_presets: dict[str, LocalModelPreset] = {}
        self._cloud_presets: dict[str, CloudModelPreset] = {}
        self._embedding_presets: dict[str, EmbeddingModelPreset] = {}
        self._loaded = False

    def load(self) -> None:
        """Загрузить все YAML файлы пресетов.

        Raises:
            FileNotFoundError: Если директория не существует

        """
        if not self._presets_dir.exists():
            msg = f"Директория пресетов не найдена: {self._presets_dir}"
            raise FileNotFoundError(msg)

        self._load_local_models()
        self._load_cloud_models()
        self._load_embedding_models()
        self._loaded = True

        logger.info(
            "Пресеты загружены",
            local=len(self._local_presets),
            cloud=len(self._cloud_presets),
            embedding=len(self._embedding_presets),
        )

    def _load_local_models(self) -> None:
        """Загрузить пресеты локальных моделей."""
        yaml_path = self._presets_dir / "local_models.yaml"

        if not yaml_path.exists():
            logger.warning("Файл local_models.yaml не найден", path=str(yaml_path))
            return

        try:
            with yaml_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "models" not in data:
                logger.warning("Пустой или невалидный local_models.yaml")
                return

            for model_data in data["models"]:
                try:
                    preset = LocalModelPreset(**model_data)
                    self._local_presets[preset.name] = preset
                except Exception as e:
                    logger.warning(
                        "Ошибка парсинга локального пресета",
                        model=model_data.get("name", "unknown"),
                        error=str(e),
                    )

            logger.debug("Загружены локальные пресеты", count=len(self._local_presets))

        except Exception as e:
            logger.exception("Ошибка загрузки local_models.yaml", error=str(e))

    def _load_cloud_models(self) -> None:
        """Загрузить пресеты облачных моделей."""
        yaml_path = self._presets_dir / "cloud_models.yaml"

        if not yaml_path.exists():
            logger.warning("Файл cloud_models.yaml не найден", path=str(yaml_path))
            return

        try:
            with yaml_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "models" not in data:
                logger.warning("Пустой или невалидный cloud_models.yaml")
                return

            for model_data in data["models"]:
                try:
                    preset = CloudModelPreset(**model_data)
                    self._cloud_presets[preset.name] = preset
                except Exception as e:
                    logger.warning(
                        "Ошибка парсинга облачного пресета",
                        model=model_data.get("name", "unknown"),
                        error=str(e),
                    )

            logger.debug("Загружены облачные пресеты", count=len(self._cloud_presets))

        except Exception as e:
            logger.exception("Ошибка загрузки cloud_models.yaml", error=str(e))

    def _load_embedding_models(self) -> None:
        """Загрузить пресеты embedding моделей."""
        yaml_path = self._presets_dir / "embedding_models.yaml"

        if not yaml_path.exists():
            logger.warning("Файл embedding_models.yaml не найден", path=str(yaml_path))
            return

        try:
            with yaml_path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "models" not in data:
                logger.warning("Пустой или невалидный embedding_models.yaml")
                return

            for model_data in data["models"]:
                try:
                    preset = EmbeddingModelPreset(**model_data)
                    self._embedding_presets[preset.name] = preset
                except Exception as e:
                    logger.warning(
                        "Ошибка парсинга embedding пресета",
                        model=model_data.get("name", "unknown"),
                        error=str(e),
                    )

            logger.debug("Загружены embedding пресеты", count=len(self._embedding_presets))

        except Exception as e:
            logger.exception("Ошибка загрузки embedding_models.yaml", error=str(e))

    # Getters

    def get_local_preset(self, name: str) -> LocalModelPreset | None:
        """Получить пресет локальной модели по имени.

        Args:
            name: Имя пресета

        Returns:
            LocalModelPreset или None если не найден

        """
        return self._local_presets.get(name)

    def get_cloud_preset(self, name: str) -> CloudModelPreset | None:
        """Получить пресет облачной модели по имени.

        Args:
            name: Имя пресета

        Returns:
            CloudModelPreset или None если не найден

        """
        return self._cloud_presets.get(name)

    def get_embedding_preset(self, name: str) -> EmbeddingModelPreset | None:
        """Получить пресет embedding модели по имени.

        Args:
            name: Имя пресета

        Returns:
            EmbeddingModelPreset или None если не найден

        """
        return self._embedding_presets.get(name)

    def get_preset(self, name: str) -> LocalModelPreset | CloudModelPreset | EmbeddingModelPreset | None:
        """Получить любой пресет по имени.

        Ищет сначала в локальных, затем в облачных, затем в embedding.

        Args:
            name: Имя пресета

        Returns:
            Пресет или None если не найден

        """
        return self._local_presets.get(name) or self._cloud_presets.get(name) or self._embedding_presets.get(name)

    # Listers

    def list_local(self) -> list[LocalModelPreset]:
        """Получить список всех локальных пресетов."""
        return list(self._local_presets.values())

    def list_cloud(self) -> list[CloudModelPreset]:
        """Получить список всех облачных пресетов."""
        return list(self._cloud_presets.values())

    def list_embedding(self) -> list[EmbeddingModelPreset]:
        """Получить список всех embedding пресетов."""
        return list(self._embedding_presets.values())

    def list_local_names(self) -> list[str]:
        """Получить список имён локальных пресетов."""
        return list(self._local_presets.keys())

    def list_cloud_names(self) -> list[str]:
        """Получить список имён облачных пресетов."""
        return list(self._cloud_presets.keys())

    def list_embedding_names(self) -> list[str]:
        """Получить список имён embedding пресетов."""
        return list(self._embedding_presets.keys())

    @property
    def is_loaded(self) -> bool:
        """Проверить, загружены ли пресеты."""
        return self._loaded


# Initialize + Get паттерн (как SessionStore, ProviderRegistry)

_presets_loader: ModelPresetsLoader | None = None


def create_presets_loader(presets_dir: Path) -> ModelPresetsLoader:
    """Factory: создать и загрузить пресеты.

    Args:
        presets_dir: Путь к директории с YAML файлами

    Returns:
        Инициализированный ModelPresetsLoader

    """
    loader = ModelPresetsLoader(presets_dir)
    loader.load()
    return loader


def get_presets_loader() -> ModelPresetsLoader:
    """Получить singleton ModelPresetsLoader.

    Raises:
        RuntimeError: Если loader не инициализирован

    Returns:
        ModelPresetsLoader instance

    """
    if _presets_loader is None:
        msg = "ModelPresetsLoader не инициализирован. Вызовите set_presets_loader() в lifespan."
        raise RuntimeError(msg)
    return _presets_loader


def set_presets_loader(loader: ModelPresetsLoader) -> None:
    """Установить singleton ModelPresetsLoader.

    Вызывается в app.py lifespan при старте приложения.

    Args:
        loader: Инициализированный ModelPresetsLoader

    """
    global _presets_loader
    _presets_loader = loader
