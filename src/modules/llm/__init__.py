"""LLM Module - модуль для работы с языковыми моделями.

Включает:
- Providers: различные провайдеры LLM (local, claude, lm_studio)
- Formatters: форматирование промптов и парсинг ответов
- Services: высокоуровневые сервисы (managers, json fixer, unified interface)
- Schemas: схемы для валидации данных
"""

from src.modules.llm import formatters, providers, schemas, services

# Основные экспорты для удобства использования
from src.modules.llm.providers import (
    BaseLLMProvider,
    ClaudeProvider,
    LMStudioProvider,
    LocalLLMProvider,
    ProviderCapability,
)
from src.modules.llm.services import (
    EmbeddingManager,
    JSONFixerManager,
    LLMManager,
    ProviderManager,
    UnifiedLLM,
    embedding_manager,
    json_fixer,
    llm_manager,
    provider_manager,
    unified_llm,
)

__all__ = [
    # Submodules
    "providers",
    "formatters",
    "services",
    "schemas",
    # Providers
    "BaseLLMProvider",
    "ProviderCapability",
    "LocalLLMProvider",
    "ClaudeProvider",
    "LMStudioProvider",
    # Services - Classes
    "LLMManager",
    "EmbeddingManager",
    "JSONFixerManager",
    "ProviderManager",
    "UnifiedLLM",
    # Services - Instances
    "llm_manager",
    "embedding_manager",
    "json_fixer",
    "provider_manager",
    "unified_llm",
]
