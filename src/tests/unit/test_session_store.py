"""Unit тесты для services/session_store.py."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from src.services.session_store import SessionStore, SessionNotFoundError


@pytest.fixture
def session_store(mock_redis: MagicMock) -> SessionStore:
    """Фикстура SessionStore с mock Redis."""
    return SessionStore(
        redis=mock_redis,
        session_ttl=86400,  # 24 hours
        idempotency_ttl=86400,
    )


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

    @pytest.mark.asyncio
    async def test_create_session_with_idempotency_key(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест создания сессии с ключом идемпотентности."""
        mock_redis.set = AsyncMock()

        await session_store.create_session(
            task_id="task-123",
            model="test-model",
            prompt="Test prompt",
            params={},
            idempotency_key="test-key-456",
        )

        # Проверяем что ключ идемпотентности сохранён
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "idempotency:test-key-456" in call_args[0][0]

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
                b"created_at": b"2024-01-01T00:00:00+00:00",
                b"updated_at": b"2024-01-01T00:00:00+00:00",
            }
        )

        session = await session_store.get_session("task-123")

        assert session is not None
        assert session["task_id"] == "task-123"
        assert session["status"] == "pending"
        assert session["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_raises_error(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест что получение несуществующей сессии вызывает ошибку."""
        mock_redis.hgetall = AsyncMock(return_value={})

        with pytest.raises(SessionNotFoundError):
            await session_store.get_session("nonexistent")

    @pytest.mark.asyncio
    async def test_update_session_status(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест обновления статуса сессии."""
        mock_redis.hset = AsyncMock()

        await session_store.update_session_status(
            task_id="task-123", status="processing"
        )

        # Проверяем что hset вызван с правильными аргументами
        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args
        assert call_args[0][0] == "session:task-123"

    @pytest.mark.asyncio
    async def test_enqueue_task(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест добавления задачи в очередь."""
        mock_redis.zadd = AsyncMock()

        await session_store.enqueue_task(task_id="task-123", priority=5.0)

        # Проверяем что zadd вызван
        mock_redis.zadd.assert_called_once()
        call_args = mock_redis.zadd.call_args
        assert call_args[0][0] == "queue:tasks"

    @pytest.mark.asyncio
    async def test_dequeue_task(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест извлечения задачи из очереди."""
        # Мокаем возврат задачи с наивысшим приоритетом
        mock_redis.zpopmin = AsyncMock(return_value=[(b"task-123", 5.0)])

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
        mock_redis.rpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()

        await session_store.add_log(
            task_id="task-123", level="info", message="Test log", metadata={}
        )

        # Проверяем что логи добавлены в оба списка
        assert mock_redis.rpush.call_count == 2
        # Проверяем что ltrim вызван для ограничения размера
        assert mock_redis.ltrim.call_count == 2

    @pytest.mark.asyncio
    async def test_get_logs(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения логов задачи."""
        # Мокаем возврат логов
        mock_redis.lrange = AsyncMock(
            return_value=[
                b'{"task_id": "task-123", "level": "info", "message": "Test 1"}',
                b'{"task_id": "task-123", "level": "error", "message": "Test 2"}',
            ]
        )

        logs = await session_store.get_logs("task-123")

        assert len(logs) == 2
        assert logs[0]["message"] == "Test 1"
        assert logs[1]["level"] == "error"

    @pytest.mark.asyncio
    async def test_check_idempotency_key_exists(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест проверки существующего ключа идемпотентности."""
        mock_redis.get = AsyncMock(return_value=b"task-123")

        task_id = await session_store.check_idempotency_key("test-key")

        assert task_id == "task-123"
        mock_redis.get.assert_called_once_with("idempotency:test-key")

    @pytest.mark.asyncio
    async def test_check_idempotency_key_not_exists(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест проверки несуществующего ключа идемпотентности."""
        mock_redis.get = AsyncMock(return_value=None)

        task_id = await session_store.check_idempotency_key("test-key")

        assert task_id is None

    @pytest.mark.asyncio
    async def test_delete_session(
        self, session_store: SessionStore, mock_redis: MagicMock
    ) -> None:
        """Тест удаления сессии."""
        mock_redis.delete = AsyncMock()

        await session_store.delete_session("task-123")

        # Проверяем что удалены session и logs
        assert mock_redis.delete.call_count == 2
