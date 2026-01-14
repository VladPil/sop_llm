"""API Documentation strings для SOP LLM Executor.

Модуль содержит все description строки для API endpoints.
Вынесены из роутов для чистоты кода.

Использование:
    from src.api.docs import tasks as tasks_docs

    @router.post("/", description=tasks_docs.CREATE_TASK)
    async def create_task(...):
        ...
"""

from src.api.docs import conversations, embeddings, models, monitor, tasks, websocket

__all__ = [
    "conversations",
    "embeddings",
    "models",
    "monitor",
    "tasks",
    "websocket",
]
