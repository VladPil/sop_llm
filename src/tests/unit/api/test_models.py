"""Tests for Models API endpoints."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import models
from src.providers.registry import ProviderRegistry, set_provider_registry
from src.tests.conftest import MockLLMProvider, MockPresetsLoader


@pytest.fixture
def models_app(
    mock_presets_loader: MockPresetsLoader,
) -> FastAPI:
    """Create FastAPI app with models router."""
    app = FastAPI()
    app.include_router(models.router, prefix="/api/v1")

    # Create fresh registry with presets loader
    registry = ProviderRegistry()
    registry.set_presets_loader(mock_presets_loader)  # type: ignore[arg-type]
    set_provider_registry(registry)

    # Set presets loader globally
    from src.services.model_presets import set_presets_loader
    set_presets_loader(mock_presets_loader)  # type: ignore[arg-type]

    return app


@pytest.fixture
def client(models_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(models_app)


@pytest.fixture
def app_with_provider(
    mock_presets_loader: MockPresetsLoader,
) -> tuple[FastAPI, ProviderRegistry]:
    """Create FastAPI app with registry that has a provider."""
    app = FastAPI()
    app.include_router(models.router, prefix="/api/v1")

    registry = ProviderRegistry()
    registry.set_presets_loader(mock_presets_loader)  # type: ignore[arg-type]
    set_provider_registry(registry)

    from src.services.model_presets import set_presets_loader
    set_presets_loader(mock_presets_loader)  # type: ignore[arg-type]

    return app, registry


class TestListModels:
    """Tests for GET /models endpoint."""

    def test_list_models_empty(self, client: TestClient) -> None:
        """Test listing models when registry is empty."""
        response = client.get("/api/v1/models/")

        assert response.status_code == 200
        data = response.json()
        assert data["models"] == []
        assert data["total"] == 0

    def test_list_models_with_registered(
        self,
        app_with_provider: tuple[FastAPI, ProviderRegistry],
    ) -> None:
        """Test listing models with registered providers."""
        app, registry = app_with_provider
        client = TestClient(app)

        provider = MockLLMProvider(model_name="test-model")
        registry.register("test-model", provider)

        response = client.get("/api/v1/models/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["models"]) == 1
        assert data["models"][0]["name"] == "test-model"


class TestListPresets:
    """Tests for GET /models/presets endpoint."""

    def test_list_presets(self, client: TestClient) -> None:
        """Test listing available presets."""
        response = client.get("/api/v1/models/presets")

        assert response.status_code == 200
        data = response.json()

        # Check cloud presets
        assert data["total_cloud"] == 3
        cloud_names = [p["name"] for p in data["cloud_models"]]
        assert "claude-sonnet-4" in cloud_names
        assert "gpt-4-turbo" in cloud_names
        assert "qwen2.5:7b" in cloud_names

        # Check embedding presets
        assert data["total_embedding"] == 2
        embedding_names = [p["name"] for p in data["embedding_models"]]
        assert "multilingual-e5-large" in embedding_names
        assert "all-MiniLM-L6-v2" in embedding_names


class TestGetModelInfo:
    """Tests for GET /models/{model_name} endpoint."""

    def test_get_model_info_lazy_loading(
        self,
        client: TestClient,
        mock_env_vars: None,
    ) -> None:
        """Test getting model info triggers lazy loading."""
        with patch("src.providers.litellm_provider.LiteLLMProvider") as mock_litellm:
            mock_provider = MockLLMProvider(model_name="claude-sonnet-4-20250514")
            mock_litellm.return_value = mock_provider

            response = client.get("/api/v1/models/claude-sonnet-4")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "claude-sonnet-4-20250514"
            mock_litellm.assert_called_once()

    def test_get_model_info_not_found(self, client: TestClient) -> None:
        """Test getting info for non-existent model."""
        response = client.get("/api/v1/models/unknown-model")

        assert response.status_code == 404
        data = response.json()
        assert "unknown-model" in data["detail"]


class TestUnregisterModel:
    """Tests for DELETE /models/{model_name} endpoint."""

    def test_unregister_model(
        self,
        app_with_provider: tuple[FastAPI, ProviderRegistry],
    ) -> None:
        """Test unregistering a model."""
        app, registry = app_with_provider
        client = TestClient(app)

        provider = MockLLMProvider(model_name="test-model")
        registry.register("test-model", provider)

        response = client.delete("/api/v1/models/test-model")

        assert response.status_code == 204
        assert "test-model" not in registry

    def test_unregister_model_not_found(self, client: TestClient) -> None:
        """Test unregistering non-existent model."""
        response = client.delete("/api/v1/models/unknown-model")

        assert response.status_code == 404
