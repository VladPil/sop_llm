"""SOP LLM - Task Endpoints.

Endpoints для управления задачами (создание, получение, удаление).
"""

import asyncio
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, status
from loguru import logger

from src.api.schemas import (
    TaskCreatedResponse,
    TaskRequest,
    TaskResponse,
    TaskStatus,
    TaskType,
)
from src.core.dependencies import (
    EmbeddingManagerDep,
    RedisCacheDep,
    TaskStorageDep,
    UnifiedLLMDep,
)
from src.shared.errors import TaskNotFoundError
from src.modules.monitoring.services.statistics import task_statistics

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "",
    response_model=TaskCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу",
    description="Создает новую задачу для обработки (генерация текста или embedding)",
)
async def create_task(
    request: TaskRequest,
    cache: RedisCacheDep,
    storage: TaskStorageDep,
    unified_llm: UnifiedLLMDep,
    embedding_manager: EmbeddingManagerDep,
) -> TaskCreatedResponse:
    """Создает новую задачу для обработки.

    Args:
        request: Запрос на создание задачи.
        cache: Redis cache instance.
        storage: Task storage instance.
        unified_llm: Unified LLM instance.
        embedding_manager: Embedding manager instance.

    Returns:
        Информация о созданной задаче.

    Raises:
        HTTPException: При ошибке создания задачи.

    """
    task_id = str(uuid.uuid4())

    logger.info(
        "Создание задачи",
        task_id=task_id,
        task_type=request.task_type.value,
    )

    # Проверяем кэш если включен
    cached_result = None
    if request.use_cache:
        cached_result = await cache.get(
            text=request.text,
            model=f"{request.provider.value}:{request.model or 'default'}",
            task_type=request.task_type.value,
            **request.parameters,
        )

    if cached_result:
        logger.info("Кэш найден для задачи", task_id=task_id)

        # Формируем детали обработки для кэша
        processing_details = {
            "original_request": {
                "text": request.text,
                "provider": request.provider.value,
                "model": request.model,
                "expected_format": request.expected_format,
                "preprocess_text": request.preprocess_text,
                "parameters": request.parameters,
            },
            "preprocessing": {},
            "llm_interaction": {
                "provider_used": request.provider.value,
                "model_used": request.model or "default",
                "raw_response": "Получено из кэша",
            },
            "postprocessing": {},
        }

        # Сохраняем результат как completed с request и processing_details
        task_data = {
            "task_id": task_id,
            "status": TaskStatus.COMPLETED,
            "request": request.model_dump(),
            "result": cached_result,
            "created_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
            "duration_ms": 0,
            "from_cache": True,
            "processing_details": processing_details,
        }
        storage.set(task_id, task_data)

        # Уведомляем систему мониторинга
        task_statistics.task_created(task_id, task_data)
        task_statistics.task_completed(
            task_id,
            cached_result,
            from_cache=True,
            processing_details=processing_details,
        )

        return TaskCreatedResponse(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            message="Результат получен из кэша",
        )

    # Сохраняем задачу в хранилище
    task_data = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "request": request.model_dump(),
        "created_at": datetime.now(timezone.utc),
        "result": None,
        "error": None,
    }
    storage.set(task_id, task_data)

    # Регистрируем в системе мониторинга
    task_statistics.task_created(task_id, task_data)

    # Запускаем обработку асинхронно (без ожидания)
    asyncio.create_task(
        _process_task(
            task_id, request, cache, storage, unified_llm, embedding_manager
        )
    )

    return TaskCreatedResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Задача создана и отправлена на обработку",
    )


