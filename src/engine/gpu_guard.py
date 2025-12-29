"""GPU Guard для SOP LLM Executor.

Обеспечивает эксклюзивный доступ к GPU через asyncio.Lock.
Критично для Single Worker Architecture (согласно ТЗ).
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
from src.engine.vram_monitor import get_vram_monitor
from src.utils.logging import get_logger

logger = get_logger()


class GPUGuard:
    """GPU Guard для эксклюзивного доступа к GPU.

    Singleton + asyncio.Lock паттерн:
    - Только одна задача может использовать GPU одновременно
    - Интеграция с VRAMMonitor для проверки доступной памяти
    - Context manager для безопасного acquire/release

    Usage:
        async with gpu_guard.acquire(task_id="task-123"):
            # Эксклюзивный доступ к GPU
            result = await model.generate(...)
    """

    _instance: "GPUGuard | None" = None

    def __new__(cls) -> "GPUGuard":
        """Singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Инициализировать GPU Guard."""
        if self._initialized:  # type: ignore[has-type]
            return

        self._lock = asyncio.Lock()
        self._current_task_id: str | None = None
        self._vram_monitor = get_vram_monitor()

        logger.info("GPUGuard инициализирован")

        self._initialized = True  # type: ignore[misc]

    @asynccontextmanager
    async def acquire(
        self,
        task_id: str,
        required_vram_mb: float | None = None,
    ) -> AsyncIterator[None]:
        """Получить эксклюзивный доступ к GPU.

        Args:
            task_id: ID задачи для логирования
            required_vram_mb: Требуемая VRAM (опционально, для проверки)

        Yields:
            None (контекст эксклюзивного доступа)

        Raises:
            RuntimeError: Недостаточно VRAM
        """
        # Проверить VRAM перед блокировкой (если указано)
        if required_vram_mb is not None:
            if not self._vram_monitor.can_allocate(required_vram_mb):
                available_mb = self._vram_monitor.get_available_vram_mb()
                msg = (
                    f"Недостаточно VRAM для задачи {task_id}. "
                    f"Требуется: {required_vram_mb:.0f} MB, доступно: {available_mb:.0f} MB"
                )
                logger.error(
                    "VRAM check failed",
                    task_id=task_id,
                    required_mb=required_vram_mb,
                    available_mb=available_mb,
                )
                raise RuntimeError(msg)

        # Ожидать освобождения GPU
        logger.debug("Ожидание GPU lock", task_id=task_id)
        async with self._lock:
            self._current_task_id = task_id

            logger.info(
                "GPU lock получен",
                task_id=task_id,
                vram_usage=self._vram_monitor.get_vram_usage(),
            )

            try:
                yield

            finally:
                # Освободить lock
                self._current_task_id = None

                logger.info(
                    "GPU lock освобождён",
                    task_id=task_id,
                    vram_usage=self._vram_monitor.get_vram_usage(),
                )

    def is_locked(self) -> bool:
        """Проверить, заблокирован ли GPU.

        Returns:
            True если GPU занят
        """
        return self._lock.locked()

    def get_current_task_id(self) -> str | None:
        """Получить ID текущей задачи, занявшей GPU.

        Returns:
            task_id или None если GPU свободен
        """
        return self._current_task_id

    async def wait_until_free(self, timeout: float | None = None) -> bool:
        """Ожидать освобождения GPU.

        Args:
            timeout: Максимальное время ожидания (секунды)

        Returns:
            True если GPU освободился, False если timeout

        Raises:
            asyncio.TimeoutError: Если timeout и GPU не освободился
        """
        if timeout is None:
            # Ожидать бесконечно
            async with self._lock:
                pass
            return True

        # Ожидать с timeout
        try:
            async with asyncio.timeout(timeout):
                async with self._lock:
                    pass
            return True

        except asyncio.TimeoutError:
            logger.warning(
                "GPU wait timeout",
                timeout_seconds=timeout,
                current_task=self._current_task_id,
            )
            return False


# =================================================================
# Global Instance
# =================================================================

# Singleton instance
_gpu_guard_instance: GPUGuard | None = None


def get_gpu_guard() -> GPUGuard:
    """Получить глобальный GPUGuard instance.

    Returns:
        Singleton GPUGuard
    """
    global _gpu_guard_instance  # noqa: PLW0603

    if _gpu_guard_instance is None:
        _gpu_guard_instance = GPUGuard()

    return _gpu_guard_instance
