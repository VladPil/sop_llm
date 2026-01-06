"""Langfuse Client Initialization and Singleton Management.

Отвечает за инициализацию и управление глобальным экземпляром Langfuse клиента.
Реализует паттерн Singleton для обеспечения единственной точки доступа.
"""

from langfuse import Langfuse
from loguru import logger

# Global Langfuse client instance (Singleton)
_langfuse_client: Langfuse | None = None


def initialize_langfuse(
    public_key: str,
    secret_key: str,
    host: str = "http://localhost:3000",
    enabled: bool = True,
) -> Langfuse | None:
    """Инициализирует Langfuse клиент для observability.

    Создает и настраивает глобальный экземпляр Langfuse клиента.
    При повторном вызове перезаписывает существующий экземпляр.

    Args:
        public_key: Публичный API ключ Langfuse.
        secret_key: Секретный API ключ Langfuse.
        host: URL сервера Langfuse (self-hosted или cloud).
        enabled: Флаг включения/отключения трекинга Langfuse.

    Returns:
        Инициализированный Langfuse клиент или None, если отключен.

    Raises:
        Exception: При ошибке инициализации клиента.

    Example:
        >>> client = initialize_langfuse(
        ...     public_key="pk_xxx",
        ...     secret_key="sk_xxx",
        ...     host="https://cloud.langfuse.com",
        ...     enabled=True
        ... )
        >>> assert client is not None
    """
    global _langfuse_client

    if not enabled:
        logger.warning("Langfuse observability is disabled")
        _langfuse_client = None
        return None

    try:
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            enabled=enabled,
        )
        logger.info(f"Langfuse client initialized: {host}")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        _langfuse_client = None
        raise


def get_langfuse_client() -> Langfuse | None:
    """Возвращает глобальный экземпляр Langfuse клиента.

    Returns:
        Langfuse клиент или None, если не инициализирован.

    Example:
        >>> client = get_langfuse_client()
        >>> if client:
        ...     client.flush()
    """
    return _langfuse_client


def flush_observations() -> None:
    """Отправляет все pending observations на Langfuse сервер.

    Должна вызываться перед остановкой приложения для гарантии
    отправки всех накопленных трейсов.

    Example:
        >>> flush_observations()  # Перед shutdown приложения
    """
    if not _langfuse_client:
        return

    try:
        _langfuse_client.flush()
        logger.info("Langfuse observations flushed")
    except Exception as e:
        logger.error(f"Failed to flush Langfuse observations: {e}")
