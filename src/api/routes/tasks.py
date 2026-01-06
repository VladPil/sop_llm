"""Tasks API Routes для SOP LLM Executor.

Endpoints для управления задачами генерации.

Архитектура (после рефакторинга):
- IntakeAdapter: адаптация Intake-style запросов
- TaskOrchestrator: создание и выполнение задач
- Dependency Injection: FastAPI Depends для loose coupling
- Observability: trace_id в responses для корреляции с Langfuse
"""

from fastapi import APIRouter, HTTPException, status

try:
    from langfuse.decorators import langfuse_context
except (ImportError, AttributeError):
    try:
        from langfuse.client import langfuse_context
    except ImportError:
        class DummyContext:
            def flush(self):
                pass
        langfuse_context = DummyContext()

from src.api.schemas.requests import CreateTaskRequest
from src.api.schemas.responses import ErrorResponse, TaskResponse
from src.core import TaskStatus
from src.core.dependencies import IntakeAdapterDep, SessionStoreDep, TaskOrchestratorDep
from src.shared.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу генерации текста",
    description="""
Создаёт асинхронную задачу генерации текста и добавляет её в очередь обработки.

## Как это работает

1. Запрос валидируется и создаётся задача со статусом `pending`
2. Задача добавляется в priority queue
3. Возвращается `task_id` для отслеживания статуса
4. Задача обрабатывается в фоновом режиме
5. Результат можно получить через `GET /tasks/{task_id}` или webhook

## Основные параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `model` | string | Имя зарегистрированной модели |
| `prompt` | string | Текст промпта |
| `temperature` | float | Температура (0.0-2.0) |
| `max_tokens` | int | Максимум токенов в ответе |

## Дополнительные параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `response_format` | object | Structured Output (JSON Schema) |
| `idempotency_key` | string | Ключ дедупликации (TTL: 24 часа) |
| `webhook_url` | string | URL для callback при завершении |
| `priority` | int | Приоритет в очереди (0-100, больше = раньше) |

## Structured Output

Для получения структурированного JSON укажите `response_format` с типом `json_schema`
и JSON Schema в поле `json_schema`.

## Idempotency

При повторном запросе с тем же `idempotency_key` вернётся существующая задача вместо создания новой.

## Приоритет

Поле `priority` (0-100) определяет порядок обработки.
Задачи с большим приоритетом обрабатываются первыми.
""",
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
) -> TaskResponse:
    """Создать задачу генерации.

    Использует Dependency Injection для loose coupling:
    - IntakeAdapter: адаптация Intake-style запросов
    - TaskOrchestrator: создание и добавление в очередь
    - SessionStore: получение данных сессии

    Args:
        request: Параметры задачи
        orchestrator: TaskOrchestrator (DI)
        adapter: IntakeAdapter (DI)
        session_store: SessionStore (DI)

    Returns:
        TaskResponse с task_id, статусом и trace_id

    Raises:
        HTTPException: 404 если модель не найдена, 400 при ошибке валидации

    """
    try:
        # Адаптировать Intake-style запрос
        model, prompt, params = adapter.adapt_request(request)

        # Создать задачу через Orchestrator
        task_id = await orchestrator.submit_task(
            model=model,
            prompt=prompt,
            params=params,
            webhook_url=request.webhook_url,
            idempotency_key=request.idempotency_key,
            priority=request.priority,
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
    response_model=TaskResponse,
    summary="Получить статус и результат задачи",
    description="""
Возвращает текущий статус задачи и результат генерации (если задача завершена).

## Статусы задачи

| Статус | Описание |
|--------|----------|
| `pending` | Задача в очереди, ожидает обработки |
| `processing` | Задача выполняется |
| `completed` | Генерация успешно завершена |
| `failed` | Произошла ошибка |

## Polling

Опрашивайте этот endpoint с интервалом 1-2 секунды до получения статуса `completed` или `failed`.

## Структура результата (при status=completed)

| Поле | Описание |
|------|----------|
| `result.text` | Сгенерированный текст |
| `result.finish_reason` | Причина завершения |
| `result.usage.prompt_tokens` | Токены в промпте |
| `result.usage.completion_tokens` | Токены в ответе |
| `result.usage.total_tokens` | Всего токенов |

## Finish Reasons

| Reason | Описание |
|--------|----------|
| `stop` | Генерация завершена естественно |
| `length` | Достигнут лимит max_tokens |
| `content_filter` | Контент заблокирован фильтром |

## Observability

Поле `trace_id` содержит ID трейса в Langfuse для отладки.
""",
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
    description="""
Удаляет завершённую задачу из хранилища сессий.

## Когда можно удалить

Задачу можно удалить только если она в финальном статусе:
- `completed` — успешно завершена
- `failed` — завершена с ошибкой

## Когда нельзя удалить

Нельзя удалить задачу в статусе:
- `pending` — ожидает в очереди
- `processing` — выполняется

В этих случаях вернётся ошибка **409 Conflict**.

## Зачем удалять задачи

- Освобождение места в Redis
- Очистка после обработки результата
- GDPR compliance (удаление данных)

## Примечание

- Удаление необратимо
- Результат задачи будет потерян
- Задачи автоматически удаляются по TTL (настраивается)
""",
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
