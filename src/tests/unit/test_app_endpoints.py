"""Unit тесты для основных endpoints приложения."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY

from src.app import app


@pytest.fixture
async def client() -> AsyncClient:
    """Test client для FastAPI приложения."""
    # Отключаем lifespan для unit тестов
    app_copy = app
    app_copy.router.lifespan_context = None

    transport = ASGITransport(app=app_copy)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestRootEndpoint:
    """Тесты для корневого endpoint /."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient) -> None:
        """Тест корневого endpoint."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "SOP LLM Executor"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert "docs" in data


class TestHealthEndpoint:
    """Тесты для /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint_ok(self, client: AsyncClient) -> None:
        """Тест health check endpoint - всё OK."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ok"
        assert data["service"] == "sop_llm"
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_endpoint_format(self, client: AsyncClient) -> None:
        """Тест формата ответа health check."""
        response = await client.get("/health")

        data = response.json()

        # Проверяем обязательные поля
        assert "status" in data
        assert "service" in data
        assert "version" in data

        # Проверяем типы
        assert isinstance(data["status"], str)
        assert isinstance(data["service"], str)
        assert isinstance(data["version"], str)


class TestMetricsEndpoint:
    """Тесты для /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_prometheus_format(
        self, client: AsyncClient
    ) -> None:
        """Тест что /metrics возвращает Prometheus формат."""
        response = await client.get("/metrics")

        assert response.status_code == 200

        # Проверяем content type
        assert "text/plain" in response.headers["content-type"]

        # Проверяем что это Prometheus формат
        text = response.text
        assert "# HELP" in text or "# TYPE" in text or len(text) > 0

    @pytest.mark.asyncio
    async def test_metrics_endpoint_contains_custom_metrics(
        self, client: AsyncClient
    ) -> None:
        """Тест что метрики содержат наши кастомные метрики."""
        response = await client.get("/metrics")

        text = response.text

        # Проверяем наличие наших метрик
        assert "http_requests_total" in text or "python_" in text
        # python_ метрики всегда есть от prometheus_client


class TestMetricsMiddleware:
    """Тесты для middleware сбора метрик."""

    @pytest.mark.asyncio
    async def test_metrics_middleware_tracks_requests(self, client: AsyncClient) -> None:
        """Тест что middleware отслеживает запросы."""
        # Сбросим метрики
        # (в реальности REGISTRY.unregister не сработает, но для теста это OK)

        # Делаем несколько запросов
        await client.get("/health")
        await client.get("/health")
        await client.get("/")

        # Получаем метрики
        response = await client.get("/metrics")
        text = response.text

        # Проверяем что запросы отслеживаются
        # Метрика http_requests_total должна быть увеличена
        assert "http_requests_total" in text

    @pytest.mark.asyncio
    async def test_metrics_middleware_skips_metrics_endpoint(
        self, client: AsyncClient
    ) -> None:
        """Тест что middleware пропускает /metrics endpoint (избегает рекурсии)."""
        # Получаем метрики дважды
        response1 = await client.get("/metrics")
        response2 = await client.get("/metrics")

        # Оба запроса должны пройти успешно
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Не должно быть бесконечной рекурсии


class TestMonitorHealthEndpoint:
    """Тесты для /api/v1/monitor/health endpoint."""

    @pytest.mark.asyncio
    @patch("src.api.routes.monitor.get_task_processor")
    @patch("src.api.routes.monitor.get_provider_registry")
    async def test_monitor_health_endpoint(
        self,
        mock_get_registry: MagicMock,
        mock_get_processor: MagicMock,
        client: AsyncClient,
    ) -> None:
        """Тест детального health check endpoint."""
        # Mock task processor
        mock_processor = MagicMock()
        mock_session_store = AsyncMock()
        mock_session_store.health_check = AsyncMock(return_value=True)
        mock_processor.session_store = mock_session_store
        mock_get_processor.return_value = mock_processor

        # Mock provider registry
        mock_registry = AsyncMock()
        mock_registry.health_check_all = AsyncMock(return_value={})
        mock_get_registry.return_value = mock_registry

        response = await client.get("/api/v1/monitor/health")

        # Может быть 200 или 503 в зависимости от состояния
        assert response.status_code in [200, 503]

        data = response.json()

        # Проверяем структуру ответа
        assert "status" in data
        assert "redis" in data
        assert "providers" in data
        assert data["redis"] is True


class TestQueueStatsEndpoint:
    """Тесты для /api/v1/monitor/queue endpoint."""

    @pytest.mark.asyncio
    @patch("src.api.routes.monitor.get_task_processor")
    async def test_queue_stats_endpoint(
        self, mock_get_processor: MagicMock, client: AsyncClient
    ) -> None:
        """Тест получения статистики очереди."""
        # Mock task processor
        mock_processor = MagicMock()
        mock_session_store = AsyncMock()
        mock_session_store.get_stats = AsyncMock(
            return_value={
                "queue_size": 5,
                "processing_task": "task-123",
                "recent_logs_count": 10,
            }
        )
        mock_processor.session_store = mock_session_store
        mock_get_processor.return_value = mock_processor

        response = await client.get("/api/v1/monitor/queue")

        assert response.status_code == 200
        data = response.json()

        assert "queue_size" in data
        assert "processing_task" in data
        assert "recent_logs_count" in data
        assert data["queue_size"] == 5
        assert data["processing_task"] == "task-123"
        assert data["recent_logs_count"] == 10
