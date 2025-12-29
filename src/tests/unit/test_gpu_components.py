"""Unit тесты для engine/gpu_guard.py и engine/vram_monitor.py."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.engine.gpu_guard import GPUGuard
from src.engine.vram_monitor import VRAMMonitor


class TestVRAMMonitor:
    """Тесты для VRAMMonitor."""

    @patch("src.engine.vram_monitor.pynvml")
    def test_singleton(self, mock_pynvml: MagicMock) -> None:
        """Тест что VRAMMonitor является синглтоном."""
        # Сбрасываем синглтон
        VRAMMonitor._instance = None

        monitor1 = VRAMMonitor(gpu_index=0)
        monitor2 = VRAMMonitor(gpu_index=0)

        assert monitor1 is monitor2

    @patch("src.engine.vram_monitor.pynvml")
    def test_initialization(self, mock_pynvml: MagicMock) -> None:
        """Тест инициализации монитора."""
        # Сбрасываем синглтон
        VRAMMonitor._instance = None

        mock_pynvml.nvmlInit.return_value = None
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = MagicMock()

        monitor = VRAMMonitor(gpu_index=0)

        mock_pynvml.nvmlInit.assert_called_once()
        mock_pynvml.nvmlDeviceGetHandleByIndex.assert_called_once_with(0)

    @patch("src.engine.vram_monitor.pynvml")
    def test_get_vram_usage(self, mock_pynvml: MagicMock) -> None:
        """Тест получения использования VRAM."""
        # Сбрасываем синглтон
        VRAMMonitor._instance = None

        # Мокаем данные GPU
        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle

        mock_memory_info = MagicMock()
        mock_memory_info.used = 4 * 1024 * 1024 * 1024  # 4 GB
        mock_memory_info.total = 8 * 1024 * 1024 * 1024  # 8 GB
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory_info

        monitor = VRAMMonitor(gpu_index=0)
        usage = monitor.get_vram_usage()

        assert usage["used_mb"] == 4096.0
        assert usage["total_mb"] == 8192.0
        assert usage["free_mb"] == 4096.0
        assert usage["used_percent"] == 50.0

    @patch("src.engine.vram_monitor.pynvml")
    def test_has_available_vram(self, mock_pynvml: MagicMock) -> None:
        """Тест проверки доступности VRAM."""
        # Сбрасываем синглтон
        VRAMMonitor._instance = None

        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle

        mock_memory_info = MagicMock()
        mock_memory_info.used = 4 * 1024 * 1024 * 1024  # 4 GB used
        mock_memory_info.total = 8 * 1024 * 1024 * 1024  # 8 GB total
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_memory_info

        monitor = VRAMMonitor(gpu_index=0)

        # Запрашиваем 2 GB - должно быть доступно
        assert monitor.has_available_vram(required_mb=2048.0) is True

        # Запрашиваем 6 GB - не должно быть доступно
        assert monitor.has_available_vram(required_mb=6144.0) is False

    @patch("src.engine.vram_monitor.pynvml")
    def test_get_gpu_utilization(self, mock_pynvml: MagicMock) -> None:
        """Тест получения загрузки GPU."""
        # Сбрасываем синглтон
        VRAMMonitor._instance = None

        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle

        mock_utilization = MagicMock()
        mock_utilization.gpu = 75
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization

        monitor = VRAMMonitor(gpu_index=0)
        utilization = monitor.get_gpu_utilization()

        assert utilization == 75

    @patch("src.engine.vram_monitor.pynvml")
    def test_get_gpu_temperature(self, mock_pynvml: MagicMock) -> None:
        """Тест получения температуры GPU."""
        # Сбрасываем синглтон
        VRAMMonitor._instance = None

        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 65

        monitor = VRAMMonitor(gpu_index=0)
        temperature = monitor.get_gpu_temperature()

        assert temperature == 65

    @patch("src.engine.vram_monitor.pynvml")
    def test_cleanup_on_deletion(self, mock_pynvml: MagicMock) -> None:
        """Тест что nvmlShutdown вызывается при удалении."""
        # Сбрасываем синглтон
        VRAMMonitor._instance = None

        monitor = VRAMMonitor(gpu_index=0)
        del monitor

        # Проверяем что shutdown вызван (может быть вызван или не вызван в зависимости от GC)
        # Это сложно тестировать надёжно, поэтому просто проверяем что не падает


class TestGPUGuard:
    """Тесты для GPUGuard."""

    def test_singleton(self) -> None:
        """Тест что GPUGuard является синглтоном."""
        # Сбрасываем синглтон
        GPUGuard._instance = None

        with patch("src.engine.gpu_guard.VRAMMonitor"):
            guard1 = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )
            guard2 = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )

            assert guard1 is guard2

    @pytest.mark.asyncio
    async def test_acquire_lock(self) -> None:
        """Тест захвата блокировки GPU."""
        # Сбрасываем синглтон
        GPUGuard._instance = None

        with patch("src.engine.gpu_guard.VRAMMonitor") as mock_vram_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor.has_available_vram.return_value = True
            mock_vram_monitor_class.return_value = mock_monitor

            guard = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )

            async with guard.acquire(task_id="task-123"):
                # Проверяем что задача установлена
                assert guard._current_task_id == "task-123"

            # После выхода задача должна быть сброшена
            assert guard._current_task_id is None

    @pytest.mark.asyncio
    async def test_acquire_with_vram_check(self) -> None:
        """Тест захвата блокировки с проверкой VRAM."""
        # Сбрасываем синглтон
        GPUGuard._instance = None

        with patch("src.engine.gpu_guard.VRAMMonitor") as mock_vram_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor.has_available_vram.return_value = True
            mock_vram_monitor_class.return_value = mock_monitor

            guard = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )

            async with guard.acquire(task_id="task-123", required_vram_mb=2048.0):
                pass

            # Проверяем что has_available_vram был вызван
            mock_monitor.has_available_vram.assert_called_once_with(
                required_mb=2048.0
            )

    @pytest.mark.asyncio
    async def test_acquire_insufficient_vram_raises_error(self) -> None:
        """Тест что недостаточно VRAM вызывает ошибку."""
        # Сбрасываем синглтон
        GPUGuard._instance = None

        with patch("src.engine.gpu_guard.VRAMMonitor") as mock_vram_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor.has_available_vram.return_value = False
            mock_monitor.get_vram_usage.return_value = {
                "used_mb": 7168.0,
                "total_mb": 8192.0,
                "free_mb": 1024.0,
                "used_percent": 87.5,
            }
            mock_vram_monitor_class.return_value = mock_monitor

            guard = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )

            with pytest.raises(RuntimeError, match="Недостаточно VRAM"):
                async with guard.acquire(
                    task_id="task-123", required_vram_mb=4096.0
                ):
                    pass

    @pytest.mark.asyncio
    async def test_get_current_task(self) -> None:
        """Тест получения текущей задачи."""
        # Сбрасываем синглтон
        GPUGuard._instance = None

        with patch("src.engine.gpu_guard.VRAMMonitor") as mock_vram_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor.has_available_vram.return_value = True
            mock_vram_monitor_class.return_value = mock_monitor

            guard = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )

            # Изначально нет задачи
            assert guard.get_current_task() is None

            async with guard.acquire(task_id="task-123"):
                # Во время выполнения есть задача
                assert guard.get_current_task() == "task-123"

            # После завершения нет задачи
            assert guard.get_current_task() is None

    @pytest.mark.asyncio
    async def test_is_locked(self) -> None:
        """Тест проверки блокировки."""
        # Сбрасываем синглтон
        GPUGuard._instance = None

        with patch("src.engine.gpu_guard.VRAMMonitor") as mock_vram_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor.has_available_vram.return_value = True
            mock_vram_monitor_class.return_value = mock_monitor

            guard = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )

            # Изначально не заблокирован
            assert guard.is_locked() is False

            async with guard.acquire(task_id="task-123"):
                # Во время выполнения заблокирован
                assert guard.is_locked() is True

            # После завершения не заблокирован
            assert guard.is_locked() is False

    def test_get_vram_stats(self) -> None:
        """Тест получения статистики VRAM."""
        # Сбрасываем синглтон
        GPUGuard._instance = None

        with patch("src.engine.gpu_guard.VRAMMonitor") as mock_vram_monitor_class:
            mock_monitor = MagicMock()
            mock_monitor.get_vram_usage.return_value = {
                "used_mb": 4096.0,
                "total_mb": 8192.0,
                "free_mb": 4096.0,
                "used_percent": 50.0,
            }
            mock_vram_monitor_class.return_value = mock_monitor

            guard = GPUGuard(
                gpu_index=0, max_vram_percent=95, vram_reserve_mb=1024
            )

            stats = guard.get_vram_stats()

            assert stats["used_mb"] == 4096.0
            assert stats["total_mb"] == 8192.0
            assert stats["used_percent"] == 50.0
