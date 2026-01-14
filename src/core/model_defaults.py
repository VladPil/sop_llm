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

GLOBAL_DEFAULTS: dict[str, Any] = {
    "temperature": 0.1,
    "max_tokens": 2048,
    "top_p": 1.0,
    "top_k": 40,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
}

MODEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "gpt-4": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    "gpt-4-turbo": {
        "temperature": 0.7,
        "max_tokens": 8192,
        "top_p": 1.0,
    },
    "gpt-3.5-turbo": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    "claude-3-opus": {
        "temperature": 1.0,
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
    "qwen2.5-7b-instruct": {
        "temperature": 0.7,
        "max_tokens": 2048,
        "top_p": 0.9,
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
    "gpt-": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 1.0,
    },
    "claude-": {
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
    if model_name is None:
        return GLOBAL_DEFAULTS.copy()

    if model_name in MODEL_DEFAULTS:
        return {**GLOBAL_DEFAULTS, **MODEL_DEFAULTS[model_name]}

    for prefix, defaults in MODEL_DEFAULTS.items():
        if model_name.startswith(prefix):
            return {**GLOBAL_DEFAULTS, **defaults}

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
