"""Model Presets Service Module.

Содержит сервисы для работы с пресетами моделей:
- ModelPresetsLoader - загрузка YAML пресетов
- CompatibilityChecker - проверка совместимости с GPU

Архитектура следует SOLID принципам:
- Single Responsibility: каждый сервис выполняет одну задачу
- Open/Closed: Protocol ModelPreset позволяет добавлять новые типы
- Dependency Inversion: DI через конструкторы и FastAPI Depends

Note:
    Локальные модели теперь обслуживаются через Ollama + LiteLLM.
    HuggingFace downloader удалён - скачивание моделей не требуется.

"""

from src.services.model_presets.compatibility import (
    CompatibilityChecker,
    CompatibilityResult,
    create_compatibility_checker,
    get_compatibility_checker,
    set_compatibility_checker,
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
    # Loader
    "ModelPresetsLoader",
    "create_compatibility_checker",
    "create_presets_loader",
    "get_compatibility_checker",
    "get_presets_loader",
    "set_compatibility_checker",
    "set_presets_loader",
]
