"""Conversations API Routes для SOP LLM Executor.

Multi-turn conversations management endpoints.
"""

from fastapi import APIRouter, HTTPException, Query, status

from src.api.schemas.requests import (
    AddMessageRequest,
    CreateConversationRequest,
    UpdateConversationRequest,
)
from src.api.schemas.responses import (
    ConversationDetailResponse,
    ConversationMessage,
    ConversationResponse,
    ConversationsListResponse,
    ErrorResponse,
)
from src.core.dependencies import ConversationStoreDep
from src.docs import conversations as docs
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый диалог",
    description=docs.CREATE_CONVERSATION,
    responses={
        201: {
            "description": "Диалог успешно создан",
            "model": ConversationResponse,
        },
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"},
    },
)
async def create_conversation(
    request: CreateConversationRequest,
    conversation_store: ConversationStoreDep,
) -> ConversationResponse:
    """Создать новый диалог.

    Args:
        request: Параметры создания диалога
        conversation_store: ConversationStore (DI)

    Returns:
        ConversationResponse с conversation_id

    """
    try:
        conversation_id = await conversation_store.create_conversation(
            model=request.model,
            system_prompt=request.system_prompt,
            metadata=request.metadata,
        )

        # Получить созданный диалог
        conv = await conversation_store.get_conversation(conversation_id)

        if conv is None:
            msg = "Не удалось получить созданный диалог"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=msg,
            )

        return ConversationResponse(
            conversation_id=conv["conversation_id"],
            model=conv.get("model"),
            system_prompt=conv.get("system_prompt"),
            message_count=conv.get("message_count", 0),
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            metadata=conv.get("metadata"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка создания диалога", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания диалога: {e}",
        ) from e


@router.get(
    "/",
    summary="Получить список диалогов",
    description=docs.LIST_CONVERSATIONS,
    responses={
        200: {
            "description": "Список диалогов",
            "model": ConversationsListResponse,
        },
    },
)
async def list_conversations(
    conversation_store: ConversationStoreDep,
    limit: int = Query(default=100, ge=1, le=1000, description="Максимум диалогов"),
    offset: int = Query(default=0, ge=0, description="Смещение для пагинации"),
) -> ConversationsListResponse:
    """Получить список диалогов.

    Args:
        conversation_store: ConversationStore (DI)
        limit: Максимум диалогов
        offset: Смещение для пагинации

    Returns:
        ConversationsListResponse со списком диалогов

    """
    conversations = await conversation_store.list_conversations(
        limit=limit,
        offset=offset,
    )

    return ConversationsListResponse(
        conversations=[
            ConversationResponse(
                conversation_id=conv["conversation_id"],
                model=conv.get("model"),
                system_prompt=conv.get("system_prompt"),
                message_count=conv.get("message_count", 0),
                created_at=conv["created_at"],
                updated_at=conv["updated_at"],
                metadata=conv.get("metadata"),
            )
            for conv in conversations
        ],
        total=len(conversations),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{conversation_id}",
    summary="Получить информацию о диалоге",
    description=docs.GET_CONVERSATION_DETAIL,
    responses={
        200: {
            "description": "Информация о диалоге",
            "model": ConversationDetailResponse,
        },
        404: {"model": ErrorResponse, "description": "Диалог не найден"},
    },
)
async def get_conversation(
    conversation_id: str,
    conversation_store: ConversationStoreDep,
    include_messages: bool = Query(
        default=True,
        description="Включить историю сообщений в ответ",
    ),
) -> ConversationDetailResponse:
    """Получить информацию о диалоге.

    Args:
        conversation_id: ID диалога
        conversation_store: ConversationStore (DI)
        include_messages: Включить сообщения в ответ

    Returns:
        ConversationDetailResponse с информацией о диалоге

    Raises:
        HTTPException: 404 если диалог не найден

    """
    conv = await conversation_store.get_conversation(conversation_id)

    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Диалог '{conversation_id}' не найден",
        )

    messages = []
    if include_messages:
        raw_messages = await conversation_store.get_messages(conversation_id)
        messages = [
            ConversationMessage(
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["timestamp"],
            )
            for msg in raw_messages
        ]

    return ConversationDetailResponse(
        conversation_id=conv["conversation_id"],
        model=conv.get("model"),
        system_prompt=conv.get("system_prompt"),
        message_count=conv.get("message_count", 0),
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        metadata=conv.get("metadata"),
        messages=messages,
    )


