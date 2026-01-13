"""Интеграции с внешними библиотеками.

Конфигурация интеграций с внешними библиотеками для автоматического трейсинга.
В частности, настройка LiteLLM callbacks для Langfuse.
"""

from loguru import logger

from src.services.observability.utils import is_observability_enabled


def configure_litellm_callbacks() -> None:
    """Настраивает LiteLLM для автоматической отправки traces в Langfuse.

    Включает автоматический трейсинг всех LLM API вызовов через LiteLLM.
    При успешной настройке все вызовы к cloud LLM провайдерам
    (Anthropic, OpenAI, Google, и др.) будут автоматически логироваться.

    Note:
        Должна вызываться после инициализации Langfuse клиента.
        Требует Langfuse v2 и langfuse SDK <3.0.0.

    Raises:
        ImportError: Если LiteLLM не установлен.

    Example:
        >>> initialize_langfuse(...)
        >>> configure_litellm_callbacks()

    """
    if not is_observability_enabled():
        logger.warning("Пропуск настройки LiteLLM callback - Langfuse не инициализирован")
        return

    try:
        import litellm

        # Включаем Langfuse callback для автоматического трейсинга
        # Используем langfuse v2 SDK совместимый с litellm
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

        logger.info("LiteLLM callbacks настроены для Langfuse трейсинга")
    except ImportError:
        logger.error("LiteLLM не установлен, невозможно настроить callbacks")
    except Exception as e:
        logger.error(f"Не удалось настроить LiteLLM callbacks: {e}")
