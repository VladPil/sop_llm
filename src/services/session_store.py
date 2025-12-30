"""Session Store для SOP LLM Executor.

Redis wrapper для управления жизненным циклом задач согласно ТЗ.

Redis Schema (TTL 24h):
    session:{task_id}       -> Hash (task data: status, model, prompt, result, etc.)
    queue:tasks             -> Sorted Set (priority queue)
    queue:processing        -> String (current task_id)
    idempotency:{key}       -> String (task_id mapping)
    logs:recent             -> List (последние N логов)
    logs:{task_id}          -> List (логи конкретной задачи)
"""

from datetime import datetime
from typing import Any

import orjson
from redis.asyncio import Redis

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger()


class SessionStore:
    """Redis-based session storage для task lifecycle management.

    Обеспечивает:
    - Создание и обновление сессий
    - Управление очередью задач (priority queue)
    - Idempotency ключи
    - Хранение логов
    """

    def __init__(self, redis_client: Redis) -> None:
        """Инициализировать Session Store.

        Args:
            redis_client: Async Redis client

        """
        self.redis = redis_client
        self.session_ttl = settings.session_ttl_seconds
        self.idempotency_ttl = settings.idempotency_ttl_seconds
        self.logs_max_recent = settings.logs_max_recent

    async def create_session(
        self,
        task_id: str,
        model: str,
        prompt: str,
        params: dict[str, Any],
        webhook_url: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        """Создать новую сессию задачи.

        Args:
            task_id: Уникальный ID задачи
            model: Название модели
            prompt: Промпт для генерации
            params: Параметры генерации (temperature, max_tokens, etc.)
            webhook_url: URL для callback (опционально)
            idempotency_key: Ключ идемпотентности (опционально)

        """
        session_key = f"session:{task_id}"

        session_data = {
            "task_id": task_id,
            "status": "pending",
            "model": model,
            "prompt": prompt,
            "params": orjson.dumps(params).decode("utf-8"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        if webhook_url:
            session_data["webhook_url"] = webhook_url

        if idempotency_key:
            session_data["idempotency_key"] = idempotency_key
            # Сохранить маппинг idempotency_key -> task_id
            await self.redis.setex(
                f"idempotency:{idempotency_key}",
                self.idempotency_ttl,
                task_id,
            )

        # Сохранить сессию с TTL
        await self.redis.hset(session_key, mapping=session_data)  # type: ignore[arg-type]
        await self.redis.expire(session_key, self.session_ttl)  # type: ignore[misc]

        logger.info(
            "Session создана",
            task_id=task_id,
            model=model,
            has_webhook=webhook_url is not None,
            has_idempotency=idempotency_key is not None,
        )

    async def update_session_status(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Обновить статус сессии.

        Args:
            task_id: ID задачи
            status: Новый статус (pending, processing, completed, failed)
            result: Результат генерации (для completed)
            error: Сообщение об ошибке (для failed)

        """
        session_key = f"session:{task_id}"

        update_data: dict[str, str] = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if result:
            update_data["result"] = orjson.dumps(result).decode("utf-8")

        if error:
            update_data["error"] = error

        if status in ("completed", "failed"):
            update_data["finished_at"] = datetime.utcnow().isoformat()

        await self.redis.hset(session_key, mapping=update_data)  # type: ignore[arg-type,misc]

        logger.debug("Session обновлена", task_id=task_id, status=status)

    async def get_session(self, task_id: str) -> dict[str, Any] | None:
        """Получить данные сессии.

        Args:
            task_id: ID задачи

        Returns:
            Данные сессии или None если не найдена

        """
        session_key = f"session:{task_id}"
        data = await self.redis.hgetall(session_key)  # type: ignore[misc]

        if not data:
            return None

        # Декодировать bytes -> str
        session = {k.decode("utf-8"): v.decode("utf-8") for k, v in data.items()}

        # Распарсить JSON поля
        if "params" in session:
            session["params"] = orjson.loads(session["params"])

        if "result" in session:
            session["result"] = orjson.loads(session["result"])

        return session

    async def get_task_by_idempotency_key(self, idempotency_key: str) -> str | None:
        """Получить task_id по idempotency ключу.

        Args:
            idempotency_key: Ключ идемпотентности

        Returns:
            task_id или None

        """
        result = await self.redis.get(f"idempotency:{idempotency_key}")  # type: ignore[misc]
        return result.decode("utf-8") if result else None  # type: ignore[no-any-return]

    async def delete_session(self, task_id: str) -> None:
        """Удалить сессию (для очистки).

        Args:
            task_id: ID задачи

        """
        session_key = f"session:{task_id}"
        await self.redis.delete(session_key)

        # Удалить логи задачи
        await self.redis.delete(f"logs:{task_id}")

        logger.debug("Session удалена", task_id=task_id)

    async def enqueue_task(self, task_id: str, priority: float = 0.0) -> None:
        """Добавить задачу в очередь.

        Args:
            task_id: ID задачи
            priority: Приоритет (выше = раньше обработается)

        """
        # Sorted Set: score = -priority (чтобы больший приоритет был первым)
        await self.redis.zadd("queue:tasks", {task_id: -priority})

        logger.debug("Task добавлена в очередь", task_id=task_id, priority=priority)

    async def dequeue_task(self) -> str | None:
        """Извлечь задачу из очереди (с наивысшим приоритетом).

        Returns:
            task_id или None если очередь пуста

        """
        # ZPOPMIN - извлечь элемент с минимальным score (наивысшим приоритетом)
        result = await self.redis.zpopmin("queue:tasks", 1)  # type: ignore[misc]

        if not result:
            return None

        task_id = result[0][0].decode("utf-8")

        logger.debug("Task извлечена из очереди", task_id=task_id)
        return task_id

    async def get_queue_size(self) -> int:
        """Получить размер очереди.

        Returns:
            Количество задач в очереди

        """
        return await self.redis.zcard("queue:tasks")  # type: ignore[no-any-return,misc]

    async def set_processing_task(self, task_id: str) -> None:
        """Установить задачу как обрабатываемую.

        Args:
            task_id: ID задачи

        """
        await self.redis.set("queue:processing", task_id)

    async def get_processing_task(self) -> str | None:
        """Получить ID обрабатываемой задачи.

        Returns:
            task_id или None

        """
        result = await self.redis.get("queue:processing")
        return result.decode("utf-8") if result else None

    async def clear_processing_task(self) -> None:
        """Очистить обрабатываемую задачу."""
        await self.redis.delete("queue:processing")

    async def add_log(self, task_id: str, level: str, message: str) -> None:
        """Добавить лог для задачи.

        Args:
            task_id: ID задачи
            level: Уровень лога (INFO, WARNING, ERROR, etc.)
            message: Сообщение

        """
        log_entry = orjson.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": task_id,
            "level": level,
            "message": message,
        }).decode("utf-8")

        # Добавить в logs:{task_id}
        await self.redis.rpush(f"logs:{task_id}", log_entry)  # type: ignore[misc]

        # Добавить в logs:recent (с ограничением размера)
        await self.redis.rpush("logs:recent", log_entry)  # type: ignore[misc]
        await self.redis.ltrim("logs:recent", -self.logs_max_recent, -1)  # type: ignore[misc]

    async def get_task_logs(self, task_id: str) -> list[dict[str, Any]]:
        """Получить логи задачи.

        Args:
            task_id: ID задачи

        Returns:
            Список логов

        """
        logs = await self.redis.lrange(f"logs:{task_id}", 0, -1)  # type: ignore[misc]
        return [orjson.loads(log) for log in logs]

    async def get_recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Получить последние логи всех задач.

        Args:
            limit: Максимум логов

        Returns:
            Список последних логов

        """
        logs = await self.redis.lrange("logs:recent", -limit, -1)  # type: ignore[misc]
        return [orjson.loads(log) for log in logs]

    async def get_stats(self) -> dict[str, Any]:
        """Получить статистику Redis.

        Returns:
            Словарь со статистикой

        """
        queue_size = await self.get_queue_size()
        processing_task = await self.get_processing_task()
        recent_logs_count = await self.redis.llen("logs:recent")  # type: ignore[misc]

        return {
            "queue_size": queue_size,
            "processing_task": processing_task,
            "recent_logs_count": recent_logs_count,
        }

    async def health_check(self) -> bool:
        """Проверить доступность Redis.

        Returns:
            True если Redis доступен

        """
        try:
            await self.redis.ping()  # type: ignore[misc]
            return True
        except Exception as e:
            logger.exception("Redis недоступен", error=str(e))
            return False


async def create_session_store() -> SessionStore:
    """Создать SessionStore с подключением к Redis.

    Returns:
        Настроенный SessionStore instance

    """
    redis_client = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,  # Мы сами декодируем
    )

    store = SessionStore(redis_client)

    # Проверить подключение
    if not await store.health_check():
        msg = f"Не удалось подключиться к Redis: {settings.redis_url}"
        raise ConnectionError(msg)

    logger.info("SessionStore создан", redis_url=settings.redis_url)
    return store
