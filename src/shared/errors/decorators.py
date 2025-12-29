"""Error handling decorators.

Декораторы для обработки ошибок.
"""

import functools
from typing import Any, Callable, TypeVar

from loguru import logger

from src.shared.errors.base import AppException
from src.shared.errors.domain_errors import ServiceUnavailableError

T = TypeVar("T")


def safe_deco(func: Callable[..., T]) -> Callable[..., T]:
    """Декоратор для безопасного выполнения функций.

    Перехватывает технические исключения и преобразует их в доменные.

    Args:
        func: Функция для декорирования.

    Returns:
        Обернутая функция.

    """

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> T:
        """Асинхронная обертка.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.

        Returns:
            Результат выполнения функции.

        Raises:
            AppException: Доменное исключение.

        """
        try:
            return await func(*args, **kwargs)
        except AppException:
            # Пробрасываем доменные исключения как есть
            raise
        except Exception as e:
            # Преобразуем технические ошибки в доменные
            logger.exception(
                f"Technical error in {func.__name__}",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )
            raise ServiceUnavailableError(
                message=f"Техническая ошибка: {type(e).__name__}",
                details={"error": str(e), "function": func.__name__},
            ) from e

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> T:
        """Синхронная обертка.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.

        Returns:
            Результат выполнения функции.

        Raises:
            AppException: Доменное исключение.

        """
        try:
            return func(*args, **kwargs)
        except AppException:
            # Пробрасываем доменные исключения как есть
            raise
        except Exception as e:
            # Преобразуем технические ошибки в доменные
            logger.exception(
                f"Technical error in {func.__name__}",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )
            raise ServiceUnavailableError(
                message=f"Техническая ошибка: {type(e).__name__}",
                details={"error": str(e), "function": func.__name__},
            ) from e

    # Определяем, асинхронная функция или нет
    if functools.iscoroutinefunction(func):
        return async_wrapper  # type: ignore
    return sync_wrapper  # type: ignore
