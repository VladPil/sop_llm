"""Unit тесты для services/session_store.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.session_store import SessionStore


@pytest.fixture
def mock_redis() -> MagicMock:
    """Мок Redis клиента."""
    redis = MagicMock()
    redis.hset = AsyncMock()
    redis.expire = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.zadd = AsyncMock()
    redis.zpopmin = AsyncMock(return_value=[])
    redis.zcard = AsyncMock(return_value=0)
    redis.rpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.llen = AsyncMock(return_value=0)
    redis.ping = AsyncMock()
    return redis


@pytest.fixture
def session_store(mock_redis: MagicMock) -> SessionStore:
    """Фикстура SessionStore с mock Redis."""
    with patch("src.services.session_store.settings") as mock_settings:
        mock_settings.session_ttl_seconds = 86400
        mock_settings.idempotency_ttl_seconds = 86400
        mock_settings.logs_max_recent = 100
        return SessionStore(redis_client=mock_redis)


class TestSessionStore:
    """Тесты для SessionStore."""

    @pytest.mark.asyncio
    async def test_create_session(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест создания новой сессии."""
        await session_store.create_session(
            task_id="task-123",
            model="test-model",
            prompt="Test prompt",
            params={"temperature": 0.7, "max_tokens": 100},
        )

        # Проверяем что Redis методы вызваны
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()

        # Проверяем аргументы hset
        call_args = mock_redis.hset.call_args
        assert call_args[0][0] == "session:task-123"
        assert "mapping" in call_args[1]

    @pytest.mark.asyncio
    async def test_create_session_with_webhook(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест создания сессии с webhook URL."""
        await session_store.create_session(
            task_id="task-123",
            model="test-model",
            prompt="Test prompt",
            params={},
            webhook_url="https://example.com/webhook",
        )

        mock_redis.hset.assert_called_once()
        # Проверяем что webhook_url сохранён
        call_args = mock_redis.hset.call_args
        mapping = call_args[1]["mapping"]
        assert mapping["webhook_url"] == "https://example.com/webhook"

    @pytest.mark.asyncio
    async def test_create_session_with_idempotency_key(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест создания сессии с ключом идемпотентности."""
        await session_store.create_session(
            task_id="task-123",
            model="test-model",
            prompt="Test prompt",
            params={},
            idempotency_key="test-key-456",
        )

        # Проверяем что ключ идемпотентности сохранён через setex
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert "idempotency:test-key-456" in call_args[0][0]
        assert call_args[0][2] == "task-123"

    @pytest.mark.asyncio
    async def test_get_session(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения существующей сессии."""
        # Мокаем возврат данных из Redis
        mock_redis.hgetall = AsyncMock(
            return_value={
                b"task_id": b"task-123",
                b"status": b"pending",
                b"model": b"test-model",
                b"prompt": b"Test prompt",
                b"params": b'{"temperature": 0.7}',
                b"created_at": b"2024-01-01T00:00:00",
                b"updated_at": b"2024-01-01T00:00:00",
            }
        )

        session = await session_store.get_session("task-123")

        assert session is not None
        assert session["task_id"] == "task-123"
        assert session["status"] == "pending"
        assert session["model"] == "test-model"
        assert session["params"]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_none(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест что получение несуществующей сессии возвращает None."""
        mock_redis.hgetall = AsyncMock(return_value={})

        session = await session_store.get_session("nonexistent")

        assert session is None

    @pytest.mark.asyncio
    async def test_update_session_status(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест обновления статуса сессии."""
        await session_store.update_session_status(
            task_id="task-123", status="processing"
        )

        # Проверяем что hset вызван с правильными аргументами
        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args
        assert call_args[0][0] == "session:task-123"
        mapping = call_args[1]["mapping"]
        assert mapping["status"] == "processing"

    @pytest.mark.asyncio
    async def test_update_session_status_with_result(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест обновления статуса с результатом."""
        result = {"text": "Generated text", "tokens": 100}

        await session_store.update_session_status(
            task_id="task-123",
            status="completed",
            result=result,
        )

        call_args = mock_redis.hset.call_args
        mapping = call_args[1]["mapping"]
        assert mapping["status"] == "completed"
        assert "result" in mapping
        assert "finished_at" in mapping

    @pytest.mark.asyncio
    async def test_update_session_status_with_error(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест обновления статуса с ошибкой."""
        await session_store.update_session_status(
            task_id="task-123",
            status="failed",
            error="Generation failed",
        )

        call_args = mock_redis.hset.call_args
        mapping = call_args[1]["mapping"]
        assert mapping["status"] == "failed"
        assert mapping["error"] == "Generation failed"
        assert "finished_at" in mapping

    @pytest.mark.asyncio
    async def test_enqueue_task(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест добавления задачи в очередь."""
        await session_store.enqueue_task(task_id="task-123", priority=5.0)

        # Проверяем что zadd вызван с отрицательным приоритетом
        mock_redis.zadd.assert_called_once()
        call_args = mock_redis.zadd.call_args
        assert call_args[0][0] == "queue:tasks"
        assert call_args[0][1] == {"task-123": -5.0}

    @pytest.mark.asyncio
    async def test_dequeue_task(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест извлечения задачи из очереди."""
        # Мокаем возврат задачи с наивысшим приоритетом
        mock_redis.zpopmin = AsyncMock(return_value=[(b"task-123", -5.0)])

        task_id = await session_store.dequeue_task()

        assert task_id == "task-123"
        mock_redis.zpopmin.assert_called_once_with("queue:tasks", 1)

    @pytest.mark.asyncio
    async def test_dequeue_task_empty_queue(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест извлечения из пустой очереди возвращает None."""
        mock_redis.zpopmin = AsyncMock(return_value=[])

        task_id = await session_store.dequeue_task()

        assert task_id is None

    @pytest.mark.asyncio
    async def test_get_queue_size(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения размера очереди."""
        mock_redis.zcard = AsyncMock(return_value=5)

        size = await session_store.get_queue_size()

        assert size == 5
        mock_redis.zcard.assert_called_once_with("queue:tasks")

    @pytest.mark.asyncio
    async def test_add_log(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест добавления лога."""
        await session_store.add_log(
            task_id="task-123", level="INFO", message="Test log"
        )

        # Проверяем что логи добавлены в оба списка
        assert mock_redis.rpush.call_count == 2
        # Проверяем что ltrim вызван для ограничения размера
        mock_redis.ltrim.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_logs(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения логов задачи."""
        # Мокаем возврат логов
        mock_redis.lrange = AsyncMock(
            return_value=[
                b'{"task_id": "task-123", "level": "INFO", "message": "Test 1"}',
                b'{"task_id": "task-123", "level": "ERROR", "message": "Test 2"}',
            ]
        )

        logs = await session_store.get_task_logs("task-123")

        assert len(logs) == 2
        assert logs[0]["message"] == "Test 1"
        assert logs[1]["level"] == "ERROR"

    @pytest.mark.asyncio
    async def test_get_task_by_idempotency_key_exists(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест проверки существующего ключа идемпотентности."""
        mock_redis.get = AsyncMock(return_value=b"task-123")

        task_id = await session_store.get_task_by_idempotency_key("test-key")

        assert task_id == "task-123"
        mock_redis.get.assert_called_once_with("idempotency:test-key")

    @pytest.mark.asyncio
    async def test_get_task_by_idempotency_key_not_exists(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест проверки несуществующего ключа идемпотентности."""
        mock_redis.get = AsyncMock(return_value=None)

        task_id = await session_store.get_task_by_idempotency_key("test-key")

        assert task_id is None

    @pytest.mark.asyncio
    async def test_delete_session(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест удаления сессии."""
        await session_store.delete_session("task-123")

        # Проверяем что удалены session и logs
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_set_processing_task(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест установки обрабатываемой задачи."""
        await session_store.set_processing_task("task-123")

        mock_redis.set.assert_called_once_with("queue:processing", "task-123")

    @pytest.mark.asyncio
    async def test_get_processing_task(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения обрабатываемой задачи."""
        mock_redis.get = AsyncMock(return_value=b"task-123")

        task_id = await session_store.get_processing_task()

        assert task_id == "task-123"

    @pytest.mark.asyncio
    async def test_get_processing_task_none(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест когда нет обрабатываемой задачи."""
        mock_redis.get = AsyncMock(return_value=None)

        task_id = await session_store.get_processing_task()

        assert task_id is None

    @pytest.mark.asyncio
    async def test_clear_processing_task(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест очистки обрабатываемой задачи."""
        await session_store.clear_processing_task()

        mock_redis.delete.assert_called_once_with("queue:processing")

    @pytest.mark.asyncio
    async def test_get_stats(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения статистики."""
        mock_redis.zcard = AsyncMock(return_value=5)
        mock_redis.get = AsyncMock(return_value=b"task-123")
        mock_redis.llen = AsyncMock(return_value=50)

        stats = await session_store.get_stats()

        assert stats["queue_size"] == 5
        assert stats["processing_task"] == "task-123"
        assert stats["recent_logs_count"] == 50

    @pytest.mark.asyncio
    async def test_health_check_success(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест успешной проверки здоровья."""
        mock_redis.ping = AsyncMock(return_value=True)

        result = await session_store.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест неудачной проверки здоровья."""
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))

        result = await session_store.health_check()

        assert result is False
