"""SOP LLM - Core module.

Ядро приложения: конфигурация, константы, зависимости.
"""

from src.core.config import settings
from src.core.constants import (
    API_PREFIX,
    CACHE_PREFIX,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)

__all__ = [
    "settings",
    "API_PREFIX",
    "CACHE_PREFIX",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
]