@router.patch(
    "/{conversation_id}",
    summary="Обновить метаданные диалога",
    description=docs.UPDATE_CONVERSATION,
    responses={
        200: {
            "description": "Диалог обновлён",
            "model": ConversationResponse,
        },
        404: {"model": ErrorResponse, "description": "Диалог не найден"},
    },
)
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    conversation_store: ConversationStoreDep,
) -> ConversationResponse:
    """Обновить метаданные диалога.

    Args:
        conversation_id: ID диалога
        request: Параметры обновления
        conversation_store: ConversationStore (DI)

    Returns:
        ConversationResponse с обновлённой информацией

    Raises:
        HTTPException: 404 если диалог не найден

    """
    # Проверить существование
    conv = await conversation_store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Диалог '{conversation_id}' не найден",
        )

    # Обновить
    await conversation_store.update_conversation(
        conversation_id=conversation_id,
        model=request.model,
        system_prompt=request.system_prompt,
        metadata=request.metadata,
    )

    # Получить обновлённый диалог
    conv = await conversation_store.get_conversation(conversation_id)

    return ConversationResponse(
        conversation_id=conv["conversation_id"],
        model=conv.get("model"),
        system_prompt=conv.get("system_prompt"),
        message_count=conv.get("message_count", 0),
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        metadata=conv.get("metadata"),
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить диалог",
    description=docs.DELETE_CONVERSATION,
    responses={
        204: {"description": "Диалог удалён"},
        404: {"model": ErrorResponse, "description": "Диалог не найден"},
    },
)
async def delete_conversation(
    conversation_id: str,
    conversation_store: ConversationStoreDep,
) -> None:
    """Удалить диалог.

    Args:
        conversation_id: ID диалога
        conversation_store: ConversationStore (DI)

    Raises:
        HTTPException: 404 если диалог не найден

    """
    deleted = await conversation_store.delete_conversation(conversation_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Диалог '{conversation_id}' не найден",
        )

    logger.info("Диалог удалён через API", conversation_id=conversation_id)


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить сообщение в диалог",
    description=docs.ADD_MESSAGE,
    responses={
        201: {
            "description": "Сообщение добавлено",
            "model": ConversationMessage,
        },
        404: {"model": ErrorResponse, "description": "Диалог не найден"},
    },
)
async def add_message(
    conversation_id: str,
    request: AddMessageRequest,
    conversation_store: ConversationStoreDep,
) -> ConversationMessage:
    """Добавить сообщение в диалог.

    Args:
        conversation_id: ID диалога
        request: Параметры сообщения
        conversation_store: ConversationStore (DI)

    Returns:
        Добавленное сообщение

    Raises:
        HTTPException: 404 если диалог не найден

    """
    added = await conversation_store.add_message(
        conversation_id=conversation_id,
        role=request.role,
        content=request.content,
    )

    if not added:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Диалог '{conversation_id}' не найден",
        )

    # Получить добавленное сообщение (последнее)
    messages = await conversation_store.get_messages(conversation_id, limit=1)

    if not messages:
        # Fallback - вернуть данные из запроса
        from datetime import datetime

        return ConversationMessage(
            role=request.role,
            content=request.content,
            timestamp=datetime.utcnow().isoformat(),
        )

    msg = messages[-1]
    return ConversationMessage(
        role=msg["role"],
        content=msg["content"],
        timestamp=msg["timestamp"],
    )


@router.get(
    "/{conversation_id}/messages",
    summary="Получить сообщения диалога",
    description=docs.GET_MESSAGES,
    responses={
        200: {
            "description": "Список сообщений",
            "content": {
                "application/json": {
                    "example": {
                        "messages": [
                            {"role": "user", "content": "Hello", "timestamp": "2024-01-15T10:30:00Z"},
                            {"role": "assistant", "content": "Hi!", "timestamp": "2024-01-15T10:30:01Z"},
                        ]
                    }
                }
            },
        },
        404: {"model": ErrorResponse, "description": "Диалог не найден"},
    },
)
async def get_messages(
    conversation_id: str,
    conversation_store: ConversationStoreDep,
    limit: int | None = Query(
        default=None,
        ge=1,
        le=1000,
        description="Максимум сообщений (последние N)",
    ),
) -> dict:
    """Получить сообщения диалога.

    Args:
        conversation_id: ID диалога
        conversation_store: ConversationStore (DI)
        limit: Максимум сообщений

    Returns:
        Список сообщений

    Raises:
        HTTPException: 404 если диалог не найден

    """
    # Проверить существование диалога
    conv = await conversation_store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Диалог '{conversation_id}' не найден",
        )

    raw_messages = await conversation_store.get_messages(conversation_id, limit=limit)

    messages = [
        ConversationMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"],
        )
        for msg in raw_messages
    ]

    return {"messages": messages}


@router.delete(
    "/{conversation_id}/messages",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Очистить историю сообщений",
    description=docs.CLEAR_MESSAGES,
    responses={
        204: {"description": "История очищена"},
        404: {"model": ErrorResponse, "description": "Диалог не найден"},
    },
)
async def clear_messages(
    conversation_id: str,
    conversation_store: ConversationStoreDep,
) -> None:
    """Очистить историю сообщений диалога.

    Args:
        conversation_id: ID диалога
        conversation_store: ConversationStore (DI)

    Raises:
        HTTPException: 404 если диалог не найден

    """
    cleared = await conversation_store.clear_messages(conversation_id)

    if not cleared:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Диалог '{conversation_id}' не найден",
        )

    logger.info("История диалога очищена через API", conversation_id=conversation_id)
