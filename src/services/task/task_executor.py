"""Task Executor - выполнение задач генерации.

Отвечает ТОЛЬКО за выполнение задач генерации через LLM providers.
НЕ отвечает за очереди, webhooks, state management (SRP).

Example:
    >>> executor = TaskExecutor(provider_registry, state_manager)
    >>> await executor.execute_task(task_id, session_data)

"""


from src.providers.base import ChatMessage, GenerationParams, GenerationResult
from src.providers.registry import ProviderRegistry
from src.services.observability import trace_context
from src.shared.errors import GenerationFailedError, ModelNotFoundError
from src.shared.logging import get_logger

logger = get_logger()


class TaskExecutor:
    """Executor для выполнения задач генерации.

    Single Responsibility: выполнение LLM генерации.
    НЕ управляет очередями, НЕ отправляет webhooks, НЕ обновляет state.

    Attributes:
        provider_registry: Registry для получения LLM providers

    """

    def __init__(self, provider_registry: ProviderRegistry) -> None:
        """Инициализировать TaskExecutor.

        Args:
            provider_registry: Registry для доступа к providers

        """
        self.provider_registry = provider_registry
        logger.info("TaskExecutor инициализирован")

    async def execute_task(
        self,
        task_id: str,
        model: str,
        prompt: str | None,
        params: GenerationParams,
        messages: list[ChatMessage] | None = None,
    ) -> GenerationResult:
        """Выполнить задачу генерации.

        Args:
            task_id: ID задачи (для логирования и трейсинга)
            model: Название модели
            prompt: Промпт для генерации (или None если используются messages)
            params: Параметры генерации
            messages: Сообщения для multi-turn conversations (опционально)

        Returns:
            GenerationResult с результатом

        Raises:
            ModelNotFoundError: Если модель не найдена
            GenerationFailedError: Если генерация провалилась

        Note:
            Выполняется в Langfuse trace контексте для observability.
            Можно использовать либо prompt, либо messages.

        """
        input_preview = prompt[:100] if prompt else f"[{len(messages or [])} messages]"

        logger.info(
            "Начало выполнения задачи",
            task_id=task_id,
            model=model,
            has_messages=messages is not None,
            params=params.model_dump(exclude={"extra"}),
        )

        # Создать Langfuse trace для задачи
        async with trace_context(
            name="task_execution",
            input_data={"task_id": task_id, "model": model, "input": input_preview},
            metadata={"task_id": task_id, "model": model},
        ):
            # Получить provider
            try:
                provider = self.provider_registry.get(model)
            except KeyError as e:
                available = self.provider_registry.list_providers()
                f"Модель '{model}' не зарегистрирована. Доступные: {', '.join(available)}"

                logger.exception(
                    "Provider не найден",
                    task_id=task_id,
                    model=model,
                    available_models=available,
                )

                raise ModelNotFoundError(
                    model_name=model,
                ) from e

            # Выполнить генерацию
            try:
                result = await provider.generate(
                    prompt=prompt,
                    messages=messages,
                    params=params,
                )

                logger.info(
                    "Задача выполнена успешно",
                    task_id=task_id,
                    model=model,
                    tokens=result.usage.get("total_tokens", 0),
                    finish_reason=result.finish_reason,
                )

                return result

            except Exception as e:
                logger.exception(
                    "Ошибка генерации",
                    task_id=task_id,
                    model=model,
                    error=str(e),
                )

                # Map инфраструктурные ошибки в доменные
                raise GenerationFailedError(
                    message=f"Ошибка генерации: {e}",
                    details={"model": model, "error": str(e)},
                ) from e
