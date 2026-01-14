"""Tests for Embeddings API endpoints."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import embeddings
from src.services.embedding_manager import EmbeddingManager, set_embedding_manager
from src.tests.conftest import MockEmbeddingProvider


@pytest.fixture
def embeddings_app(
    embedding_manager: EmbeddingManager,
) -> FastAPI:
    """Create FastAPI app with embeddings router."""
    app = FastAPI()
    app.include_router(embeddings.router, prefix="/api/v1")

    # Set global embedding manager
    set_embedding_manager(embedding_manager)

    return app


@pytest.fixture
def client(embeddings_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(embeddings_app)


class TestGenerateEmbeddings:
    """Tests for POST /embeddings endpoint."""

    def test_generate_embeddings_success(
        self,
        client: TestClient,
    ) -> None:
        """Test successful embedding generation."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider = MockEmbeddingProvider()
            mock_provider_class.return_value = mock_provider

            response = client.post(
                "/api/v1/embeddings/",
                json={
                    "texts": ["Hello world", "Test text"],
                    "model_name": "multilingual-e5-large",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["embeddings"]) == 2
            assert data["model"] == "multilingual-e5-large"
            assert data["dimensions"] == 768

    def test_generate_embeddings_model_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test embedding generation with unknown model."""
        response = client.post(
            "/api/v1/embeddings/",
            json={
                "texts": ["Hello world"],
                "model_name": "unknown-model",
            },
        )

        assert response.status_code == 404
        data = response.json()
        assert "unknown-model" in data["detail"]

    def test_generate_embeddings_empty_texts(
        self,
        client: TestClient,
    ) -> None:
        """Test embedding generation with empty texts list."""
        response = client.post(
            "/api/v1/embeddings/",
            json={
                "texts": [],
                "model_name": "multilingual-e5-large",
            },
        )

        # Should fail validation
        assert response.status_code == 422


class TestCalculateSimilarity:
    """Tests for POST /embeddings/similarity endpoint."""

    def test_calculate_similarity_success(
        self,
        client: TestClient,
    ) -> None:
        """Test successful similarity calculation."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider = MockEmbeddingProvider()
            mock_provider_class.return_value = mock_provider

            response = client.post(
                "/api/v1/embeddings/similarity",
                json={
                    "text1": "Machine learning is great",
                    "text2": "AI is awesome",
                    "model_name": "multilingual-e5-large",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "similarity" in data
            assert 0 <= data["similarity"] <= 1
            assert data["model"] == "multilingual-e5-large"
            assert "text1_preview" in data
            assert "text2_preview" in data

    def test_calculate_similarity_model_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test similarity calculation with unknown model."""
        response = client.post(
            "/api/v1/embeddings/similarity",
            json={
                "text1": "Hello",
                "text2": "World",
                "model_name": "unknown-model",
            },
        )

        assert response.status_code == 404

    def test_calculate_similarity_truncates_preview(
        self,
        client: TestClient,
    ) -> None:
        """Test that long texts are truncated in preview."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider = MockEmbeddingProvider()
            mock_provider_class.return_value = mock_provider

            long_text = "A" * 200  # More than 100 chars

            response = client.post(
                "/api/v1/embeddings/similarity",
                json={
                    "text1": long_text,
                    "text2": "Short text",
                    "model_name": "multilingual-e5-large",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["text1_preview"]) <= 104  # 100 + "..."
            assert data["text1_preview"].endswith("...")
