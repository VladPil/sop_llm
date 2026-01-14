"""Conversation Store для SOP LLM Executor.

Redis wrapper для управления историей диалогов (multi-turn conversations).

Redis Schema:
    conversation:{conv_id}          -> Hash (metadata: model, created_at, updated_at, etc.)
    conversation:{conv_id}:messages -> List (сообщения в формате JSON)
    conversations:index             -> Set (все conversation_id)
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import orjson
from redis.asyncio import Redis

from src.core.constants import (
    DEFAULT_CONTEXT_MESSAGES_LIMIT,
    DEFAULT_CONVERSATION_TTL,
    DEFAULT_MAX_CONVERSATION_MESSAGES,
    REDIS_CONVERSATION_INDEX_KEY,
    REDIS_CONVERSATION_PREFIX,
)
from src.providers.base import ChatMessage
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ConversationStore:
    """Redis-based storage для multi-turn conversations.

    Обеспечивает:
    - Создание и получение диалогов
    - Добавление сообщений в историю
    - Получение контекста для LLM запросов
    - TTL для автоматической очистки старых диалогов
    """

    def __init__(self, redis_client: Redis) -> None:
        """Инициализировать Conversation Store.

        Args:
            redis_client: Async Redis client

        """
        self.redis = redis_client
        self.conversation_ttl = DEFAULT_CONVERSATION_TTL
        self.max_messages = DEFAULT_MAX_CONVERSATION_MESSAGES
        self.context_limit = DEFAULT_CONTEXT_MESSAGES_LIMIT

    def _conv_key(self, conversation_id: str) -> str:
        """Получить ключ для метаданных диалога."""
        return f"{REDIS_CONVERSATION_PREFIX}{conversation_id}"

    def _messages_key(self, conversation_id: str) -> str:
        """Получить ключ для сообщений диалога."""
        return f"{REDIS_CONVERSATION_PREFIX}{conversation_id}:messages"

    async def create_conversation(
        self,
        model: str | None = None,
        system_prompt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Создать новый диалог.

        Args:
            model: Модель по умолчанию для диалога (опционально)
            system_prompt: Системный промпт (опционально)
            metadata: Дополнительные метаданные

        Returns:
            conversation_id: Уникальный ID диалога

        """
        conversation_id = f"conv_{uuid4().hex[:12]}"
        conv_key = self._conv_key(conversation_id)
        messages_key = self._messages_key(conversation_id)

        now = datetime.now(UTC).isoformat()

        conv_data: dict[str, str] = {
            "conversation_id": conversation_id,
            "created_at": now,
            "updated_at": now,
            "message_count": "0",
        }

        if model:
            conv_data["model"] = model

        if system_prompt:
            conv_data["system_prompt"] = system_prompt

        if metadata:
            conv_data["metadata"] = orjson.dumps(metadata).decode("utf-8")

        # Сохранить метаданные
        await self.redis.hset(conv_key, mapping=conv_data)  # type: ignore[arg-type]
        await self.redis.expire(conv_key, self.conversation_ttl)  # type: ignore[misc]

        # Инициализировать пустой список сообщений
        await self.redis.expire(messages_key, self.conversation_ttl)  # type: ignore[misc]

        # Добавить в индекс
        await self.redis.sadd(REDIS_CONVERSATION_INDEX_KEY, conversation_id)  # type: ignore[misc]

        # Если есть системный промпт, добавить как первое сообщение
        if system_prompt:
            await self.add_message(
                conversation_id,
                role="system",
                content=system_prompt,
            )

        logger.info(
            "Диалог создан",
            conversation_id=conversation_id,
            model=model,
            has_system_prompt=system_prompt is not None,
        )

        return conversation_id

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """Получить метаданные диалога.

        Args:
            conversation_id: ID диалога

        Returns:
            Метаданные диалога или None если не найден

        """
        conv_key = self._conv_key(conversation_id)
        data = await self.redis.hgetall(conv_key)  # type: ignore[misc]

        if not data:
            return None

        # Декодировать bytes -> str
        result = {k.decode("utf-8"): v.decode("utf-8") for k, v in data.items()}

        # Распарсить JSON поля
        if "metadata" in result:
            result["metadata"] = orjson.loads(result["metadata"])

        if "message_count" in result:
            result["message_count"] = int(result["message_count"])

        return result

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Удалить диалог.

        Args:
            conversation_id: ID диалога

        Returns:
            True если диалог был удалён

        """
        conv_key = self._conv_key(conversation_id)
        messages_key = self._messages_key(conversation_id)

        # Проверить существование
        exists = await self.redis.exists(conv_key)
        if not exists:
            return False

        # Удалить данные
        await self.redis.delete(conv_key, messages_key)

        # Удалить из индекса
        await self.redis.srem(REDIS_CONVERSATION_INDEX_KEY, conversation_id)  # type: ignore[misc]

        logger.info("Диалог удалён", conversation_id=conversation_id)
        return True

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> bool:
        """Добавить сообщение в диалог.

        Args:
            conversation_id: ID диалога
            role: Роль отправителя (system, user, assistant)
            content: Текст сообщения

        Returns:
            True если сообщение добавлено

        """
        conv_key = self._conv_key(conversation_id)
        messages_key = self._messages_key(conversation_id)

        # Проверить существование диалога
        exists = await self.redis.exists(conv_key)
        if not exists:
            logger.warning("Диалог не найден", conversation_id=conversation_id)
            return False

        # Создать сообщение
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        message_json = orjson.dumps(message).decode("utf-8")

        # Добавить в список
        await self.redis.rpush(messages_key, message_json)  # type: ignore[misc]

        # Ограничить количество сообщений
        await self.redis.ltrim(messages_key, -self.max_messages, -1)  # type: ignore[misc]

        # Обновить метаданные
        message_count = await self.redis.llen(messages_key)  # type: ignore[misc]
        await self.redis.hset(conv_key, mapping={  # type: ignore[arg-type]
            "updated_at": datetime.now(UTC).isoformat(),
            "message_count": str(message_count),
        })

        # Обновить TTL
        await self.redis.expire(conv_key, self.conversation_ttl)  # type: ignore[misc]
        await self.redis.expire(messages_key, self.conversation_ttl)  # type: ignore[misc]

        logger.debug(
            "Сообщение добавлено",
            conversation_id=conversation_id,
            role=role,
            message_count=message_count,
        )

        return True

    async def get_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Получить сообщения диалога.

        Args:
            conversation_id: ID диалога
            limit: Максимум сообщений (None = все)

        Returns:
            Список сообщений

        """
        messages_key = self._messages_key(conversation_id)

        if limit:
            # Получить последние N сообщений
            messages = await self.redis.lrange(messages_key, -limit, -1)  # type: ignore[misc]
        else:
            # Получить все
            messages = await self.redis.lrange(messages_key, 0, -1)  # type: ignore[misc]

        return [orjson.loads(msg) for msg in messages]

    async def get_context_messages(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[ChatMessage]:
        """Получить сообщения в формате ChatMessage для LLM.

        Args:
            conversation_id: ID диалога
            limit: Максимум сообщений (по умолчанию context_limit)

        Returns:
            Список ChatMessage для передачи в провайдер

        """
        effective_limit = limit or self.context_limit
        messages = await self.get_messages(conversation_id, limit=effective_limit)

        return [
            ChatMessage(role=msg["role"], content=msg["content"])  # type: ignore[arg-type]
            for msg in messages
        ]

    async def add_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
    ) -> bool:
        """Добавить полный turn (user + assistant) в диалог.

        Удобный метод для добавления пары сообщений после генерации.

        Args:
            conversation_id: ID диалога
            user_message: Сообщение пользователя
            assistant_response: Ответ ассистента

        Returns:
            True если оба сообщения добавлены

        """
        user_added = await self.add_message(
            conversation_id,
            role="user",
            content=user_message,
        )

        if not user_added:
            return False

        return await self.add_message(
            conversation_id,
            role="assistant",
            content=assistant_response,
        )

    async def clear_messages(self, conversation_id: str) -> bool:
        """Очистить историю сообщений диалога (сохранить метаданные).

        Args:
            conversation_id: ID диалога

        Returns:
            True если история очищена

        """
        conv_key = self._conv_key(conversation_id)
        messages_key = self._messages_key(conversation_id)

        # Проверить существование
        exists = await self.redis.exists(conv_key)
        if not exists:
            return False

        # Очистить сообщения
        await self.redis.delete(messages_key)

        # Обновить метаданные
        await self.redis.hset(conv_key, mapping={  # type: ignore[arg-type]
            "updated_at": datetime.now(UTC).isoformat(),
            "message_count": "0",
        })

        logger.info("История диалога очищена", conversation_id=conversation_id)
        return True

    async def list_conversations(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Получить список диалогов.

        Args:
            limit: Максимум диалогов
            offset: Смещение для пагинации

        Returns:
            Список метаданных диалогов

        """
        # Получить все ID из индекса
        all_ids = await self.redis.smembers(REDIS_CONVERSATION_INDEX_KEY)  # type: ignore[misc]
        conversation_ids = sorted(
            [cid.decode("utf-8") for cid in all_ids],
            reverse=True,  # Новые первыми
        )

        # Применить пагинацию
        paginated_ids = conversation_ids[offset : offset + limit]

        # Получить метаданные для каждого
        conversations = []
        for conv_id in paginated_ids:
            conv = await self.get_conversation(conv_id)
            if conv:
                conversations.append(conv)

        return conversations

    async def update_conversation(
        self,
        conversation_id: str,
        model: str | None = None,
        system_prompt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Обновить метаданные диалога.

        Args:
            conversation_id: ID диалога
            model: Новая модель (опционально)
            system_prompt: Новый системный промпт (опционально)
            metadata: Новые метаданные (опционально)

        Returns:
            True если диалог обновлён

        """
        conv_key = self._conv_key(conversation_id)

        # Проверить существование
        exists = await self.redis.exists(conv_key)
        if not exists:
            return False

        update_data: dict[str, str] = {
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if model is not None:
            update_data["model"] = model

        if system_prompt is not None:
            update_data["system_prompt"] = system_prompt

        if metadata is not None:
            update_data["metadata"] = orjson.dumps(metadata).decode("utf-8")

        await self.redis.hset(conv_key, mapping=update_data)  # type: ignore[arg-type]

        logger.debug("Диалог обновлён", conversation_id=conversation_id)
        return True

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


# Singleton instance
_conversation_store_instance: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    """Получить singleton instance ConversationStore.

    Returns:
        Глобальный экземпляр ConversationStore

    Raises:
        RuntimeError: Если ConversationStore не инициализирован

    """
    if _conversation_store_instance is None:
        msg = "ConversationStore не инициализирован. Вызовите set_conversation_store()."
        raise RuntimeError(msg)

    return _conversation_store_instance


def set_conversation_store(store: ConversationStore) -> None:
    """Установить global instance ConversationStore.

    Args:
        store: ConversationStore instance

    """
    global _conversation_store_instance
    _conversation_store_instance = store


def create_conversation_store(redis_client: Redis) -> ConversationStore:
    """Создать ConversationStore с существующим Redis клиентом.

    Args:
        redis_client: Async Redis client (можно использовать от SessionStore)

    Returns:
        Настроенный ConversationStore instance

    """
    store = ConversationStore(redis_client)
    logger.info("ConversationStore создан")
    return store
