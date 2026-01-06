"""Task Orchestrator - координация задач генерации.

Orchestrator координирует TaskExecutor, WebhookService, TaskStateManager.
НЕ содержит бизнес-логику - делегирует специализированным компонентам.

Example:
    >>> orchestrator = TaskOrchestrator(executor, webhook, state_manager, queue)
    >>> await orchestrator.start()  # Запустить worker
    >>> await orchestrator.stop()   # Остановить worker

"""

import asyncio
import contextlib
import uuid

from src.providers.base import GenerationParams
from src.providers.registry import get_provider_registry
from src.services.observability import trace_context
from src.services.session_store import SessionStore
from src.services.task.task_executor import TaskExecutor
from src.services.task.task_state_manager import TaskStateManager
from src.services.task.webhook_service import WebhookService
from src.shared.errors import GenerationFailedError, ModelNotFoundError
from src.shared.logging import get_logger

logger = get_logger()


class TaskOrchestrator:
    """Orchestrator для координации выполнения задач.

    Orchestrator pattern: координирует компоненты, НЕ содержит логику.
    Делегирует ответственности:
    - TaskExecutor: выполнение генерации
    - WebhookService: отправка callbacks
    - TaskStateManager: управление состоянием
    - SessionStore: очередь и хранение

    Attributes:
        executor: Executor для выполнения генерации
        webhook_service: Service для отправки webhooks
        state_manager: Manager для управления состоянием
        session_store: Store для очереди и сессий

    """

    def __init__(
        self,
        executor: TaskExecutor,
        webhook_service: WebhookService,
        state_manager: TaskStateManager,
        session_store: SessionStore,
    ) -> None:
        """Инициализировать TaskOrchestrator.

        Args:
            executor: TaskExecutor для выполнения
            webhook_service: WebhookService для callbacks
            state_manager: TaskStateManager для state
            session_store: SessionStore для очереди

        """
        self.executor = executor
        self.webhook_service = webhook_service
        self.state_manager = state_manager
        self.session_store = session_store

        self._running = False
        self._worker_task: asyncio.Task[None] | None = None

        logger.info("TaskOrchestrator инициализирован")

    async def start(self) -> None:
        """Запустить background worker для обработки очереди."""
        if self._running:
            logger.warning("TaskOrchestrator уже запущен")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

        logger.info("TaskOrchestrator запущен")

    async def stop(self) -> None:
        """Остановить background worker."""
        if not self._running:
            return

        self._running = False

        if self._worker_task:
            self._worker_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task

        logger.info("TaskOrchestrator остановлен")

    async def submit_task(
        self,
        model: str,
        prompt: str,
        params: GenerationParams,
        webhook_url: str | None = None,
        idempotency_key: str | None = None,
        priority: float = 0.0,
    ) -> str:
        """Создать и добавить задачу в очередь.

        Args:
            model: Название модели
            prompt: Промпт для генерации
            params: Параметры генерации
            webhook_url: URL для callback (опционально)
            idempotency_key: Ключ идемпотентности (опционально)
            priority: Приоритет задачи

        Returns:
            task_id созданной задачи

        Raises:
            ValueError: Если модель не найдена или idempotency_key дублируется

        """
        # Проверить idempotency
        if idempotency_key:
            existing_task_id = await self.session_store.get_task_by_idempotency_key(
                idempotency_key
            )

            if existing_task_id:
                logger.info(
                    "Задача с таким idempotency_key уже существует",
                    idempotency_key=idempotency_key,
                    task_id=existing_task_id,
                )
                return existing_task_id

        # Проверить, что модель зарегистрирована
        provider_registry = get_provider_registry()
        if model not in provider_registry:
            available_models = provider_registry.list_providers()
            msg = f"Модель '{model}' не зарегистрирована. Доступные: {', '.join(available_models)}"
            raise ValueError(msg)

        # Создать task_id
        task_id = f"task-{uuid.uuid4().hex[:16]}"

        # Создать сессию
        await self.session_store.create_session(
            task_id=task_id,
            model=model,
            prompt=prompt,
            params=params.model_dump(),
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
        )

        # Добавить в очередь
        await self.session_store.enqueue_task(task_id, priority=priority)

        # Добавить лог
        await self.state_manager.add_log(task_id, "INFO", "Задача создана и добавлена в очередь")

        logger.info(
            "Задача создана",
            task_id=task_id,
            model=model,
            priority=priority,
            has_webhook=webhook_url is not None,
            has_idempotency=idempotency_key is not None,
        )

        return task_id

    async def _worker_loop(self) -> None:
        """Worker loop - обрабатывает задачи из очереди."""
        logger.info("Worker loop начат")

        while self._running:
            try:
                # Извлечь задачу из очереди
                task_id = await self.session_store.dequeue_task()

                if task_id is None:
                    # Очередь пуста, подождать
                    await asyncio.sleep(0.5)
                    continue

                # Обработать задачу в Langfuse trace контексте
                async with trace_context(
                    name="task_processing",
                    input_data={"task_id": task_id},
                    metadata={"task_id": task_id},
                ):
                    await self._process_task(task_id)

            except Exception as e:
                logger.exception("Ошибка в worker loop", error=str(e))
                await asyncio.sleep(1)

        logger.info("Worker loop завершён")

    async def _process_task(self, task_id: str) -> None:
        """Обработать задачу (координация компонентов).

        Оркестрирует:
        1. TaskStateManager - обновление статуса
        2. TaskExecutor - выполнение генерации
        3. WebhookService - отправка callback

        Args:
            task_id: ID задачи

        """
        logger.info("Начало обработки задачи", task_id=task_id)

        try:
            # Получить данные задачи
            session = await self.state_manager.get_session(task_id)

            if session is None:
                logger.error("Задача не найдена в session store", task_id=task_id)
                return

            # Установить как processing
            await self.state_manager.mark_as_processing(task_id)

            # Извлечь параметры
            model = session["model"]
            prompt = session["prompt"]
            params_dict = session["params"]
            webhook_url = session.get("webhook_url")

            # Подготовить параметры
            gen_params = GenerationParams(**params_dict)

            # Выполнить генерацию через Executor
            try:
                result = await self.executor.execute_task(
                    task_id=task_id,
                    model=model,
                    prompt=prompt,
                    params=gen_params,
                )

                # Сохранить результат через StateManager
                await self.state_manager.mark_as_completed(task_id, result)

                # Отправить webhook (если есть)
                if webhook_url:
                    result_dict = {
                        "text": result.text,
                        "finish_reason": result.finish_reason,
                        "usage": result.usage,
                        "model": result.model,
                        "extra": result.extra,
                    }
                    await self.webhook_service.send_webhook(
                        task_id=task_id,
                        webhook_url=webhook_url,
                        status="completed",
                        data=result_dict,
                    )

                logger.info(
                    "Задача завершена успешно",
                    task_id=task_id,
                    tokens=result.usage.get("total_tokens", 0),
                )

            except (ModelNotFoundError, GenerationFailedError) as e:
                # Доменная ошибка - обработать
                error_msg = f"{e.error_code}: {e.message}"
                await self._handle_task_failure(task_id, error_msg, webhook_url)

            except Exception as e:
                # Неожиданная ошибка
                error_msg = f"Неожиданная ошибка: {e}"
                logger.exception("Неожиданная ошибка выполнения", task_id=task_id, error=str(e))
                await self._handle_task_failure(task_id, error_msg, webhook_url)

        except Exception as e:
            logger.exception(
                "Критическая ошибка обработки задачи",
                task_id=task_id,
                error=str(e),
            )

        finally:
            # Освободить processing slot
            await self.state_manager.clear_processing()

    async def _handle_task_failure(
        self,
        task_id: str,
        error_msg: str,
        webhook_url: str | None,
    ) -> None:
        """Обработать ошибку задачи.

        Args:
            task_id: ID задачи
            error_msg: Сообщение об ошибке
            webhook_url: URL для webhook (если есть)

        """
        # Отметить как failed через StateManager
        await self.state_manager.mark_as_failed(task_id, error_msg)

        # Отправить webhook (если есть)
        if webhook_url:
            await self.webhook_service.send_webhook(
                task_id=task_id,
                webhook_url=webhook_url,
                status="failed",
                data={"error": error_msg},
            )


