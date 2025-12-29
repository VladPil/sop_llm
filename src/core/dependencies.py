"""SOP LLM - Dependencies.

Dependency Injection для FastAPI.
"""

from typing import Annotated, Any, Dict, Optional

from fastapi import Depends, Request

from src.shared.cache.redis_cache import RedisCache

# Импорты из новой структуры
from src.modules.llm.services import (
    EmbeddingManager,
    embedding_manager,
    JSONFixerManager,
    json_fixer,
    LLMManager,
    llm_manager,
    ProviderManager,
    provider_manager,
    UnifiedLLM,
    unified_llm,
)
from src.core.config import settings


# ==================== Manager Dependencies ====================


def get_llm_manager() -> LLMManager:
    """Предоставляет LLM manager instance.

    Returns:
        LLM manager instance.

    """
    return llm_manager


def get_embedding_manager() -> EmbeddingManager:
    """Предоставляет Embedding manager instance.

    Returns:
        Embedding manager instance.

    """
    return embedding_manager


def get_unified_llm() -> UnifiedLLM:
    """Предоставляет Unified LLM interface.

    Returns:
        Unified LLM instance.

    """
    return unified_llm


def get_json_fixer() -> JSONFixerManager:
    """Предоставляет JSON Fixer manager instance.

    Returns:
        JSON Fixer manager instance.

    """
    return json_fixer


def get_provider_manager() -> ProviderManager:
    """Предоставляет Provider Manager instance.

    Новая архитектура с поддержкой множественных провайдеров:
    - local (Qwen модели)
    - claude (Claude API)
    - lm_studio (LM Studio)

    Returns:
        Provider manager instance.

    """
    return provider_manager


# ==================== Cache Dependencies ====================


async def get_redis_cache(request: Request) -> RedisCache:
    """Получить Redis кэш из состояния приложения.

    Args:
        request: HTTP запрос FastAPI.

    Returns:
        Экземпляр RedisCache.

    """
    return request.app.state.redis_cache


# ==================== Configuration Dependencies ====================


def get_settings():
    """Предоставляет application settings.

    Returns:
        Settings instance.

    """
    return settings


# ==================== Storage Dependencies ====================


class TaskStorage:
    """In-memory task storage.

    Заменяет глобальный dict tasks_storage из routes.py.
    В будущем можно заменить на Redis или DB storage.

    """

    def __init__(self) -> None:
        """Инициализация хранилища."""
        self._storage: Dict[str, Dict[str, Any]] = {}

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получить задачу по ID.

        Args:
            task_id: ID задачи.

        Returns:
            Данные задачи или None.

        """
        return self._storage.get(task_id)

    def set(self, task_id: str, data: Dict[str, Any]) -> None:
        """Сохранить задачу.

        Args:
            task_id: ID задачи.
            data: Данные задачи.

        """
        self._storage[task_id] = data

    def delete(self, task_id: str) -> None:
        """Удалить задачу.

        Args:
            task_id: ID задачи.

        """
        if task_id in self._storage:
            del self._storage[task_id]

    def exists(self, task_id: str) -> bool:
        """Проверить существование задачи.

        Args:
            task_id: ID задачи.

        Returns:
            True если задача существует.

        """
        return task_id in self._storage

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Получить все задачи.

        Returns:
            Копия всех задач.

        """
        return self._storage.copy()


# Глобальный singleton storage (заменяет tasks_storage из routes.py)
_task_storage = TaskStorage()


def get_task_storage() -> TaskStorage:
    """Предоставляет task storage instance.

    Returns:
        Task storage instance.

    """
    return _task_storage


# ==================== Type Aliases ====================
# Используются для более чистого кода в route handlers

LLMManagerDep = Annotated[LLMManager, Depends(get_llm_manager)]
EmbeddingManagerDep = Annotated[EmbeddingManager, Depends(get_embedding_manager)]
UnifiedLLMDep = Annotated[UnifiedLLM, Depends(get_unified_llm)]
JSONFixerDep = Annotated[JSONFixerManager, Depends(get_json_fixer)]
ProviderManagerDep = Annotated[ProviderManager, Depends(get_provider_manager)]
RedisCacheDep = Annotated[RedisCache, Depends(get_redis_cache)]
TaskStorageDep = Annotated[TaskStorage, Depends(get_task_storage)]
