"""Task State Manager - управление состоянием задач.

Отвечает ТОЛЬКО за управление состоянием задач в SessionStore.
НЕ отвечает за execution, webhooks (SRP).

Example:
    >>> manager = TaskStateManager(session_store)
    >>> await manager.mark_as_processing(task_id)
    >>> await manager.mark_as_completed(task_id, result)

"""

from typing import Any

from src.providers.base import GenerationResult
from src.services.session_store import SessionStore
from src.shared.logging import get_logger

logger = get_logger()


class TaskStateManager:
    """Manager для управления состоянием задач.

    Single Responsibility: управление state transitions.
    Тонкий wrapper над SessionStore с понятным API.

    Attributes:
        session_store: Session store для хранения состояния

    """

    def __init__(self, session_store: SessionStore) -> None:
        """Инициализировать TaskStateManager.

        Args:
            session_store: Session store instance

        """
        self.session_store = session_store
        logger.info("TaskStateManager инициализирован")

    async def mark_as_processing(self, task_id: str) -> None:
        """Отметить задачу как обрабатываемую.

        Args:
            task_id: ID задачи

        """
        await self.session_store.set_processing_task(task_id)
        await self.session_store.update_session_status(task_id, "processing")

        logger.debug("Задача отмечена как processing", task_id=task_id)

    async def mark_as_completed(
        self,
        task_id: str,
        result: GenerationResult,
    ) -> None:
        """Отметить задачу как завершённую успешно.

        Args:
            task_id: ID задачи
            result: Результат генерации

        """
        result_dict = {
            "text": result.text,
            "finish_reason": result.finish_reason,
            "usage": result.usage,
            "model": result.model,
            "extra": result.extra,
        }

        await self.session_store.update_session_status(
            task_id,
            "completed",
            result=result_dict,
        )

        logger.info(
            "Задача отмечена как completed",
            task_id=task_id,
            tokens=result.usage.get("total_tokens", 0),
        )

    async def mark_as_failed(
        self,
        task_id: str,
        error_message: str,
    ) -> None:
        """Отметить задачу как провалившуюся.

        Args:
            task_id: ID задачи
            error_message: Сообщение об ошибке

        """
        await self.session_store.update_session_status(
            task_id,
            "failed",
            error=error_message,
        )

        logger.error("Задача отмечена как failed", task_id=task_id, error=error_message)

    async def clear_processing(self) -> None:
        """Очистить processing task (вызывается в finally).

        Освобождает слот обработки для следующей задачи.
        """
        await self.session_store.clear_processing_task()

        logger.debug("Processing task slot освобождён")

    async def get_session(self, task_id: str) -> dict[str, Any] | None:
        """Получить данные сессии задачи.

        Args:
            task_id: ID задачи

        Returns:
            Данные сессии или None если не найдена

        """
        return await self.session_store.get_session(task_id)

    async def add_log(self, task_id: str, level: str, message: str) -> None:
        """Добавить лог к задаче.

        Args:
            task_id: ID задачи
            level: Уровень лога (INFO, ERROR, etc.)
            message: Сообщение

        """
        await self.session_store.add_log(task_id, level, message)
