"""Unit тесты для services/conversation_store.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.conversation_store import ConversationStore


@pytest.fixture
def mock_redis() -> MagicMock:
    """Мок Redis клиента."""
    redis = MagicMock()
    redis.hset = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.expire = AsyncMock()
    redis.sadd = AsyncMock()
    redis.srem = AsyncMock()
    redis.smembers = AsyncMock(return_value=set())
    redis.exists = AsyncMock(return_value=1)
    redis.delete = AsyncMock()
    redis.rpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.llen = AsyncMock(return_value=0)
    redis.ping = AsyncMock()
    return redis


@pytest.fixture
def conversation_store(mock_redis: MagicMock) -> ConversationStore:
    """Фикстура ConversationStore с mock Redis."""
    return ConversationStore(redis_client=mock_redis)


@pytest.mark.unit
class TestConversationStore:
    """Тесты для ConversationStore."""

    @pytest.mark.asyncio
    async def test_create_conversation(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест создания нового диалога."""
        conv_id = await conversation_store.create_conversation(
            model="claude-3.5-sonnet",
            system_prompt="Ты - полезный ассистент",
        )

        # Проверяем формат ID
        assert conv_id.startswith("conv_")
        assert len(conv_id) == 17  # conv_ + 12 hex chars

        # Проверяем что Redis методы вызваны
        assert mock_redis.hset.call_count >= 1
        assert mock_redis.expire.call_count >= 1
        assert mock_redis.sadd.called  # Добавление в индекс

    @pytest.mark.asyncio
    async def test_create_conversation_with_system_prompt_adds_message(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест что системный промпт добавляется как первое сообщение."""
        # При создании с system_prompt вызывается add_message
        mock_redis.exists = AsyncMock(return_value=1)

        await conversation_store.create_conversation(
            system_prompt="System prompt",
        )

        # Должен быть вызов rpush для добавления сообщения
        assert mock_redis.rpush.called

    @pytest.mark.asyncio
    async def test_create_conversation_with_metadata(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест создания диалога с метаданными."""
        await conversation_store.create_conversation(
            metadata={"user_id": "user_123", "session_type": "support"},
        )

        # Проверяем что hset вызван
        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args
        mapping = call_args[1]["mapping"]
        assert "metadata" in mapping

    @pytest.mark.asyncio
    async def test_get_conversation(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения существующего диалога."""
        mock_redis.hgetall = AsyncMock(
            return_value={
                b"conversation_id": b"conv_abc123",
                b"model": b"claude-3.5-sonnet",
                b"system_prompt": b"Test prompt",
                b"message_count": b"5",
                b"created_at": b"2024-01-01T00:00:00",
                b"updated_at": b"2024-01-01T00:00:00",
            }
        )

        conv = await conversation_store.get_conversation("conv_abc123")

        assert conv is not None
        assert conv["conversation_id"] == "conv_abc123"
        assert conv["model"] == "claude-3.5-sonnet"
        assert conv["message_count"] == 5

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения несуществующего диалога."""
        mock_redis.hgetall = AsyncMock(return_value={})

        conv = await conversation_store.get_conversation("conv_nonexistent")

        assert conv is None

    @pytest.mark.asyncio
    async def test_delete_conversation(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест удаления диалога."""
        mock_redis.exists = AsyncMock(return_value=1)

        result = await conversation_store.delete_conversation("conv_abc123")

        assert result is True
        mock_redis.delete.assert_called()
        mock_redis.srem.assert_called()  # Удаление из индекса

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест удаления несуществующего диалога."""
        mock_redis.exists = AsyncMock(return_value=0)

        result = await conversation_store.delete_conversation("conv_nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_add_message(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест добавления сообщения в диалог."""
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis.llen = AsyncMock(return_value=1)

        result = await conversation_store.add_message(
            conversation_id="conv_abc123",
            role="user",
            content="Hello!",
        )

        assert result is True
        mock_redis.rpush.assert_called()
        mock_redis.ltrim.assert_called()  # Ограничение размера

    @pytest.mark.asyncio
    async def test_add_message_to_nonexistent_conversation(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест добавления сообщения в несуществующий диалог."""
        mock_redis.exists = AsyncMock(return_value=0)

        result = await conversation_store.add_message(
            conversation_id="conv_nonexistent",
            role="user",
            content="Hello!",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_messages(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения сообщений диалога."""
        mock_redis.lrange = AsyncMock(
            return_value=[
                b'{"role": "system", "content": "You are helpful", "timestamp": "2024-01-01T00:00:00"}',
                b'{"role": "user", "content": "Hello!", "timestamp": "2024-01-01T00:00:01"}',
                b'{"role": "assistant", "content": "Hi there!", "timestamp": "2024-01-01T00:00:02"}',
            ]
        )

        messages = await conversation_store.get_messages("conv_abc123")

        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_messages_with_limit(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения ограниченного количества сообщений."""
        mock_redis.lrange = AsyncMock(
            return_value=[
                b'{"role": "user", "content": "Last message", "timestamp": "2024-01-01T00:00:00"}',
            ]
        )

        messages = await conversation_store.get_messages("conv_abc123", limit=1)

        assert len(messages) == 1
        # Проверяем что lrange вызван с правильными параметрами (-1, -1 для последнего)
        mock_redis.lrange.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_context_messages(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения сообщений в формате ChatMessage."""
        mock_redis.lrange = AsyncMock(
            return_value=[
                b'{"role": "user", "content": "Hello", "timestamp": "2024-01-01T00:00:00"}',
                b'{"role": "assistant", "content": "Hi!", "timestamp": "2024-01-01T00:00:01"}',
            ]
        )

        chat_messages = await conversation_store.get_context_messages("conv_abc123")

        assert len(chat_messages) == 2
        assert chat_messages[0].role == "user"
        assert chat_messages[0].content == "Hello"
        assert chat_messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_add_turn(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест добавления полного turn (user + assistant)."""
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis.llen = AsyncMock(return_value=2)

        result = await conversation_store.add_turn(
            conversation_id="conv_abc123",
            user_message="What is Python?",
            assistant_response="Python is a programming language.",
        )

        assert result is True
        # Должно быть 2 вызова rpush (user + assistant)
        assert mock_redis.rpush.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_messages(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест очистки истории сообщений."""
        mock_redis.exists = AsyncMock(return_value=1)

        result = await conversation_store.clear_messages("conv_abc123")

        assert result is True
        mock_redis.delete.assert_called()  # Удаление списка сообщений
        mock_redis.hset.assert_called()  # Обновление message_count

    @pytest.mark.asyncio
    async def test_list_conversations(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест получения списка диалогов."""
        mock_redis.smembers = AsyncMock(
            return_value={b"conv_abc123", b"conv_def456"}
        )
        mock_redis.hgetall = AsyncMock(
            return_value={
                b"conversation_id": b"conv_abc123",
                b"created_at": b"2024-01-01T00:00:00",
                b"updated_at": b"2024-01-01T00:00:00",
            }
        )

        conversations = await conversation_store.list_conversations(limit=10)

        assert len(conversations) > 0
        mock_redis.smembers.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест обновления метаданных диалога."""
        mock_redis.exists = AsyncMock(return_value=1)

        result = await conversation_store.update_conversation(
            conversation_id="conv_abc123",
            model="gpt-4-turbo",
            system_prompt="New prompt",
        )

        assert result is True
        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_success(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест успешной проверки здоровья."""
        mock_redis.ping = AsyncMock(return_value=True)

        result = await conversation_store.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(
        self, conversation_store: ConversationStore, mock_redis: MagicMock
    ) -> None:
        """Тест неудачной проверки здоровья."""
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection failed"))

        result = await conversation_store.health_check()

        assert result is False
