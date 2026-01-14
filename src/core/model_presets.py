"""Model Presets - Pydantic схемы для пресетов моделей.

Содержит:
- Protocol для duck typing пресетов
- Pydantic модели для локальных и облачных пресетов
- Config классы с точным маппингом на provider конструкторы

Маппинг полей:
- LocalProviderConfig -> LocalProvider (src/providers/local.py:44-50)
- CloudProviderConfig -> LiteLLMProvider (src/providers/litellm_provider.py:40-49)
"""

import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from src.core.enums import ProviderType


@runtime_checkable
class ModelPreset(Protocol):
    """Protocol для всех типов пресетов (duck typing).

    Реализуется LocalModelPreset и CloudModelPreset.
    Позволяет работать с пресетами единообразно (Liskov Substitution Principle).
    """

    name: str

    def to_register_config(self) -> dict:
        """Преобразовать пресет в config для _create_provider().

        Returns:
            dict с параметрами для конструктора provider'а

        """
        ...


class LocalProviderConfig(BaseModel):
    """Config который передаётся напрямую в LocalProvider.

    Поля точно соответствуют параметрам LocalProvider.__init__():
    - model_path -> LocalProvider.model_path
    - context_window -> LocalProvider.context_window
    - gpu_layers -> LocalProvider.gpu_layers
    """

    model_path: str | None = Field(
        default=None,
        description="Путь к GGUF файлу. Если None, вычисляется из models_dir + filename",
    )

    context_window: int = Field(
        default=4096,
        ge=512,
        le=131072,
        description="Размер контекстного окна модели",
    )

    gpu_layers: int = Field(
        default=-1,
        ge=-1,
        description="Количество слоёв на GPU. -1 = все слои на GPU, 0 = CPU only",
    )


class CloudProviderConfig(BaseModel):
    """Config который передаётся напрямую в LiteLLMProvider.

    Поля точно соответствуют параметрам LiteLLMProvider.__init__():
    - model_name -> LiteLLMProvider.model_name
    - api_key -> LiteLLMProvider.api_key
    - base_url -> LiteLLMProvider.base_url
    - timeout -> LiteLLMProvider.timeout
    - max_retries -> LiteLLMProvider.max_retries
    - keep_alive -> LiteLLMProvider.keep_alive (для Ollama)
    """

    model_name: str = Field(
        description="ID модели в API провайдера (e.g. 'claude-3-5-sonnet-20241022', 'gpt-4-turbo')",
    )

    api_key: str | None = Field(
        default=None,
        description="API ключ. Если None, берётся из env variable (api_key_env_var)",
    )

    base_url: str | None = Field(
        default=None,
        description="Custom base URL для API (опционально)",
    )

    timeout: int = Field(
        default=600,
        ge=1,
        le=3600,
        description="Таймаут запроса в секундах",
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Максимальное количество повторных попыток",
    )

    keep_alive: str | None = Field(
        default=None,
        description="Время удержания модели в памяти для Ollama (e.g. '5m', '1h', '-1' для бесконечно)",
    )


