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

from src.core import (
    REDIS_IDEMPOTENCY_PREFIX,
    REDIS_LOGS_PREFIX,
    REDIS_LOGS_RECENT_KEY,
    REDIS_PROCESSING_KEY,
    REDIS_QUEUE_KEY,
    REDIS_SESSION_PREFIX,
    TaskStatus,
)
from src.core.config import settings
from src.shared.logging import get_logger

logger = get_logger()

# Дополнительные ключи Redis согласно ТЗ
REDIS_GPU_CACHE_KEY = "system:gpu"
REDIS_STATS_PREFIX = "stats:daily:"
GPU_CACHE_TTL = 5  # 5 секунд
STATS_TTL = 7 * 24 * 60 * 60  # 7 дней


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
        session_key = f"{REDIS_SESSION_PREFIX}{task_id}"

        session_data = {
            "task_id": task_id,
            "status": TaskStatus.PENDING.value,
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
                f"{REDIS_IDEMPOTENCY_PREFIX}{idempotency_key}",
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
        session_key = f"{REDIS_SESSION_PREFIX}{task_id}"

        update_data: dict[str, str] = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if result:
            update_data["result"] = orjson.dumps(result).decode("utf-8")

        if error:
            update_data["error"] = error

        if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value):
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
        session_key = f"{REDIS_SESSION_PREFIX}{task_id}"
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
        result = await self.redis.get(f"{REDIS_IDEMPOTENCY_PREFIX}{idempotency_key}")  # type: ignore[misc]
        return result.decode("utf-8") if result else None  # type: ignore[no-any-return]

    async def delete_session(self, task_id: str) -> None:
        """Удалить сессию (для очистки).

        Args:
            task_id: ID задачи

        """
        session_key = f"{REDIS_SESSION_PREFIX}{task_id}"
        await self.redis.delete(session_key)

        # Удалить логи задачи
        await self.redis.delete(f"{REDIS_LOGS_PREFIX}{task_id}")

        logger.debug("Session удалена", task_id=task_id)

    async def enqueue_task(self, task_id: str, priority: float = 0.0) -> None:
        """Добавить задачу в очередь.

        Args:
            task_id: ID задачи
            priority: Приоритет (выше = раньше обработается)

        """
        # Sorted Set: score = -priority (чтобы больший приоритет был первым)
        await self.redis.zadd(REDIS_QUEUE_KEY, {task_id: -priority})

        logger.debug("Task добавлена в очередь", task_id=task_id, priority=priority)

    async def dequeue_task(self) -> str | None:
        """Извлечь задачу из очереди (с наивысшим приоритетом).

        Returns:
            task_id или None если очередь пуста

        """
        # ZPOPMIN - извлечь элемент с минимальным score (наивысшим приоритетом)
        result = await self.redis.zpopmin(REDIS_QUEUE_KEY, 1)  # type: ignore[misc]

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
        return await self.redis.zcard(REDIS_QUEUE_KEY)  # type: ignore[no-any-return,misc]

    async def set_processing_task(self, task_id: str) -> None:
        """Установить задачу как обрабатываемую.

        Args:
            task_id: ID задачи

        """
        await self.redis.set(REDIS_PROCESSING_KEY, task_id)

    async def get_processing_task(self) -> str | None:
        """Получить ID обрабатываемой задачи.

        Returns:
            task_id или None

        """
        result = await self.redis.get(REDIS_PROCESSING_KEY)
        return result.decode("utf-8") if result else None

    async def clear_processing_task(self) -> None:
        """Очистить обрабатываемую задачу."""
        await self.redis.delete(REDIS_PROCESSING_KEY)

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
        await self.redis.rpush(f"{REDIS_LOGS_PREFIX}{task_id}", log_entry)  # type: ignore[misc]

        # Добавить в logs:recent (с ограничением размера)
        await self.redis.rpush(REDIS_LOGS_RECENT_KEY, log_entry)  # type: ignore[misc]
        await self.redis.ltrim(REDIS_LOGS_RECENT_KEY, -self.logs_max_recent, -1)  # type: ignore[misc]

    async def get_task_logs(self, task_id: str) -> list[dict[str, Any]]:
        """Получить логи задачи.

        Args:
            task_id: ID задачи

        Returns:
            Список логов

        """
        logs = await self.redis.lrange(f"{REDIS_LOGS_PREFIX}{task_id}", 0, -1)  # type: ignore[misc]
        return [orjson.loads(log) for log in logs]

    async def get_recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Получить последние логи всех задач.

        Args:
            limit: Максимум логов

        Returns:
            Список последних логов

        """
        logs = await self.redis.lrange(REDIS_LOGS_RECENT_KEY, -limit, -1)  # type: ignore[misc]
        return [orjson.loads(log) for log in logs]

    async def get_stats(self) -> dict[str, Any]:
        """Получить статистику Redis.

        Returns:
            Словарь со статистикой

        """
        queue_size = await self.get_queue_size()
        processing_task = await self.get_processing_task()
        recent_logs_count = await self.redis.llen(REDIS_LOGS_RECENT_KEY)  # type: ignore[misc]

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

    # GPU Cache (согласно ТЗ)

    async def cache_gpu_stats(self, stats: dict[str, Any]) -> None:
        """Кэшировать GPU статистику.

        Args:
            stats: Словарь с GPU статистикой

        """
        data = orjson.dumps(stats).decode("utf-8")
        await self.redis.setex(REDIS_GPU_CACHE_KEY, GPU_CACHE_TTL, data)

    async def get_cached_gpu_stats(self) -> dict[str, Any] | None:
        """Получить кэшированную GPU статистику.

        Returns:
            Кэшированные данные или None если кэш устарел

        """
        data = await self.redis.get(REDIS_GPU_CACHE_KEY)
        if data:
            return orjson.loads(data)
        return None

    # Daily Statistics (согласно ТЗ)

    async def increment_daily_stat(self, stat_name: str, increment: int = 1) -> None:
        """Инкрементировать дневную статистику.

        Args:
            stat_name: Название метрики (tasks_completed, tokens_used, etc.)
            increment: Значение инкремента

        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"{REDIS_STATS_PREFIX}{today}"

        await self.redis.hincrby(key, stat_name, increment)  # type: ignore[misc]
        await self.redis.expire(key, STATS_TTL)  # type: ignore[misc]

    async def get_daily_stats(self, date: str | None = None) -> dict[str, int]:
        """Получить дневную статистику.

        Args:
            date: Дата в формате YYYY-MM-DD (по умолчанию сегодня)

        Returns:
            Словарь со статистикой

        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        key = f"{REDIS_STATS_PREFIX}{date}"
        data = await self.redis.hgetall(key)  # type: ignore[misc]

        if not data:
            return {}

        return {k.decode("utf-8"): int(v) for k, v in data.items()}

    async def record_task_completion(
        self,
        tokens_used: int,
        duration_ms: int,
        success: bool = True,
    ) -> None:
        """Записать завершение задачи в статистику.

        Args:
            tokens_used: Использовано токенов
            duration_ms: Время выполнения в мс
            success: Успешное завершение

        """
        if success:
            await self.increment_daily_stat("tasks_completed")
        else:
            await self.increment_daily_stat("tasks_failed")

        await self.increment_daily_stat("tokens_used", tokens_used)
        await self.increment_daily_stat("total_duration_ms", duration_ms)


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


# Singleton instance
_session_store_instance: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Получить singleton instance SessionStore.

    Returns:
        Глобальный экземпляр SessionStore

    Raises:
        RuntimeError: Если SessionStore не инициализирован

    """
    if _session_store_instance is None:
        msg = "SessionStore не инициализирован. Вызовите set_session_store() или создайте через startup event."
        raise RuntimeError(msg)

    return _session_store_instance


def set_session_store(store: SessionStore) -> None:
    """Установить global instance SessionStore.

    Args:
        store: SessionStore instance

    """
    global _session_store_instance
    _session_store_instance = store