async def _process_task(
    task_id: str,
    request: TaskRequest,
    cache: RedisCacheDep,
    storage: TaskStorageDep,
    unified_llm: UnifiedLLMDep,
    embedding_manager: EmbeddingManagerDep,
) -> None:
    """Внутренняя функция для обработки задачи.

    Args:
        task_id: ID задачи.
        request: Запрос задачи.
        cache: Redis cache instance.
        storage: Task storage instance.
        unified_llm: Unified LLM instance.
        embedding_manager: Embedding manager instance.

    """
    start_time = datetime.now(timezone.utc)

    try:
        # Обновляем статус
        task_data = storage.get(task_id)
        task_data["status"] = TaskStatus.PROCESSING
        storage.set(task_id, task_data)

        # Уведомляем систему мониторинга о начале обработки
        task_statistics.task_started(task_id)

        logger.info(
            "Обработка задачи",
            task_id=task_id,
            task_type=request.task_type.value,
        )

        # Обрабатываем в зависимости от типа
        if request.task_type == TaskType.GENERATE:
            # Обновляем прогресс
            task_statistics.task_progress(
                task_id, "Генерация текста", 20, "Отправка запроса к модели"
            )

            # Сохраняем детали обработки
            processing_details = {
                "original_request": {
                    "text": request.text,
                    "provider": request.provider.value,
                    "model": request.model,
                    "expected_format": request.expected_format,
                    "preprocess_text": request.preprocess_text,
                    "parameters": request.parameters,
                },
                "preprocessing": {},
                "llm_interaction": {},
                "postprocessing": {},
            }

            # Используем унифицированный интерфейс для генерации
            generation_result = await unified_llm.generate_with_timeout(
                prompt=request.text,
                provider=request.provider,
                model=request.model,
                expected_format=request.expected_format,
                json_schema=request.json_schema,
                preprocess_text=request.preprocess_text,
                **request.parameters,
            )
            result = generation_result

            # Дополняем детали обработки результатами
            processing_details["llm_interaction"] = {
                "provider_used": generation_result.get("provider", "unknown"),
                "model_used": generation_result.get("model", "unknown"),
                "tokens": generation_result.get("tokens", {}),
                "raw_response": generation_result.get("text", ""),
            }

            if generation_result.get("was_fixed"):
                processing_details["postprocessing"]["json_fixed"] = True
                processing_details["postprocessing"]["fix_attempts"] = (
                    generation_result.get("fix_attempts", 0)
                )

            # Сохраняем детали в task_data
            task_data["processing_details"] = processing_details

            task_statistics.task_progress(
                task_id, "Генерация текста", 90, "Обработка результата"
            )

        elif request.task_type == TaskType.EMBEDDING:
            task_statistics.task_progress(
                task_id, "Генерация embedding", 30, "Обработка текста"
            )

            # Сохраняем детали обработки для embedding
            processing_details = {
                "original_request": {
                    "text": request.text,
                    "provider": request.provider.value,
                    "model": request.model,
                    "expected_format": request.expected_format,
                    "parameters": request.parameters,
                },
                "preprocessing": {},
                "llm_interaction": {
                    "provider_used": "embedding_manager",
                    "model_used": "sentence-transformers",
                    "raw_response": "Embedding вектор размерности 384",
                },
                "postprocessing": {},
            }

            embedding = await embedding_manager.get_embedding(request.text)
            result = {"embedding": embedding, "dimension": len(embedding)}

            # Сохраняем детали в task_data
            task_data["processing_details"] = processing_details

            task_statistics.task_progress(
                task_id, "Генерация embedding", 90, "Завершение"
            )

        else:
            raise ValueError(f"Неизвестный тип задачи: {request.task_type}")

        # Сохраняем в кэш если нужно
        if request.use_cache:
            await cache.set(
                text=request.text,
                model=f"{request.provider.value}:{request.model or 'default'}",
                task_type=request.task_type.value,
                result=result,
                **request.parameters,
            )

        # Обновляем результат
        duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        task_data.update(
            {
                "status": TaskStatus.COMPLETED,
                "result": result,
                "completed_at": datetime.now(timezone.utc),
                "duration_ms": duration,
                "from_cache": False,
            }
        )
        storage.set(task_id, task_data)

        # Уведомляем систему мониторинга о завершении с деталями обработки
        task_statistics.task_completed(
            task_id,
            result,
            from_cache=False,
            processing_details=task_data.get("processing_details"),
        )

        logger.info(
            "Задача выполнена",
            task_id=task_id,
            duration_ms=round(duration, 2),
        )

    except Exception as e:
        logger.error(
            "Задача завершилась с ошибкой",
            task_id=task_id,
            error=str(e),
        )

        # Получаем полный стектрейс
        error_traceback = traceback.format_exc()

        task_data = storage.get(task_id)
        task_data.update(
            {
                "status": TaskStatus.FAILED,
                "error": str(e),
                "error_traceback": error_traceback,
                "completed_at": datetime.now(timezone.utc),
            }
        )
        storage.set(task_id, task_data)

        # Уведомляем систему мониторинга об ошибке
        task_statistics.task_failed(task_id, str(e), error_traceback)


@router.get(
    "",
    summary="Получить список всех задач",
    description="Возвращает список всех задач в системе",
    status_code=status.HTTP_200_OK,
)
async def get_all_tasks(storage: TaskStorageDep) -> Dict[str, Any]:
    """Получает список всех задач.

    Args:
        storage: Task storage instance.

    Returns:
        Список всех задач с их статусами и метаданными.

    """
    logger.debug("Получение списка всех задач")
    all_tasks = storage.get_all()

    # Преобразуем в список и сортируем по времени создания (новые первыми)
    tasks_list = []
    for task_id, task_data in all_tasks.items():
        # Сериализуем datetime объекты
        task_dict = dict(task_data)

        if "created_at" in task_dict and task_dict["created_at"]:
            if isinstance(task_dict["created_at"], datetime):
                task_dict["created_at"] = task_dict["created_at"].isoformat()

        if "completed_at" in task_dict and task_dict["completed_at"]:
            if isinstance(task_dict["completed_at"], datetime):
                task_dict["completed_at"] = task_dict["completed_at"].isoformat()

        tasks_list.append(task_dict)

    # Сортируем по времени создания (новые первыми)
    tasks_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"tasks": tasks_list, "total": len(tasks_list)}


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Получить статус задачи",
    description="Возвращает статус и результат задачи по ID",
    status_code=status.HTTP_200_OK,
)
async def get_task(task_id: str, storage: TaskStorageDep) -> TaskResponse:
    """Получает статус и результат задачи.

    Args:
        task_id: ID задачи.
        storage: Task storage instance.

    Returns:
        Информация о задаче.

    Raises:
        TaskNotFoundError: Если задача не найдена.

    """
    logger.debug("Получение задачи", task_id=task_id)

    if not storage.exists(task_id):
        raise TaskNotFoundError(task_id)

    task_data = storage.get(task_id)

    return TaskResponse(
        task_id=task_data["task_id"],
        status=task_data["status"],
        result=task_data.get("result"),
        error=task_data.get("error"),
        created_at=task_data.get("created_at"),
        completed_at=task_data.get("completed_at"),
        duration_ms=task_data.get("duration_ms"),
        request=task_data.get("request"),
        processing_details=task_data.get("processing_details"),
        from_cache=task_data.get("from_cache"),
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу",
    description="Удаляет задачу из хранилища",
)
async def delete_task(task_id: str, storage: TaskStorageDep) -> None:
    """Удаляет задачу из хранилища.

    Args:
        task_id: ID задачи.
        storage: Task storage instance.

    Raises:
        TaskNotFoundError: Если задача не найдена.

    """
    logger.info("Удаление задачи", task_id=task_id)

    if not storage.exists(task_id):
        raise TaskNotFoundError(task_id)

    storage.delete(task_id)
    logger.info("Задача удалена", task_id=task_id)
