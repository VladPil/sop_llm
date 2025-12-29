"""Провайдеры для работы с различными LLM.

Доступные провайдеры:
- local: Локальные модели через HuggingFace Transformers
- claude: Anthropic Claude API
- lm_studio: LM Studio (OpenAI-compatible API)
"""

from src.modules.llm.providers.base import BaseLLMProvider, ProviderCapability
from src.modules.llm.providers.factory import LLMProviderFactory, register_provider

# Импортируем провайдеры для автоматической регистрации
from src.modules.llm.providers.claude_provider_new import ClaudeProvider
from src.modules.llm.providers.lm_studio_provider import LMStudioProvider
from src.modules.llm.providers.local_provider import LocalLLMProvider

__all__ = [
    "BaseLLMProvider",
    "ProviderCapability",
    "LLMProviderFactory",
    "register_provider",
    "LocalLLMProvider",
    "ClaudeProvider",
    "LMStudioProvider",
]
