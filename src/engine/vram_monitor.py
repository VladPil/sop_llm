"""VRAM Monitor для SOP LLM Executor.

Обёртка над pynvml для мониторинга NVIDIA GPU памяти.
"""

from typing import Any
import pynvml
from config.settings import settings
from src.utils.logging import get_logger

logger = get_logger()


class VRAMMonitor:
    """Мониторинг VRAM на NVIDIA GPU через pynvml.

    Singleton pattern - только один монитор на приложение.
    """

    _instance: "VRAMMonitor | None" = None

    def __new__(cls) -> "VRAMMonitor":
        """Singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Инициализировать VRAM Monitor."""
        if self._initialized:  # type: ignore[has-type]
            return

        self.gpu_index = settings.gpu_index
        self.max_vram_percent = settings.max_vram_usage_percent
        self.vram_reserve_mb = settings.vram_reserve_mb

        self._handle: Any = None
        self._total_vram_bytes = 0

        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            self._total_vram_bytes = mem_info.total

            logger.info(
                "VRAMMonitor инициализирован",
                gpu_index=self.gpu_index,
                total_vram_gb=self._total_vram_bytes / (1024**3),
                max_percent=self.max_vram_percent,
                reserve_mb=self.vram_reserve_mb,
            )

            self._initialized = True  # type: ignore[misc]

        except pynvml.NVMLError as e:
            logger.error("Не удалось инициализировать pynvml", error=str(e))
            raise

    def get_vram_usage(self) -> dict[str, Any]:
        """Получить текущее использование VRAM.

        Returns:
            Словарь с метриками VRAM:
            - total_mb: Всего VRAM
            - used_mb: Используется VRAM
            - free_mb: Свободно VRAM
            - used_percent: Процент использования
        """
        if self._handle is None:
            msg = "VRAMMonitor не инициализирован"
            raise RuntimeError(msg)

        try:
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)

            return {
                "total_mb": mem_info.total / (1024**2),
                "used_mb": mem_info.used / (1024**2),
                "free_mb": mem_info.free / (1024**2),
                "used_percent": (mem_info.used / mem_info.total) * 100,
            }

        except pynvml.NVMLError as e:
            logger.error("Ошибка получения VRAM usage", error=str(e))
            raise

    def get_available_vram_mb(self) -> float:
        """Получить доступную VRAM с учётом резерва и лимита.

        Returns:
            Доступная VRAM в MB
        """
        usage = self.get_vram_usage()

        # Максимум VRAM с учётом процента
        max_allowed_mb = (usage["total_mb"] * self.max_vram_percent) / 100

        # Вычесть уже используемую VRAM и резерв
        available_mb = max_allowed_mb - usage["used_mb"] - self.vram_reserve_mb

        return max(0.0, available_mb)

    def can_allocate(self, required_mb: float) -> bool:
        """Проверить, можно ли выделить required_mb VRAM.

        Args:
            required_mb: Требуемая память в MB

        Returns:
            True если можно выделить
        """
        available_mb = self.get_available_vram_mb()
        return available_mb >= required_mb

    def get_gpu_info(self) -> dict[str, Any]:
        """Получить общую информацию о GPU.

        Returns:
            Словарь с метаданными GPU
        """
        if self._handle is None:
            msg = "VRAMMonitor не инициализирован"
            raise RuntimeError(msg)

        try:
            name = pynvml.nvmlDeviceGetName(self._handle)
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            cuda_version = pynvml.nvmlSystemGetCudaDriverVersion()

            # Temperature
            try:
                temperature = pynvml.nvmlDeviceGetTemperature(self._handle, pynvml.NVML_TEMPERATURE_GPU)
            except pynvml.NVMLError:
                temperature = None

            # Utilization
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
                gpu_util = util.gpu
            except pynvml.NVMLError:
                gpu_util = None

            return {
                "name": name.decode("utf-8") if isinstance(name, bytes) else name,
                "index": self.gpu_index,
                "driver_version": driver_version.decode("utf-8") if isinstance(driver_version, bytes) else driver_version,
                "cuda_version": f"{cuda_version // 1000}.{(cuda_version % 1000) // 10}",
                "temperature_celsius": temperature,
                "gpu_utilization_percent": gpu_util,
            }

        except pynvml.NVMLError as e:
            logger.error("Ошибка получения GPU info", error=str(e))
            raise

    def cleanup(self) -> None:
        """Очистить ресурсы pynvml."""
        try:
            pynvml.nvmlShutdown()
            logger.info("VRAMMonitor cleanup выполнен")
        except pynvml.NVMLError as e:
            logger.error("Ошибка cleanup VRAMMonitor", error=str(e))

    def __del__(self) -> None:
        """Деструктор - очистить pynvml при удалении."""
        if hasattr(self, "_initialized") and self._initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:  # noqa: S110
                pass


# =================================================================
# Global Instance
# =================================================================

def get_vram_monitor() -> VRAMMonitor:
    """Получить глобальный VRAMMonitor instance.

    Returns:
        Singleton VRAMMonitor
    """
    return VRAMMonitor()