class LocalModelPreset(BaseModel):
    """Пресет локальной GGUF модели.

    Содержит:
    - Метаданные для идентификации и загрузки
    - Информацию о GPU совместимости
    - Provider config который маппится напрямую в LocalProvider

    Example YAML:
        name: "qwen2.5-7b-instruct"
        huggingface_repo: "Qwen/Qwen2.5-7B-Instruct-GGUF"
        filename: "qwen2.5-7b-instruct-q4_k_m.gguf"
        size_b: 7
        vram_requirements:
          q4_k_m: 5500
          q5_k_m: 6500
          q8_0: 9000
          fp16: 14000
        provider_config:
          context_window: 32768
          gpu_layers: -1
    """

    # Идентификация
    name: str = Field(
        description="Уникальное имя для registry (e.g. 'qwen2.5-7b-instruct')",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )

    # Загрузка с HuggingFace
    huggingface_repo: str = Field(
        description="HuggingFace репозиторий (e.g. 'Qwen/Qwen2.5-7B-Instruct-GGUF')",
    )

    filename: str = Field(
        description="Имя GGUF файла в репозитории (e.g. 'qwen2.5-7b-instruct-q4_k_m.gguf')",
    )

    # GPU совместимость
    size_b: float = Field(
        gt=0,
        description="Размер модели в миллиардах параметров (e.g. 7 для 7B модели)",
    )

    vram_requirements: dict[str, int] = Field(
        description="Требования VRAM в MB для разных квантизаций: {'q4_k_m': 5500, 'q8_0': 9000}",
    )

    # Provider config (маппится напрямую в LocalProvider)
    provider_config: LocalProviderConfig = Field(
        default_factory=LocalProviderConfig,
        description="Конфигурация для LocalProvider",
    )

    def to_register_config(self, models_dir: Path | None = None) -> dict:
        """Преобразовать в config для _create_provider().

        Args:
            models_dir: Директория с моделями. Если указана, вычисляется model_path.

        Returns:
            dict с параметрами для LocalProvider

        """
        model_path = self.provider_config.model_path
        if model_path is None and models_dir is not None:
            model_path = str(models_dir / self.filename)

        return {
            "model_path": model_path,
            "context_window": self.provider_config.context_window,
            "gpu_layers": self.provider_config.gpu_layers,
        }


class CloudModelPreset(BaseModel):
    """Пресет облачной модели.

    Содержит:
    - Метаданные для идентификации
    - Информацию о провайдере и API ключе
    - Provider config который маппится напрямую в LiteLLMProvider

    Example YAML:
        name: "claude-3.5-sonnet"
        provider: "anthropic"
        api_key_env_var: "ANTHROPIC_API_KEY"
        provider_config:
          model_name: "claude-3-5-sonnet-20241022"
          timeout: 600
          max_retries: 3
    """

    # Идентификация
    name: str = Field(
        description="Уникальное имя для registry",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._:-]+$",  # : для Ollama моделей (qwen2.5:3b)
    )

    provider: ProviderType = Field(
        description="Тип провайдера: openai, anthropic, openai_compatible, ollama",
    )

    # API ключ (опционально для Ollama)
    api_key_env_var: str | None = Field(
        default=None,
        description="Имя env variable с API ключом (e.g. 'ANTHROPIC_API_KEY'). None для Ollama.",
    )

    # Provider config (маппится напрямую в LiteLLMProvider)
    provider_config: CloudProviderConfig = Field(
        description="Конфигурация для LiteLLMProvider",
    )

    def to_register_config(self) -> dict:
        """Преобразовать в config для _create_provider().

        Returns:
            dict с параметрами для LiteLLMProvider

        Note:
            api_key берётся из provider_config или из env variable

        """
        api_key = self.provider_config.api_key
        if api_key is None and self.api_key_env_var is not None:
            api_key = os.getenv(self.api_key_env_var)

        config = {
            "model_name": self.provider_config.model_name,
            "api_key": api_key,
            "base_url": self.provider_config.base_url,
            "timeout": self.provider_config.timeout,
            "max_retries": self.provider_config.max_retries,
        }

        # Добавить keep_alive для Ollama
        if self.provider_config.keep_alive is not None:
            config["keep_alive"] = self.provider_config.keep_alive

        return config


class EmbeddingModelPreset(BaseModel):
    """Пресет embedding модели.

    Example YAML:
        name: "multilingual-e5-large"
        huggingface_repo: "intfloat/multilingual-e5-large"
        dimensions: 1024
    """

    name: str = Field(
        description="Уникальное имя для registry",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )

    huggingface_repo: str = Field(
        description="HuggingFace репозиторий модели",
    )

    dimensions: int = Field(
        gt=0,
        description="Размерность векторов (e.g. 1024 для multilingual-e5-large)",
    )
