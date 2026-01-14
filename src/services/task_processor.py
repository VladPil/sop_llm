"""Task Processor для SOP LLM Executor.

Обработчик задач генерации из Redis queue.
Single Worker Architecture - обрабатывает задачи последовательно.
"""

import asyncio
import contextlib
import uuid
from typing import Any

import httpx

from src.core.config import settings
from src.providers.base import GenerationParams
from src.providers.registry import get_provider_registry
from src.services.session_store import SessionStore
from src.shared.logging import get_logger

logger = get_logger()


class TaskProcessor:
    """Процессор задач генерации.

    Single Worker Architecture:
    - Обрабатывает одну задачу за раз
    - Использует GPU Guard для эксклюзивного доступа
    - Поддерживает webhook callbacks
    - Обновляет статус задач в Redis
    """

    def __init__(
        self,
        session_store: SessionStore,
    ) -> None:
        """Инициализировать Task Processor.

        Args:
            session_store: Session store для управления задачами

        """
        self.session_store = session_store
        self.provider_registry = get_provider_registry()
        self._running = False
        self._worker_task: asyncio.Task[None] | None = None
        logger.info("TaskProcessor инициализирован")

    async def start(self) -> None:
        """Запустить обработчик задач (background worker)."""
        if self._running:
            logger.warning("TaskProcessor уже запущен")
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

        logger.info("TaskProcessor запущен")

    async def stop(self) -> None:
        """Остановить обработчик задач."""
        if not self._running:
            return

        self._running = False

        if self._worker_task:
            self._worker_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task

        logger.info("TaskProcessor остановлен")

    async def _worker_loop(self) -> None:
        """Worker loop - обрабатывает задачи из очереди."""
        logger.info("Worker loop начат")

        while self._running:
            try:
                task_id = await self.session_store.dequeue_task()

                if task_id is None:
                    await asyncio.sleep(0.5)
                    continue

                await self._process_task(task_id)

            except Exception as e:
                logger.exception("Ошибка в worker loop", error=str(e))
                await asyncio.sleep(1)

        logger.info("Worker loop завершён")

    async def _process_task(self, task_id: str) -> None:
        """Обработать задачу.

        Args:
            task_id: ID задачи

        """
        logger.info("Начало обработки задачи", task_id=task_id)

        try:
            session = await self.session_store.get_session(task_id)

            if session is None:
                logger.error("Задача не найдена в session store", task_id=task_id)
                return

            await self.session_store.set_processing_task(task_id)
            await self.session_store.update_session_status(task_id, "processing")

            model_name = session["model"]
            prompt = session["prompt"]
            params_dict = session["params"]

            try:
                provider = self.provider_registry.get_or_create(model_name)
            except KeyError:
                error_msg = f"Модель '{model_name}' не найдена в пресетах"
                logger.exception(error_msg, task_id=task_id)
                await self._handle_task_failure(task_id, error_msg, session)
                return

            gen_params = GenerationParams(**params_dict)

            try:
                result = await provider.generate(prompt, gen_params)

                result_dict = {
                    "text": result.text,
                    "finish_reason": result.finish_reason,
                    "usage": result.usage,
                    "model": result.model,
                    "extra": result.extra,
                }

                await self.session_store.update_session_status(
                    task_id,
                    "completed",
                    result=result_dict,
                )

                logger.info(
                    "Задача завершена успешно",
                    task_id=task_id,
                    tokens=result.usage["total_tokens"],
                )

                webhook_url = session.get("webhook_url")
                if webhook_url:
                    await self._send_webhook(task_id, webhook_url, "completed", result_dict)

            except Exception as e:
                error_msg = f"Ошибка генерации: {e}"
                logger.exception("Ошибка генерации", task_id=task_id, error=str(e))
                await self._handle_task_failure(task_id, error_msg, session)

        except Exception as e:
            logger.exception(
                "Критическая ошибка обработки задачи",
                task_id=task_id,
                error=str(e),
            )

        finally:
            # Очистить processing task
            await self.session_store.clear_processing_task()

    async def _handle_task_failure(
        self,
        task_id: str,
        error_msg: str,
        session: dict[str, Any],
    ) -> None:
        """Обработать ошибку задачи.

        Args:
            task_id: ID задачи
            error_msg: Сообщение об ошибке
            session: Данные сессии

        """
        await self.session_store.update_session_status(
            task_id,
            "failed",
            error=error_msg,
        )

        webhook_url = session.get("webhook_url")
        if webhook_url:
            await self._send_webhook(task_id, webhook_url, "failed", {"error": error_msg})

    async def _send_webhook(
        self,
        task_id: str,
        webhook_url: str,
        status: str,
        data: dict[str, Any],
    ) -> None:
        """Отправить webhook callback.

        Args:
            task_id: ID задачи
            webhook_url: URL для callback
            status: Статус задачи
            data: Данные для отправки

        """
        logger.info("Отправка webhook", task_id=task_id, url=webhook_url, status=status)

        payload = {
            "task_id": task_id,
            "status": status,
            "data": data,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                for attempt in range(settings.webhook_max_retries + 1):
                    try:
                        response = await client.post(webhook_url, json=payload)
                        response.raise_for_status()

                        logger.info(
                            "Webhook отправлен успешно",
                            task_id=task_id,
                            status_code=response.status_code,
                        )
                        return

                    except httpx.HTTPError as e:
                        if attempt < settings.webhook_max_retries:
                            logger.warning(
                                "Webhook failed, повтор",
                                task_id=task_id,
                                attempt=attempt + 1,
                                error=str(e),
                            )
                            await asyncio.sleep(2**attempt)
                        else:
                            raise

        except Exception as e:
            logger.exception(
                "Не удалось отправить webhook",
                task_id=task_id,
                url=webhook_url,
                error=str(e),
            )

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
            task_id

        Raises:
            ValueError: Если idempotency_key уже существует

        """
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

        task_id = f"task-{uuid.uuid4().hex[:16]}"

        await self.session_store.create_session(
            task_id=task_id,
            model=model,
            prompt=prompt,
            params=params.model_dump(),
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
        )

        await self.session_store.enqueue_task(task_id, priority=priority)
        await self.session_store.add_log(task_id, "INFO", "Задача создана и добавлена в очередь")

        logger.info(
            "Задача создана",
            task_id=task_id,
            model=model,
            priority=priority,
            has_webhook=webhook_url is not None,
            has_idempotency=idempotency_key is not None,
        )

        return task_id


_task_processor_instance: TaskProcessor | None = None


def get_task_processor() -> TaskProcessor:
    """Получить глобальный TaskProcessor instance.

    Returns:
        Singleton TaskProcessor

    """
    if _task_processor_instance is None:
        msg = "TaskProcessor не инициализирован. Вызовите create_task_processor() сначала."
        raise RuntimeError(msg)

    return _task_processor_instance


def create_task_processor(session_store: SessionStore) -> TaskProcessor:
    """Создать и инициализировать TaskProcessor.

    Args:
        session_store: Session store instance

    Returns:
        TaskProcessor instance

    """
    global _task_processor_instance

    _task_processor_instance = TaskProcessor(session_store)
    return _task_processor_instance
