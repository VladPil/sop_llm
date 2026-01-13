"""Model Defaults Configuration - дефолтные параметры для моделей.

Централизованная конфигурация дефолтных параметров генерации для разных моделей.
Избавляет от хардкода в коде.

Example:
    >>> from src.core.model_defaults import get_model_defaults
    >>> defaults = get_model_defaults("gpt-4")
    >>> # {'temperature': 0.7, 'max_tokens': 4096, ...}

See Also:
    - DOC-02-09: Стандарты документирования

"""

from typing import Any

# Глобальные defaults (применяются ко всем моделям, если не переопределено)
GLOBAL_DEFAULTS: dict[str, Any] = {
    "temperature": 0.1,  # Низкая температура = более детерминированный ответ
    "max_tokens": 2048,  # Средняя длина ответа
    "top_p": 1.0,  # Nucleus sampling отключен
    "top_k": 40,  # Top-K sampling
    "frequency_penalty": 0.0,  # Без штрафа за частоту
    "presence_penalty": 0.0,  # Без штрафа за присутствие
}

# Model-specific defaults (переопределяют GLOBAL_DEFAULTS)
MODEL_DEFAULTS: dict[str, dict[str, Any]] = {
    # === OpenAI Models ===
    "gpt-4": {
        "temperature": 0.7,  # GPT-4 лучше работает с более высокой температурой
        "max_tokens": 4096,  # Большой context window
        "top_p": 1.0,
    },
    "gpt-4-turbo": {
        "temperature": 0.7,
        "max_tokens": 8192,  # Ещё больше токенов
        "top_p": 1.0,
    },
    "gpt-3.5-turbo": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    # === Anthropic Models ===
    "claude-3-opus": {
        "temperature": 1.0,  # Claude рекомендует 1.0 для большинства задач
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    "claude-3-sonnet": {
        "temperature": 1.0,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    "claude-3-haiku": {
        "temperature": 1.0,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    # === Local Models (llama.cpp) ===
    "qwen2.5-7b-instruct": {
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.9,  # Nucleus sampling для локальных моделей
        "top_k": 40,
    },
    "llama-3.2-8b-instruct": {
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.9,
        "top_k": 40,
    },
    "mistral-7b-instruct": {
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.9,
        "top_k": 40,
    },
    # === Generic patterns (prefix matching) ===
    "gpt-": {  # Любая модель начинающаяся с "gpt-"
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    "claude-": {  # Любая модель начинающаяся с "claude-"
        "temperature": 1.0,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
}


def get_model_defaults(model_name: str) -> dict[str, Any]:
    """Получить дефолтные параметры для модели.

    Приоритет:
    1. Точное совпадение (MODEL_DEFAULTS[model_name])
    2. Prefix matching (MODEL_DEFAULTS["gpt-"] для "gpt-4-turbo")
    3. GLOBAL_DEFAULTS

    Args:
        model_name: Название модели

    Returns:
        Dict с дефолтными параметрами

    Example:
        >>> get_model_defaults("gpt-4")
        {'temperature': 0.7, 'max_tokens': 4096, 'top_p': 1.0, ...}

        >>> get_model_defaults("gpt-4-turbo-preview")  # Prefix match
        {'temperature': 0.7, 'max_tokens': 4096, 'top_p': 1.0, ...}

        >>> get_model_defaults("unknown-model")  # Global defaults
        {'temperature': 0.1, 'max_tokens': 2048, ...}

    """
    # Если модель не указана, вернуть глобальные defaults
    if model_name is None:
        return GLOBAL_DEFAULTS.copy()

    # 1. Точное совпадение
    if model_name in MODEL_DEFAULTS:
        # Merge с GLOBAL_DEFAULTS (model-specific переопределяет global)
        return {**GLOBAL_DEFAULTS, **MODEL_DEFAULTS[model_name]}

    # 2. Prefix matching
    for prefix, defaults in MODEL_DEFAULTS.items():
        if model_name.startswith(prefix):
            return {**GLOBAL_DEFAULTS, **defaults}

    # 3. Global defaults
    return GLOBAL_DEFAULTS.copy()


def register_model_defaults(model_name: str, defaults: dict[str, Any]) -> None:
    """Зарегистрировать кастомные defaults для модели.

    Используется для динамической регистрации моделей.

    Args:
        model_name: Название модели
        defaults: Дефолтные параметры

    Example:
        >>> register_model_defaults("my-custom-model", {
        ...     "temperature": 0.8,
        ...     "max_tokens": 1024,
        ... })

    """
    MODEL_DEFAULTS[model_name] = defaults


def list_model_defaults() -> dict[str, dict[str, Any]]:
    """Получить список всех зарегистрированных model defaults.

    Returns:
        Dict: {model_name: defaults}

    """
    return MODEL_DEFAULTS.copy()
