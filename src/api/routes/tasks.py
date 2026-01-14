"""Tasks API Routes для SOP LLM Executor."""

from fastapi import APIRouter, HTTPException, status

from src.docs import tasks as docs

try:
    from langfuse.decorators import langfuse_context
except (ImportError, AttributeError):
    try:
        from langfuse.client import langfuse_context  # type: ignore[attr-defined]
    except ImportError:
        class DummyContext:
            """Fallback when langfuse is not installed."""

            def flush(self) -> None:
                pass

            def get_current_trace_id(self) -> None:
                return None
        langfuse_context = DummyContext()

from src.api.schemas.requests import CreateTaskRequest
from src.api.schemas.responses import ErrorResponse, TaskResponse
from src.core import TaskStatus
from src.core.dependencies import (
    ConversationStoreDep,
    IntakeAdapterDep,
    SessionStoreDep,
    TaskOrchestratorDep,
)
from src.providers.base import ChatMessage
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу генерации текста",
    description=docs.CREATE_TASK,
    responses={
        201: {
            "description": "Задача успешно создана и добавлена в очередь",
            "model": TaskResponse,
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task_abc123",
                        "status": "pending",
                        "model": "gpt-4-turbo",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                        "webhook_url": None,
                        "idempotency_key": "user-123-request-456",
                        "trace_id": "trace_xyz789",
                    }
                }
            },
        },
        400: {"model": ErrorResponse, "description": "Невалидные параметры запроса"},
        404: {"model": ErrorResponse, "description": "Указанная модель не зарегистрирована"},
    },
)
async def create_task(
    request: CreateTaskRequest,
    orchestrator: TaskOrchestratorDep,
    adapter: IntakeAdapterDep,
    session_store: SessionStoreDep,
    conversation_store: ConversationStoreDep,
) -> TaskResponse:
    """Создать задачу генерации.

    Использует Dependency Injection для loose coupling:
    - IntakeAdapter: адаптация Intake-style запросов
    - TaskOrchestrator: создание и добавление в очередь
    - SessionStore: получение данных сессии
    - ConversationStore: загрузка контекста диалога

    Args:
        request: Параметры задачи
        orchestrator: TaskOrchestrator (DI)
        adapter: IntakeAdapter (DI)
        session_store: SessionStore (DI)
        conversation_store: ConversationStore (DI)

    Returns:
        TaskResponse с task_id, статусом и trace_id

    Raises:
        HTTPException: 404 если модель не найдена, 400 при ошибке валидации

    """
    try:
        # Адаптировать Intake-style запрос
        model, prompt, params, conv_data = adapter.adapt_request(request)

        # Подготовить messages для multi-turn conversations
        messages: list[ChatMessage] | None = None

        if conv_data.messages is not None:
            # Явно указаны messages в запросе
            messages = conv_data.messages

        elif conv_data.conversation_id is not None:
            # Загрузить контекст из ConversationStore
            conversation = await conversation_store.get_conversation(conv_data.conversation_id)
            if conversation is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Диалог '{conv_data.conversation_id}' не найден",
                )

            # Получить историю сообщений
            context_messages = await conversation_store.get_context_messages(
                conv_data.conversation_id
            )

            # Добавить текущий промпт как user сообщение
            messages = list(context_messages)
            if prompt:
                messages.append(ChatMessage(role="user", content=prompt))

            # Модель из диалога если не указана в запросе
            if model is None and conversation.get("model"):
                model = conversation["model"]

            logger.info(
                "Загружен контекст диалога",
                conversation_id=conv_data.conversation_id,
                context_messages=len(context_messages),
                total_messages=len(messages),
            )

        # Проверка что есть prompt или messages
        if prompt is None and messages is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Необходимо указать prompt или messages",
            )

        # Проверка что модель определена
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Модель не указана: укажите 'model' в запросе или в диалоге",
            )

        # Создать задачу через Orchestrator
        task_id = await orchestrator.submit_task(
            model=model,
            prompt=prompt,
            messages=messages,
            params=params,
            webhook_url=request.webhook_url,
            idempotency_key=request.idempotency_key,
            priority=request.priority,
            conversation_id=conv_data.conversation_id if conv_data.save_to_conversation else None,
        )

        # Получить сессию для ответа
        session = await session_store.get_session(task_id)

        if session is None:
            msg = "Не удалось получить созданную задачу"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=msg,
            )

        # Получить trace_id из Langfuse context
        trace_id = getattr(langfuse_context.get_current_trace_id(), "trace_id", None) if hasattr(langfuse_context, "get_current_trace_id") else None

        return TaskResponse(
            task_id=session["task_id"],
            status=session["status"],
            model=session["model"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            webhook_url=session.get("webhook_url"),
            idempotency_key=session.get("idempotency_key"),
            trace_id=trace_id,
        )

    except HTTPException:
        raise

    except ValueError as e:
        # Валидационная ошибка (модель не найдена, невалидные параметры)
        logger.warning("Ошибка создания задачи", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "не зарегистрирована" in str(e) else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    except Exception as e:
        logger.exception("Критическая ошибка создания задачи", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания задачи: {e}",
        ) from e


@router.get(
    "/{task_id}",
    summary="Получить статус и результат задачи",
    description=docs.GET_TASK_STATUS,
    responses={
        200: {
            "description": "Статус и результат задачи",
            "model": TaskResponse,
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task_abc123",
                        "status": "completed",
                        "model": "gpt-4-turbo",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:05Z",
                        "finished_at": "2024-01-15T10:30:05Z",
                        "result": {
                            "text": "Сгенерированный ответ",
                            "finish_reason": "stop",
                            "usage": {
                                "prompt_tokens": 50,
                                "completion_tokens": 100,
                                "total_tokens": 150,
                            },
                        },
                        "trace_id": "trace_xyz789",
                    }
                }
            },
        },
        404: {"model": ErrorResponse, "description": "Задача с указанным ID не найдена"},
    },
)
async def get_task_status(
    task_id: str,
    session_store: SessionStoreDep,
) -> TaskResponse:
    """Получить статус задачи.

    Args:
        task_id: ID задачи
        session_store: SessionStore (DI)

    Returns:
        TaskResponse со статусом, результатом и trace_id

    Raises:
        HTTPException: 404 если задача не найдена

    """
    session = await session_store.get_session(task_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача '{task_id}' не найдена",
        )

    # Подготовить ответ
    response = TaskResponse(
        task_id=session["task_id"],
        status=session["status"],
        model=session["model"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        finished_at=session.get("finished_at"),
        webhook_url=session.get("webhook_url"),
        idempotency_key=session.get("idempotency_key"),
        trace_id=session.get("trace_id"),  # trace_id из сессии (если был сохранён)
    )

    # Результат (если completed)
    if session["status"] == TaskStatus.COMPLETED and "result" in session:
        response.result = session["result"]

    # Ошибка (если failed)
    if session["status"] == TaskStatus.FAILED and "error" in session:
        response.error = session["error"]

    return response


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу из системы",
    description=docs.DELETE_TASK,
    responses={
        204: {"description": "Задача успешно удалена"},
        404: {"model": ErrorResponse, "description": "Задача не найдена"},
        409: {"model": ErrorResponse, "description": "Нельзя удалить задачу в процессе выполнения"},
    },
)
async def delete_task(
    task_id: str,
    session_store: SessionStoreDep,
) -> None:
    """Удалить задачу.

    Args:
        task_id: ID задачи
        session_store: SessionStore (DI)

    Raises:
        HTTPException: 404 если задача не найдена, 409 если в процессе

    """
    session = await session_store.get_session(task_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача '{task_id}' не найдена",
        )

    # Нельзя удалить задачу в процессе
    if session["status"] in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Задача '{task_id}' в статусе '{session['status']}', нельзя удалить",
        )

    await session_store.delete_session(task_id)

    logger.info("Задача удалена через API", task_id=task_id)


