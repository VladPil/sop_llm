"""Unit тесты для services/task_processor.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.providers.base import GenerationResult, StreamChunk
from src.services.task_processor import TaskProcessor


@pytest.fixture
def mock_session_store() -> MagicMock:
    """Mock SessionStore для тестирования."""
    store = MagicMock()
    store.dequeue_task = AsyncMock(return_value=None)
    store.get_session = AsyncMock()
    store.update_session_status = AsyncMock()
    store.add_log = AsyncMock()
    store.get_queue_size = AsyncMock(return_value=0)
    return store


@pytest.fixture
def mock_provider_registry() -> MagicMock:
    """Mock ProviderRegistry для тестирования."""
    return MagicMock()


@pytest.fixture
def mock_gpu_guard() -> MagicMock:
    """Mock GPUGuard для тестирования."""
    guard = MagicMock()
    guard.acquire = AsyncMock()
    guard.__aenter__ = AsyncMock()
    guard.__aexit__ = AsyncMock()
    return guard


class TestTaskProcessor:
    """Тесты для TaskProcessor."""

    def test_initialization(self, mock_session_store: MagicMock) -> None:
        """Тест инициализации процессора."""
        processor = TaskProcessor(
            session_store=mock_session_store, poll_interval=1.0, webhook_timeout=5.0
        )

        assert processor.session_store == mock_session_store
        assert processor.poll_interval == 1.0
        assert processor.webhook_timeout == 5.0
        assert processor.is_running is False

    @pytest.mark.asyncio
    async def test_start_and_stop(self, mock_session_store: MagicMock) -> None:
        """Тест запуска и остановки процессора."""
        processor = TaskProcessor(
            session_store=mock_session_store, poll_interval=0.1
        )

        # Запускаем
        await processor.start()
        assert processor.is_running is True
        assert processor._worker_task is not None

        # Останавливаем
        await processor.stop()
        assert processor.is_running is False

    @pytest.mark.asyncio
    async def test_process_task_success(
        self, mock_session_store: MagicMock
    ) -> None:
        """Тест успешной обработки задачи."""
        # Подготавливаем mock сессии
        mock_session_store.get_session = AsyncMock(
            return_value={
                "task_id": "task-123",
                "status": "pending",
                "model": "test-model",
                "prompt": "Test prompt",
                "params": '{"temperature": 0.7}',
                "webhook_url": None,
            }
        )

        # Подготавливаем mock провайдера
        mock_provider = MagicMock()
        mock_provider.generate = AsyncMock(
            return_value=GenerationResult(
                text="Generated text",
                finish_reason="stop",
                usage={"total_tokens": 100},
                model="test-model",
            )
        )

        processor = TaskProcessor(session_store=mock_session_store)

        with patch(
            "src.services.task_processor.registry.get", return_value=mock_provider
        ), patch("src.services.task_processor.gpu_guard") as mock_guard:
            # Мокаем контекстный менеджер GPU Guard
            mock_guard.acquire = MagicMock()
            mock_guard.acquire.return_value.__aenter__ = AsyncMock()
            mock_guard.acquire.return_value.__aexit__ = AsyncMock()

            await processor._process_task("task-123")

            # Проверяем что статус обновлялся
            assert mock_session_store.update_session_status.call_count >= 2
            # Проверяем что провайдер вызван
            mock_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_task_model_not_found(
        self, mock_session_store: MagicMock
    ) -> None:
        """Тест обработки задачи с несуществующей моделью."""
        mock_session_store.get_session = AsyncMock(
            return_value={
                "task_id": "task-123",
                "status": "pending",
                "model": "nonexistent-model",
                "prompt": "Test prompt",
                "params": "{}",
                "webhook_url": None,
            }
        )

        processor = TaskProcessor(session_store=mock_session_store)

        with patch(
            "src.services.task_processor.registry.get",
            side_effect=KeyError("Model not found"),
        ):
            await processor._process_task("task-123")

            # Проверяем что задача помечена как failed
            calls = mock_session_store.update_session_status.call_args_list
            assert any("failed" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_process_streaming_task(
        self, mock_session_store: MagicMock
    ) -> None:
        """Тест обработки задачи с streaming."""
        mock_session_store.get_session = AsyncMock(
            return_value={
                "task_id": "task-123",
                "status": "pending",
                "model": "test-model",
                "prompt": "Test prompt",
                "params": '{"stream": true}',
                "webhook_url": None,
            }
        )

        # Подготавливаем mock провайдера с streaming
        async def mock_stream():
            yield StreamChunk(text="Hello")
            yield StreamChunk(text=" world")
            yield StreamChunk(
                text="!",
                finish_reason="stop",
                usage={"total_tokens": 50},
            )

        mock_provider = MagicMock()
        mock_provider.generate_stream = MagicMock(return_value=mock_stream())

        processor = TaskProcessor(session_store=mock_session_store)

        with patch(
            "src.services.task_processor.registry.get", return_value=mock_provider
        ), patch("src.services.task_processor.gpu_guard") as mock_guard:
            mock_guard.acquire = MagicMock()
            mock_guard.acquire.return_value.__aenter__ = AsyncMock()
            mock_guard.acquire.return_value.__aexit__ = AsyncMock()

            await processor._process_task("task-123")

            # Проверяем что провайдер вызван
            mock_provider.generate_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_callback_success(
        self, mock_session_store: MagicMock
    ) -> None:
        """Тест успешного webhook callback."""
        processor = TaskProcessor(session_store=mock_session_store)

        session_data = {
            "task_id": "task-123",
            "status": "completed",
            "model": "test-model",
        }

        with patch("src.services.task_processor.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await processor._send_webhook(
                "https://example.com/webhook", session_data
            )

            # Проверяем что POST запрос был сделан
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_callback_retry_on_failure(
        self, mock_session_store: MagicMock
    ) -> None:
        """Тест retry механизма для webhook."""
        processor = TaskProcessor(session_store=mock_session_store)

        session_data = {
            "task_id": "task-123",
            "status": "completed",
            "model": "test-model",
        }

        with patch("src.services.task_processor.httpx.AsyncClient") as mock_client:
            # Мокаем неудачный ответ
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await processor._send_webhook(
                "https://example.com/webhook", session_data
            )

            # Проверяем что было несколько попыток (max 3)
            assert (
                mock_client.return_value.__aenter__.return_value.post.call_count
                == 3
            )

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_session_store: MagicMock) -> None:
        """Тест получения статистики процессора."""
        mock_session_store.get_queue_size = AsyncMock(return_value=5)

        processor = TaskProcessor(session_store=mock_session_store)
        processor._tasks_processed = 10
        processor._tasks_failed = 2

        stats = await processor.get_stats()

        assert stats["is_running"] is False
        assert stats["tasks_processed"] == 10
        assert stats["tasks_failed"] == 2
        assert stats["queue_size"] == 5

    @pytest.mark.asyncio
    async def test_worker_loop_stops_gracefully(
        self, mock_session_store: MagicMock
    ) -> None:
        """Тест что worker loop корректно останавливается."""
        mock_session_store.dequeue_task = AsyncMock(return_value=None)

        processor = TaskProcessor(
            session_store=mock_session_store, poll_interval=0.01
        )

        await processor.start()
        # Даём немного времени на запуск
        await asyncio.sleep(0.05)
        await processor.stop()

        assert processor.is_running is False
        assert processor._worker_task is None


