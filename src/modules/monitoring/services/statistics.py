"""Task statistics service for real-time monitoring.

Менеджер статистики для отслеживания задач в реальном времени.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from loguru import logger


def serialize_for_json(obj: Any) -> Any:
    """Recursively convert object for JSON serialization.

    Рекурсивно преобразует объект для JSON сериализации.

    Args:
        obj: Object to convert.

    Returns:
        JSON-serializable object.

    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [serialize_for_json(item) for item in obj]
    return obj


class TaskStatistics:
    """Manager for tracking task statistics in real-time.

    Менеджер для отслеживания статистики задач в реальном времени.
    """

    def __init__(self) -> None:
        """Initialize task statistics manager."""
        self._tasks: dict[str, dict[str, Any]] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._stats: dict[str, int | float] = {
            "total_tasks": 0,
            "pending_tasks": 0,
            "processing_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_errors": 0,
            "avg_processing_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }
        self._errors_log: list[dict[str, Any]] = []
        self._max_errors_log: int = 100

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to statistics updates.

        Подписка на обновления статистики.

        Returns:
            Queue for receiving updates.

        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        logger.info(f"New subscriber added. Total subscribers: {len(self._subscribers)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from statistics updates.

        Отписка от обновлений статистики.

        Args:
            queue: Queue to remove.

        """
        self._subscribers.discard(queue)
        logger.info(f"Subscriber removed. Total subscribers: {len(self._subscribers)}")

    async def _notify_subscribers(self, event_type: str, data: dict[str, Any]) -> None:
        """Notify all subscribers about an event.

        Уведомление всех подписчиков о событии.

        Args:
            event_type: Event type.
            data: Event data.

        """
        if not self._subscribers:
            return

        # Serialize data before sending
        serialized_data = serialize_for_json(data)

        message = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": serialized_data,
        }

        # Remove disconnected subscribers
        disconnected: set[asyncio.Queue] = set()

        for queue in self._subscribers:
            try:
                # Don't block if queue is full
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue is full, skipping message")
            except Exception:
                logger.exception("Error notifying subscriber")
                disconnected.add(queue)

        # Remove disconnected subscribers
        for queue in disconnected:
            self._subscribers.discard(queue)

    def task_created(self, task_id: str, task_data: dict[str, Any]) -> None:
        """Register task creation.

        Регистрация создания задачи.

        Args:
            task_id: Task ID.
            task_data: Task data.

        """
        self._tasks[task_id] = {
            **task_data,
            "created_at": datetime.now(UTC),
            "status": "pending",
        }
        self._stats["total_tasks"] += 1
        self._stats["pending_tasks"] += 1

        asyncio.create_task(
            self._notify_subscribers(
                "task_created",
                {
                    "task_id": task_id,
                    "task": self._tasks[task_id],
                    "stats": self._stats.copy(),
                },
            )
        )

    def task_started(self, task_id: str) -> None:
        """Register task processing start.

        Регистрация начала обработки задачи.

        Args:
            task_id: Task ID.

        """
        if task_id not in self._tasks:
            logger.warning(f"Task {task_id} not found in statistics")
            return

        self._tasks[task_id]["status"] = "processing"
        self._tasks[task_id]["started_at"] = datetime.now(UTC)
        self._stats["pending_tasks"] -= 1
        self._stats["processing_tasks"] += 1

        asyncio.create_task(
            self._notify_subscribers(
                "task_started",
                {
                    "task_id": task_id,
                    "task": self._tasks[task_id],
                    "stats": self._stats.copy(),
                },
            )
        )

    def task_progress(
        self,
        task_id: str,
        stage: str,
        progress: int = 0,
        message: str = "",
    ) -> None:
        """Update task progress.

        Обновление прогресса задачи.

        Args:
            task_id: Task ID.
            stage: Current processing stage.
            progress: Progress percentage (0-100).
            message: Additional message.

        """
        if task_id not in self._tasks:
            logger.warning(f"Task {task_id} not found in statistics")
            return

        self._tasks[task_id]["current_stage"] = stage
        self._tasks[task_id]["progress"] = progress
        self._tasks[task_id]["progress_message"] = message

        asyncio.create_task(
            self._notify_subscribers(
                "task_progress",
                {
                    "task_id": task_id,
                    "stage": stage,
                    "progress": progress,
                    "message": message,
                    "task": self._tasks[task_id],
                },
            )
        )

    def task_completed(
        self,
        task_id: str,
        result: dict[str, Any] | None = None,
        from_cache: bool = False,
        processing_details: dict[str, Any] | None = None,
    ) -> None:
        """Register task completion.

        Регистрация завершения задачи.

        Args:
            task_id: Task ID.
            result: Execution result.
            from_cache: Result from cache.
            processing_details: Task processing details.

        """
        if task_id not in self._tasks:
            logger.warning(f"Task {task_id} not found in statistics")
            return

        task = self._tasks[task_id]
        task["status"] = "completed"
        task["completed_at"] = datetime.now(UTC)
        task["result"] = result
        task["from_cache"] = from_cache

        # Add processing details if available
        if processing_details:
            task["processing_details"] = processing_details

        # Update statistics
        if task.get("started_at"):
            duration = (task["completed_at"] - task["started_at"]).total_seconds() * 1000
            task["duration_ms"] = duration

            # Recalculate average processing time
            total_completed = self._stats["completed_tasks"]
            avg = self._stats["avg_processing_time_ms"]
            self._stats["avg_processing_time_ms"] = (
                avg * total_completed + duration
            ) / (total_completed + 1)

        self._stats["processing_tasks"] -= 1
        self._stats["completed_tasks"] += 1

        if from_cache:
            self._stats["cache_hits"] += 1
        else:
            self._stats["cache_misses"] += 1

        asyncio.create_task(
            self._notify_subscribers(
                "task_completed",
                {
                    "task_id": task_id,
                    "task": task,
                    "stats": self._stats.copy(),
                },
            )
        )

    def task_failed(
        self,
        task_id: str,
        error: str,
        error_traceback: str | None = None,
    ) -> None:
        """Register task failure.

        Регистрация ошибки задачи.

        Args:
            task_id: Task ID.
            error: Error message.
            error_traceback: Full error traceback.

        """
        if task_id not in self._tasks:
            logger.warning(f"Task {task_id} not found in statistics")
            return

        task = self._tasks[task_id]
        task["status"] = "failed"
        task["completed_at"] = datetime.now(UTC)
        task["error"] = error
        task["error_traceback"] = error_traceback or ""

        # Calculate duration if processing was started
        if task.get("started_at"):
            duration = (task["completed_at"] - task["started_at"]).total_seconds() * 1000
            task["duration_ms"] = duration

        # Update statistics
        if task.get("status") == "processing":
            self._stats["processing_tasks"] -= 1
        else:
            self._stats["pending_tasks"] -= 1

        self._stats["failed_tasks"] += 1
        self._stats["total_errors"] += 1

        # Add to errors log
        error_entry = {
            "task_id": task_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "error": error,
            "error_traceback": error_traceback or "",
            "task_type": task.get("request", {}).get("task_type", "unknown"),
        }
        self._errors_log.append(error_entry)

        # Limit log size
        if len(self._errors_log) > self._max_errors_log:
            self._errors_log.pop(0)

        asyncio.create_task(
            self._notify_subscribers(
                "task_failed",
                {
                    "task_id": task_id,
                    "task": task,
                    "error": error_entry,
                    "stats": self._stats.copy(),
                },
            )
        )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get task information.

        Получить информацию о задаче.

        Args:
            task_id: Task ID.

        Returns:
            Task information or None if not found.

        """
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get list of all tasks.

        Получить список всех задач.

        Returns:
            List of all tasks.

        """
        return [{"task_id": task_id, **task} for task_id, task in self._tasks.items()]

    def get_active_tasks(self) -> list[dict[str, Any]]:
        """Get list of active tasks (pending, processing).

        Получить список активных задач (pending, processing).

        Returns:
            List of active tasks.

        """
        return [
            {"task_id": task_id, **task}
            for task_id, task in self._tasks.items()
            if task.get("status") in ["pending", "processing"]
        ]

    def get_stats(self) -> dict[str, int | float]:
        """Get current statistics.

        Получить текущую статистику.

        Returns:
            Dictionary with statistics.

        """
        return self._stats.copy()

    def get_errors_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent errors.

        Получить последние ошибки.

        Args:
            limit: Maximum number of errors.

        Returns:
            List of recent errors.

        """
        return self._errors_log[-limit:]

    def clear_completed_tasks(self, before: datetime | None = None) -> None:
        """Clear completed tasks.

        Очистить завершенные задачи.

        Args:
            before: Remove tasks completed before specified date.

        """
        to_remove = []
        for task_id, task in self._tasks.items():
            if task.get("status") in ["completed", "failed"]:
                if before is None or task.get("completed_at", datetime.now(UTC)) < before:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        logger.info(f"Cleared {len(to_remove)} completed tasks")

    def get_completed_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get list of recent completed tasks.

        Получить список недавних завершённых задач.

        Args:
            limit: Maximum number of tasks.

        Returns:
            List of completed tasks sorted by completion time (newest first).

        """
        completed = []
        for task in self._tasks.values():
            if task.get("status") in ["completed", "failed"]:
                completed.append(task)

        # Sort by completion time (newest first)
        completed.sort(
            key=lambda x: x.get("completed_at") or x.get("updated_at") or datetime.min,
            reverse=True,
        )

        return completed[:limit]

    def get_summary(self) -> dict[str, Any]:
        """Get summary information for dashboard.

        Получить сводную информацию для дашборда.

        Returns:
            Summary information.

        """
        summary = {
            "stats": self._stats.copy(),
            "active_tasks": self.get_active_tasks(),
            "completed_tasks": self.get_completed_tasks(limit=50),
            "recent_errors": self.get_errors_log(limit=10),
            "total_tasks_tracked": len(self._tasks),
            "subscribers_count": len(self._subscribers),
        }
        # Serialize datetime objects
        return serialize_for_json(summary)


# Global task statistics manager instance
task_statistics = TaskStatistics()
