"""Model Presets Service Module.

Содержит сервисы для работы с пресетами моделей:
- ModelPresetsLoader - загрузка YAML пресетов
- CompatibilityChecker - проверка совместимости с GPU
- ModelDownloader - загрузка моделей с HuggingFace Hub

Архитектура следует SOLID принципам:
- Single Responsibility: каждый сервис выполняет одну задачу
- Open/Closed: Protocol ModelPreset позволяет добавлять новые типы
- Dependency Inversion: DI через конструкторы и FastAPI Depends
"""

from src.services.model_presets.compatibility import (
    CompatibilityChecker,
    CompatibilityResult,
    create_compatibility_checker,
    get_compatibility_checker,
    set_compatibility_checker,
)
from src.services.model_presets.downloader import (
    DownloadResult,
    ModelDownloader,
    create_model_downloader,
    get_model_downloader,
    set_model_downloader,
)
from src.services.model_presets.loader import (
    ModelPresetsLoader,
    create_presets_loader,
    get_presets_loader,
    set_presets_loader,
)

__all__ = [
    # Compatibility
    "CompatibilityChecker",
    "CompatibilityResult",
    "DownloadResult",
    # Downloader
    "ModelDownloader",
    # Loader
    "ModelPresetsLoader",
    "create_compatibility_checker",
    "create_model_downloader",
    "create_presets_loader",
    "get_compatibility_checker",
    "get_model_downloader",
    "get_presets_loader",
    "set_compatibility_checker",
    "set_model_downloader",
    "set_presets_loader",
]
