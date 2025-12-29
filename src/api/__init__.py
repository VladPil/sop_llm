"""SOP LLM - API Module.

Главный модуль API с версионированием.
"""

from fastapi import APIRouter

from src.api.v1 import router as v1_router
from src.core.constants import API_PREFIX

# Создаем главный API роутер
router = APIRouter()

# Подключаем роутеры разных версий
router.include_router(v1_router, prefix="/v1")

__all__ = ["router", "API_PREFIX"]