@router.get(
    "/{task_id}/report",
    summary="Получить детальный отчёт о выполнении задачи",
    description=docs.GET_TASK_REPORT,
    responses={
        200: {
            "description": "Детальный отчёт о задаче",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task_abc123",
                        "status": "completed",
                        "model": "gpt-4-turbo",
                        "created_at": "2024-01-15T10:30:00Z",
                        "started_at": "2024-01-15T10:30:01Z",
                        "finished_at": "2024-01-15T10:30:05Z",
                        "metrics": {
                            "queue_wait_ms": 1000,
                            "inference_ms": 4000,
                            "total_ms": 5000,
                        },
                        "tokens": {
                            "prompt_tokens": 50,
                            "completion_tokens": 100,
                            "total_tokens": 150,
                        },
                        "logs": [
                            {"timestamp": "2024-01-15T10:30:00Z", "level": "INFO", "message": "Task created"},
                            {"timestamp": "2024-01-15T10:30:01Z", "level": "INFO", "message": "Task started"},
                        ],
                    }
                }
            },
        },
        404: {"model": ErrorResponse, "description": "Задача не найдена"},
    },
)
async def get_task_report(
    task_id: str,
    session_store: SessionStoreDep,
) -> dict:
    """Получить детальный отчёт о выполнении задачи.

    Args:
        task_id: ID задачи
        session_store: SessionStore (DI)

    Returns:
        Детальный отчёт с метриками и логами

    Raises:
        HTTPException: 404 если задача не найдена

    """
    session = await session_store.get_session(task_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача '{task_id}' не найдена",
        )

    # Получить логи задачи
    logs = await session_store.get_task_logs(task_id)

    # Рассчитать метрики
    metrics = {}
    created_at = session.get("created_at")
    started_at = session.get("started_at")
    finished_at = session.get("finished_at")

    if created_at and started_at:
        from datetime import datetime
        try:
            created = datetime.fromisoformat(created_at)
            started = datetime.fromisoformat(started_at)
            metrics["queue_wait_ms"] = int((started - created).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    if started_at and finished_at:
        from datetime import datetime
        try:
            started = datetime.fromisoformat(started_at)
            finished = datetime.fromisoformat(finished_at)
            metrics["inference_ms"] = int((finished - started).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    if created_at and finished_at:
        from datetime import datetime
        try:
            created = datetime.fromisoformat(created_at)
            finished = datetime.fromisoformat(finished_at)
            metrics["total_ms"] = int((finished - created).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    # Извлечь токены из result
    tokens = {}
    result = session.get("result", {})
    if isinstance(result, dict) and "usage" in result:
        usage = result["usage"]
        tokens = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    return {
        "task_id": task_id,
        "status": session.get("status"),
        "model": session.get("model"),
        "created_at": created_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "metrics": metrics,
        "tokens": tokens,
        "prompt": session.get("prompt"),
        "params": session.get("params", {}),
        "result": result if session.get("status") == TaskStatus.COMPLETED.value else None,
        "error": session.get("error") if session.get("status") == TaskStatus.FAILED.value else None,
        "webhook_url": session.get("webhook_url"),
        "idempotency_key": session.get("idempotency_key"),
        "trace_id": session.get("trace_id"),
        "logs": logs,
    }