# Singleton instance
_orchestrator_instance: TaskOrchestrator | None = None


def get_task_orchestrator() -> TaskOrchestrator:
    """Получить singleton instance TaskOrchestrator.

    Returns:
        Глобальный экземпляр TaskOrchestrator

    Raises:
        RuntimeError: Если orchestrator не инициализирован

    """
    if _orchestrator_instance is None:
        msg = "TaskOrchestrator не инициализирован. Вызовите create_task_orchestrator() сначала."
        raise RuntimeError(msg)

    return _orchestrator_instance


def create_task_orchestrator(
    executor: TaskExecutor,
    webhook_service: WebhookService,
    state_manager: TaskStateManager,
    session_store: SessionStore,
) -> TaskOrchestrator:
    """Создать и инициализировать TaskOrchestrator.

    Args:
        executor: TaskExecutor instance
        webhook_service: WebhookService instance
        state_manager: TaskStateManager instance
        session_store: SessionStore instance

    Returns:
        TaskOrchestrator instance

    """
    global _orchestrator_instance

    _orchestrator_instance = TaskOrchestrator(
        executor=executor,
        webhook_service=webhook_service,
        state_manager=state_manager,
        session_store=session_store,
    )

    return _orchestrator_instance


# Для тестирования
def set_task_orchestrator(orchestrator: TaskOrchestrator) -> None:
    """Установить custom instance (для тестов).

    Args:
        orchestrator: Custom TaskOrchestrator instance

    """
    global _orchestrator_instance
    _orchestrator_instance = orchestrator
