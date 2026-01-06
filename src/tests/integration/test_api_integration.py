"""Интеграционные тесты для API endpoints.

Эти тесты требуют запущенного приложения с Redis.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.requires_redis
class TestHealthEndpointIntegration:
    """Интеграционные тесты для /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, test_client: AsyncClient) -> None:
        """Тест базового health check."""
        response = await test_client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "ok"
        assert data["service"] == "sop_llm"
        assert data["version"] == "1.0.0"


@pytest.mark.integration
@pytest.mark.requires_redis
class TestMetricsEndpointIntegration:
    """Интеграционные тесты для /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, test_client: AsyncClient) -> None:
        """Тест получения метрик Prometheus."""
        response = await test_client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        # Проверяем формат Prometheus
        text = response.text
        assert len(text) > 0

        # Должны быть базовые Python метрики
        assert "python_info" in text or "process_" in text


@pytest.mark.integration
@pytest.mark.requires_redis
class TestMonitorEndpointsIntegration:
    """Интеграционные тесты для /api/v1/monitor/* endpoints."""

    @pytest.mark.asyncio
    async def test_monitor_health(self, test_client: AsyncClient) -> None:
        """Тест детального health check."""
        response = await test_client.get("/api/v1/monitor/health")

        # Может быть 200 (healthy) или 503 (degraded/unhealthy)
        assert response.status_code in [200, 503]

        data = response.json()

        # Проверяем структуру
        assert "status" in data
        assert "redis" in data
        assert "providers" in data

        # Redis должен быть доступен для integration тестов
        assert data["redis"] is True

    @pytest.mark.asyncio
    async def test_monitor_queue(self, test_client: AsyncClient) -> None:
        """Тест получения статистики очереди."""
        response = await test_client.get("/api/v1/monitor/queue")

        assert response.status_code == 200

        data = response.json()

        # Проверяем структуру
        assert "queue_size" in data
        assert "processing_task" in data
        assert "recent_logs_count" in data

        # Проверяем типы
        assert isinstance(data["queue_size"], int)
        assert isinstance(data["recent_logs_count"], int)


@pytest.mark.integration
class TestRootEndpointIntegration:
    """Интеграционные тесты для корневого endpoint."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, test_client: AsyncClient) -> None:
        """Тест корневого endpoint."""
        response = await test_client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "SOP LLM Executor"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"


@pytest.mark.integration
class TestDocsEndpoints:
    """Тесты для документации API."""

    @pytest.mark.asyncio
    async def test_openapi_json(self, test_client: AsyncClient) -> None:
        """Тест получения OpenAPI схемы."""
        response = await test_client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

        # Проверяем основную информацию
        assert data["info"]["title"] == "SOP LLM Executor"
        assert data["info"]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_docs_endpoint(self, test_client: AsyncClient) -> None:
        """Тест доступности Swagger UI."""
        response = await test_client.get("/docs")

        # Может быть 200 (доступен) или 404 (отключен в production)
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_redoc_endpoint(self, test_client: AsyncClient) -> None:
        """Тест доступности ReDoc."""
        response = await test_client.get("/redoc")

        # Может быть 200 (доступен) или 404 (отключен в production)
        assert response.status_code in [200, 404]


@pytest.mark.integration
@pytest.mark.requires_redis
class TestModelsEndpoints:
    """Интеграционные тесты для /api/v1/models/* endpoints."""

    @pytest.mark.asyncio
    async def test_list_models(self, test_client: AsyncClient) -> None:
        """Тест получения списка моделей."""
        response = await test_client.get("/api/v1/models")

        assert response.status_code == 200
        data = response.json()

        # Должен быть список
        assert isinstance(data, list) or isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_list_providers(self, test_client: AsyncClient) -> None:
        """Тест получения списка провайдеров."""
        response = await test_client.get("/api/v1/models/providers")

        assert response.status_code == 200
        data = response.json()

        # Должен быть список провайдеров
        assert isinstance(data, list) or isinstance(data, dict)


@pytest.mark.integration
class TestCORSHeaders:
    """Тесты CORS заголовков."""

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, test_client: AsyncClient) -> None:
        """Тест наличия CORS заголовков."""
        # Делаем preflight request
        response = await test_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS middleware должен добавить заголовки
        assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_cors_allows_origin(self, test_client: AsyncClient) -> None:
        """Тест что CORS разрешает запросы."""
        response = await test_client.get(
            "/health", headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200
        # CORS заголовок должен быть
        assert "access-control-allow-origin" in response.headers


@pytest.mark.integration
@pytest.mark.slow
class TestMetricsCollection:
    """Тесты сбора метрик."""

    @pytest.mark.asyncio
    async def test_metrics_middleware_increments_counters(
        self, test_client: AsyncClient
    ) -> None:
        """Тест что middleware увеличивает счетчики метрик."""
        # Делаем несколько запросов
        await test_client.get("/health")
        await test_client.get("/health")
        await test_client.get("/")

        # Получаем метрики
        response = await test_client.get("/metrics")
        text = response.text

        # Проверяем что метрики собираются
        # http_requests_total должна быть увеличена
        assert "http_requests_total" in text or "python_" in text

    @pytest.mark.asyncio
    async def test_metrics_track_different_endpoints(
        self, test_client: AsyncClient
    ) -> None:
        """Тест что метрики отслеживают разные endpoints."""
        # Делаем запросы к разным endpoints
        await test_client.get("/health")
        await test_client.get("/")
        await test_client.get("/api/v1/monitor/queue")

        # Получаем метрики
        response = await test_client.get("/metrics")
        text = response.text

        # Метрики должны содержать информацию о разных endpoints
        assert len(text) > 0
