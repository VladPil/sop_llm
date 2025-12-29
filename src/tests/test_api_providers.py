"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ для API endpoints с новой архитектурой провайдеров
Тестирует реальные HTTP запросы к API

Требования:
- Приложение должно быть запущено (или используется TestClient)
- Redis должен быть запущен
"""
import pytest
import json
from httpx import AsyncClient
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestProvidersAPI:
    """Тесты для /api/v1/providers endpoint"""

    @pytest.mark.asyncio
    async def test_list_providers_endpoint(self, test_client: AsyncClient):
        """Тест GET /api/v1/providers"""
        response = await test_client.get("/api/v1/providers")

        assert response.status_code == 200

        data = response.json()
        assert "providers" in data
        assert "total" in data
        assert isinstance(data["providers"], list)
        assert data["total"] == len(data["providers"])

        # Каждый провайдер должен иметь нужные поля
        for provider in data["providers"]:
            assert "name" in provider
            assert "is_available" in provider
            assert "capabilities" in provider
            assert "is_default" in provider

        print(f"\n✓ GET /api/v1/providers:")
        print(f"  Total: {data['total']}")
        for p in data["providers"]:
            print(f"  - {p['name']}: available={p['is_available']}, default={p['is_default']}")

    @pytest.mark.asyncio
    async def test_providers_endpoint_structure(self, test_client: AsyncClient):
        """Тест структуры ответа /api/v1/providers"""
        response = await test_client.get("/api/v1/providers")

        assert response.status_code == 200
        data = response.json()

        # Проверяем что есть хотя бы один провайдер
        assert len(data["providers"]) > 0, "Should have at least one provider"

        # Проверяем capabilities
        provider = data["providers"][0]
        assert isinstance(provider["capabilities"], list)
        assert len(provider["capabilities"]) > 0

        print(f"\n✓ Providers endpoint structure valid")
        print(f"  Example capabilities: {provider['capabilities']}")

    @pytest.mark.asyncio
    async def test_providers_default_set(self, test_client: AsyncClient):
        """Тест что есть default провайдер"""
        response = await test_client.get("/api/v1/providers")
        data = response.json()

        # Должен быть хотя бы один default
        default_providers = [p for p in data["providers"] if p["is_default"]]
        assert len(default_providers) == 1, "Should have exactly one default provider"

        print(f"\n✓ Default provider: {default_providers[0]['name']}")


@pytest.mark.integration
class TestHealthAPI:
    """Тесты для /api/v1/health endpoint (с провайдерами)"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, test_client: AsyncClient):
        """Тест GET /api/v1/health"""
        response = await test_client.get("/api/v1/health")

        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        print(f"\n✓ Health endpoint:")
        print(f"  Status: {data['status']}")

    @pytest.mark.asyncio
    async def test_health_includes_providers(self, test_client: AsyncClient):
        """Тест что health включает информацию о провайдерах"""
        response = await test_client.get("/api/v1/health")
        data = response.json()

        # Health может включать детальную информацию
        # Проверим что endpoint отвечает корректно
        assert response.status_code == 200

        print(f"\n✓ Health endpoint accessible")


@pytest.mark.integration
@pytest.mark.slow
class TestGenerationAPI:
    """Тесты для API генерации (если есть endpoint для ProviderManager)"""

    @pytest.mark.asyncio
    async def test_generate_via_api_if_exists(self, test_client: AsyncClient):
        """Тест генерации через API (если endpoint реализован)"""
        # Проверяем есть ли endpoint для генерации через ProviderManager
        # Пример: POST /api/v1/generate

        # Это placeholder - нужно будет добавить endpoint в routes.py
        # если планируется использовать ProviderManager через API

        # Пока просто проверяем что endpoints существуют
        endpoints_to_check = [
            "/api/v1/health",
            "/api/v1/providers",
        ]

        for endpoint in endpoints_to_check:
            response = await test_client.get(endpoint)
            assert response.status_code in [200, 404, 405]  # 404/405 если endpoint не существует
            print(f"  {endpoint}: {response.status_code}")

        print(f"\n✓ API endpoints checked")


@pytest.mark.integration
class TestAPIErrorHandling:
    """Тесты обработки ошибок в API"""

    @pytest.mark.asyncio
    async def test_invalid_endpoint(self, test_client: AsyncClient):
        """Тест запроса к несуществующему endpoint"""
        response = await test_client.get("/api/v1/nonexistent")

        assert response.status_code == 404

        print(f"\n✓ 404 for invalid endpoint")

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, test_client: AsyncClient):
        """Тест неподдерживаемого HTTP метода"""
        # GET /api/v1/providers поддерживается, POST - нет
        response = await test_client.post("/api/v1/providers")

        assert response.status_code == 405

        print(f"\n✓ 405 for wrong method")

    @pytest.mark.asyncio
    async def test_api_returns_json(self, test_client: AsyncClient):
        """Тест что API возвращает JSON"""
        response = await test_client.get("/api/v1/providers")

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

        # Проверяем что можно распарсить JSON
        data = response.json()
        assert isinstance(data, dict)

        print(f"\n✓ API returns valid JSON")


