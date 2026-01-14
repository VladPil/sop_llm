"""Webhook Service - отправка HTTP callbacks.

Отвечает ТОЛЬКО за отправку webhook callbacks.
НЕ отвечает за task execution, state management (SRP).

Example:
    >>> service = WebhookService()
    >>> await service.send_webhook(task_id, webhook_url, "completed", result_data)

"""

import asyncio
from typing import Any

import httpx

from src.core.config import settings
from src.services.observability import trace_operation
from src.shared.logging import get_logger

logger = get_logger()


class WebhookService:
    """Service для отправки webhook callbacks.

    Single Responsibility: HTTP callbacks с retry логикой.
    НЕ управляет tasks, НЕ обновляет state.

    Attributes:
        timeout: HTTP timeout в секундах
        max_retries: Максимум попыток retry

    """

    def __init__(
        self,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Инициализировать WebhookService.

        Args:
            timeout: HTTP timeout (defaults из settings)
            max_retries: Максимум retry (defaults из settings)

        """
        self.timeout = timeout or settings.webhook_timeout_seconds
        self.max_retries = max_retries or settings.webhook_max_retries

        logger.info(
            "WebhookService инициализирован",
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    @trace_operation(name="webhook_send")
    async def send_webhook(
        self,
        task_id: str,
        webhook_url: str,
        status: str,
        data: dict[str, Any],
    ) -> bool:
        """Отправить webhook callback с retry логикой.

        Использует exponential backoff для retry.

        Args:
            task_id: ID задачи
            webhook_url: URL для callback
            status: Статус задачи (completed, failed)
            data: Данные для отправки (result или error)

        Returns:
            True если webhook отправлен успешно, False иначе

        Note:
            НЕ бросает исключения - логирует ошибки и возвращает False.

        """
        logger.info(
            "Отправка webhook",
            task_id=task_id,
            url=webhook_url,
            status=status,
        )

        payload = {
            "task_id": task_id,
            "status": status,
            "data": data,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for attempt in range(self.max_retries + 1):
                    try:
                        response = await client.post(webhook_url, json=payload)
                        response.raise_for_status()

                        logger.info(
                            "Webhook отправлен успешно",
                            task_id=task_id,
                            url=webhook_url,
                            status_code=response.status_code,
                            attempt=attempt + 1,
                        )

                        return True

                    except httpx.HTTPError as e:
                        if attempt < self.max_retries:
                            backoff_seconds = 2**attempt
                            logger.warning(
                                "Webhook failed, повтор",
                                task_id=task_id,
                                url=webhook_url,
                                attempt=attempt + 1,
                                max_retries=self.max_retries,
                                backoff_seconds=backoff_seconds,
                                error=str(e),
                            )
                            await asyncio.sleep(backoff_seconds)
                        else:
                            logger.exception(
                                "Webhook failed после всех retry",
                                task_id=task_id,
                                url=webhook_url,
                                total_attempts=self.max_retries + 1,
                                error=str(e),
                            )
                            raise

        except Exception as e:
            logger.exception(
                "Не удалось отправить webhook",
                task_id=task_id,
                url=webhook_url,
                error=str(e),
            )
            return False

        return False
