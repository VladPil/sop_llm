"""Tasks API Routes для SOP LLM Executor.

Endpoints для управления задачами генерации.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.schemas.requests import CreateTaskRequest
from src.api.schemas.responses import ErrorResponse, TaskResponse
from src.providers.base import GenerationParams
from src.services.task_processor import get_task_processor
from src.utils.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу генерации",
    description="Создаёт новую задачу генерации и добавляет её в очередь",
    responses={
        201: {"description": "Задача создана успешно"},
        400: {"model": ErrorResponse, "description": "Невалидный запрос"},
        404: {"model": ErrorResponse, "description": "Модель не найдена"},
    },
)
async def create_task(request: CreateTaskRequest) -> TaskResponse:
    """Создать задачу генерации.

    Args:
        request: Параметры задачи

    Returns:
        TaskResponse с task_id и статусом "pending"

    Raises:
        HTTPException: 404 если модель не найдена

    """
    task_processor = get_task_processor()

    # Подготовить параметры генерации
    gen_params = GenerationParams(
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        top_k=request.top_k,
        frequency_penalty=request.frequency_penalty,
        presence_penalty=request.presence_penalty,
        stop_sequences=request.stop_sequences,
        seed=request.seed,
        response_format=request.response_format,
        grammar=request.grammar,
        extra=request.extra_params,
    )

    try:
        # Создать задачу
        task_id = await task_processor.submit_task(
            model=request.model,
            prompt=request.prompt,
            params=gen_params,
            webhook_url=request.webhook_url,
            idempotency_key=request.idempotency_key,
            priority=request.priority,
        )

        # Получить сессию для ответа
        session_store = task_processor.session_store
        session = await session_store.get_session(task_id)

        if session is None:
            msg = "Не удалось получить созданную задачу"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=msg,
            )

        return TaskResponse(
            task_id=session["task_id"],
            status=session["status"],
            model=session["model"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            webhook_url=session.get("webhook_url"),
            idempotency_key=session.get("idempotency_key"),
        )

    except ValueError as e:
        # Модель не найдена или другая валидационная ошибка
        logger.warning("Ошибка создания задачи", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    except Exception as e:
        logger.error("Критическая ошибка создания задачи", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания задачи: {e}",
        ) from e


@router.get(
    "/{task_id}",
    summary="Получить статус задачи",
    description="Возвращает текущий статус и результат задачи (если готов)",
    responses={
        200: {"description": "Статус задачи"},
        404: {"model": ErrorResponse, "description": "Задача не найдена"},
    },
)
async def get_task_status(task_id: str) -> TaskResponse:
    """Получить статус задачи.

    Args:
        task_id: ID задачи

    Returns:
        TaskResponse со статусом и результатом

    Raises:
        HTTPException: 404 если задача не найдена

    """
    task_processor = get_task_processor()
    session_store = task_processor.session_store

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
    )

    # Результат (если completed)
    if session["status"] == "completed" and "result" in session:
        response.result = session["result"]

    # Ошибка (если failed)
    if session["status"] == "failed" and "error" in session:
        response.error = session["error"]

    return response


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу",
    description="Удаляет задачу из session store (только для completed/failed)",
    responses={
        204: {"description": "Задача удалена"},
        404: {"model": ErrorResponse, "description": "Задача не найдена"},
        409: {"model": ErrorResponse, "description": "Задача в процессе выполнения"},
    },
)
async def delete_task(task_id: str) -> None:
    """Удалить задачу.

    Args:
        task_id: ID задачи

    Raises:
        HTTPException: 404 если задача не найдена, 409 если в процессе

    """
    task_processor = get_task_processor()
    session_store = task_processor.session_store

    session = await session_store.get_session(task_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача '{task_id}' не найдена",
        )

    # Нельзя удалить задачу в процессе
    if session["status"] in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Задача '{task_id}' в статусе '{session['status']}', нельзя удалить",
        )

    await session_store.delete_session(task_id)

    logger.info("Задача удалена через API", task_id=task_id)