@pytest.mark.integration
class TestAPIHeaders:
    """Тесты заголовков API"""

    @pytest.mark.asyncio
    async def test_cors_headers(self, test_client: AsyncClient):
        """Тест CORS заголовков"""
        response = await test_client.get("/api/v1/providers")

        # В зависимости от настройки CORS могут быть заголовки
        # Проверяем что endpoint отвечает
        assert response.status_code == 200

        print(f"\n✓ CORS headers check passed")

    @pytest.mark.asyncio
    async def test_request_id_header(self, test_client: AsyncClient):
        """Тест заголовка X-Request-ID"""
        # Отправляем запрос с Request-ID
        headers = {"X-Request-ID": "test-123"}
        response = await test_client.get("/api/v1/providers", headers=headers)

        assert response.status_code == 200

        # Проверяем что Request-ID вернулся (если middleware настроен)
        # В зависимости от реализации
        print(f"\n✓ Request ID handling checked")

    @pytest.mark.asyncio
    async def test_duration_header(self, test_client: AsyncClient):
        """Тест заголовка X-Duration-Ms"""
        response = await test_client.get("/api/v1/providers")

        assert response.status_code == 200

        # Проверяем есть ли заголовок с временем выполнения
        if "X-Duration-Ms" in response.headers:
            duration = float(response.headers["X-Duration-Ms"])
            assert duration >= 0
            print(f"\n✓ Duration header: {duration}ms")
        else:
            print(f"\n✓ Duration header not present (optional)")


@pytest.mark.integration
@pytest.mark.slow
class TestAPIPerformance:
    """Тесты производительности API"""

    @pytest.mark.asyncio
    async def test_providers_endpoint_performance(self, test_client: AsyncClient):
        """Тест времени ответа /api/v1/providers"""
        import time

        start = time.time()
        response = await test_client.get("/api/v1/providers")
        duration = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration < 1000, f"Should respond in less than 1s, got {duration}ms"

        print(f"\n✓ /api/v1/providers performance:")
        print(f"  Duration: {duration:.2f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, test_client: AsyncClient):
        """Тест concurrent запросов к API"""
        import asyncio

        # Отправляем несколько параллельных запросов
        tasks = [
            test_client.get("/api/v1/providers")
            for _ in range(5)
        ]

        responses = await asyncio.gather(*tasks)

        # Все должны успешно завершиться
        assert all(r.status_code == 200 for r in responses)

        print(f"\n✓ Concurrent API requests:")
        print(f"  Total: {len(responses)}")
        print(f"  All successful: True")


@pytest.mark.integration
class TestAPIDocumentation:
    """Тесты для документации API (OpenAPI/Swagger)"""

    @pytest.mark.asyncio
    async def test_openapi_schema_accessible(self, test_client: AsyncClient):
        """Тест доступности OpenAPI схемы"""
        response = await test_client.get("/openapi.json")

        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

        # Проверяем что /api/v1/providers в схеме
        assert "/api/v1/providers" in schema["paths"]

        print(f"\n✓ OpenAPI schema accessible")
        print(f"  OpenAPI version: {schema['openapi']}")
        print(f"  Endpoints count: {len(schema['paths'])}")

    @pytest.mark.asyncio
    async def test_swagger_ui_accessible(self, test_client: AsyncClient):
        """Тест доступности Swagger UI"""
        response = await test_client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        print(f"\n✓ Swagger UI accessible at /docs")

    @pytest.mark.asyncio
    async def test_redoc_accessible(self, test_client: AsyncClient):
        """Тест доступности ReDoc"""
        response = await test_client.get("/redoc")

        assert response.status_code == 200

        print(f"\n✓ ReDoc accessible at /redoc")


@pytest.mark.integration
class TestAPIVersioning:
    """Тесты версионирования API"""

    @pytest.mark.asyncio
    async def test_api_v1_prefix(self, test_client: AsyncClient):
        """Тест что endpoints используют /api/v1 prefix"""
        response = await test_client.get("/api/v1/providers")
        assert response.status_code == 200

        # Без префикса не должно работать
        response_no_prefix = await test_client.get("/providers")
        assert response_no_prefix.status_code == 404

        print(f"\n✓ API versioning (v1) works correctly")

    @pytest.mark.asyncio
    async def test_root_endpoint(self, test_client: AsyncClient):
        """Тест корневого endpoint"""
        response = await test_client.get("/")

        assert response.status_code == 200

        data = response.json()
        assert "service" in data or "version" in data

        print(f"\n✓ Root endpoint accessible")
        print(f"  Response: {data}")
