"""Tests for EmbeddingManager with FIFO eviction."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.embedding_manager import (
    EmbeddingManager,
    get_embedding_manager,
    set_embedding_manager,
)
from src.tests.conftest import MockEmbeddingProvider, MockPresetsLoader


class TestEmbeddingManagerInit:
    """Tests for EmbeddingManager initialization."""

    def test_init(self, mock_presets_loader: MockPresetsLoader) -> None:
        """Test manager initialization."""
        manager = EmbeddingManager(
            presets_loader=mock_presets_loader,  # type: ignore[arg-type]
            device="cpu",
            max_loaded_models=5,
        )

        assert manager._device == "cpu"
        assert manager._max_loaded_models == 5
        assert len(manager._loaded_models) == 0
        assert manager._vram_monitor is None

    def test_set_vram_monitor(
        self,
        embedding_manager: EmbeddingManager,
        mock_vram_monitor: MagicMock,
    ) -> None:
        """Test setting VRAM monitor."""
        embedding_manager.set_vram_monitor(mock_vram_monitor)
        assert embedding_manager._vram_monitor is mock_vram_monitor


class TestEmbeddingManagerLazyLoading:
    """Tests for lazy loading functionality."""

    @pytest.mark.asyncio
    async def test_get_or_load_creates_provider(
        self,
        embedding_manager: EmbeddingManager,
    ) -> None:
        """Test get_or_load creates provider from preset."""
        # Mock SentenceTransformerProvider
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider = MockEmbeddingProvider()
            mock_provider_class.return_value = mock_provider

            result = await embedding_manager.get_or_load("multilingual-e5-large")

            assert result is mock_provider
            assert mock_provider._loaded
            assert "multilingual-e5-large" in embedding_manager.list_loaded()

    @pytest.mark.asyncio
    async def test_get_or_load_returns_cached(
        self,
        embedding_manager: EmbeddingManager,
    ) -> None:
        """Test get_or_load returns cached provider."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider = MockEmbeddingProvider()
            mock_provider_class.return_value = mock_provider

            # First call
            result1 = await embedding_manager.get_or_load("multilingual-e5-large")
            # Second call should return cached
            result2 = await embedding_manager.get_or_load("multilingual-e5-large")

            assert result1 is result2
            assert mock_provider_class.call_count == 1  # Only created once

    @pytest.mark.asyncio
    async def test_get_or_load_unknown_preset(
        self,
        embedding_manager: EmbeddingManager,
    ) -> None:
        """Test get_or_load raises KeyError for unknown preset."""
        with pytest.raises(KeyError) as exc_info:
            await embedding_manager.get_or_load("unknown-model")

        assert "unknown-model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_or_load_moves_to_end(
        self,
        embedding_manager: EmbeddingManager,
    ) -> None:
        """Test get_or_load moves accessed model to end of FIFO queue."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider_class.return_value = MockEmbeddingProvider()

            # Load two models
            await embedding_manager.get_or_load("multilingual-e5-large")
            await embedding_manager.get_or_load("all-MiniLM-L6-v2")

            # Access first model again
            await embedding_manager.get_or_load("multilingual-e5-large")

            # multilingual-e5-large should now be at end
            loaded = embedding_manager.list_loaded()
            assert loaded[-1] == "multilingual-e5-large"


class TestEmbeddingManagerFIFOEviction:
    """Tests for FIFO eviction functionality."""

    @pytest.mark.asyncio
    async def test_fifo_eviction_on_max_models(
        self,
        mock_presets_loader: MockPresetsLoader,
    ) -> None:
        """Test FIFO eviction when max_loaded_models is reached."""
        # Add more presets for testing
        mock_presets_loader.add_embedding_preset("model-3", "mock/model-3", 512)
        mock_presets_loader.add_embedding_preset("model-4", "mock/model-4", 512)

        manager = EmbeddingManager(
            presets_loader=mock_presets_loader,  # type: ignore[arg-type]
            device="cpu",
            max_loaded_models=2,  # Small limit for testing
        )

        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            providers = []

            def create_mock_provider(*args, **kwargs):
                provider = MockEmbeddingProvider()
                providers.append(provider)
                return provider

            mock_provider_class.side_effect = create_mock_provider

            # Load 2 models (at limit)
            await manager.get_or_load("multilingual-e5-large")
            await manager.get_or_load("all-MiniLM-L6-v2")

            assert len(manager.list_loaded()) == 2

            # Load 3rd model - should evict first
            await manager.get_or_load("model-3")

            loaded = manager.list_loaded()
            assert len(loaded) == 2
            assert "multilingual-e5-large" not in loaded  # First was evicted
            assert "all-MiniLM-L6-v2" in loaded
            assert "model-3" in loaded
            assert providers[0]._cleaned_up  # First provider was cleaned up

    @pytest.mark.asyncio
    async def test_fifo_eviction_with_vram_monitor(
        self,
        embedding_manager_with_vram: EmbeddingManager,
    ) -> None:
        """Test FIFO eviction with VRAM monitoring."""
        # Set up VRAM monitor to deny allocation initially
        vram_monitor = embedding_manager_with_vram._vram_monitor
        vram_monitor.can_allocate.side_effect = [False, True]  # Deny first, then allow

        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            # Pre-load a model manually for eviction
            old_provider = MockEmbeddingProvider()
            old_provider._loaded = True
            embedding_manager_with_vram._loaded_models["old-model"] = old_provider  # type: ignore[assignment]

            mock_provider_class.return_value = MockEmbeddingProvider()

            # This should trigger eviction
            await embedding_manager_with_vram.get_or_load("multilingual-e5-large")

            # Old model should be evicted
            assert "old-model" not in embedding_manager_with_vram.list_loaded()
            assert old_provider._cleaned_up


class TestEmbeddingManagerCleanup:
    """Tests for cleanup functionality."""

    @pytest.mark.asyncio
    async def test_unload(self, embedding_manager: EmbeddingManager) -> None:
        """Test unloading specific model."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider = MockEmbeddingProvider()
            mock_provider_class.return_value = mock_provider

            await embedding_manager.get_or_load("multilingual-e5-large")
            assert "multilingual-e5-large" in embedding_manager.list_loaded()

            result = await embedding_manager.unload("multilingual-e5-large")

            assert result is True
            assert "multilingual-e5-large" not in embedding_manager.list_loaded()
            assert mock_provider._cleaned_up

    @pytest.mark.asyncio
    async def test_unload_nonexistent(self, embedding_manager: EmbeddingManager) -> None:
        """Test unloading non-existent model returns False."""
        result = await embedding_manager.unload("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup(self, embedding_manager: EmbeddingManager) -> None:
        """Test cleanup unloads all models."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            providers = []

            def create_mock_provider(*args, **kwargs):
                provider = MockEmbeddingProvider()
                providers.append(provider)
                return provider

            mock_provider_class.side_effect = create_mock_provider

            await embedding_manager.get_or_load("multilingual-e5-large")
            await embedding_manager.get_or_load("all-MiniLM-L6-v2")

            await embedding_manager.cleanup()

            assert len(embedding_manager.list_loaded()) == 0
            for provider in providers:
                assert provider._cleaned_up


class TestEmbeddingManagerInfo:
    """Tests for info methods."""

    @pytest.mark.asyncio
    async def test_get_info(self, embedding_manager: EmbeddingManager) -> None:
        """Test get_info returns correct information."""
        with patch(
            "src.services.embedding_manager.SentenceTransformerProvider"
        ) as mock_provider_class:
            mock_provider_class.return_value = MockEmbeddingProvider()

            await embedding_manager.get_or_load("multilingual-e5-large")

            info = embedding_manager.get_info()

            assert info["device"] == "cpu"
            assert info["max_loaded_models"] == 3
            assert info["loaded_count"] == 1
            assert "multilingual-e5-large" in info["loaded_models"]
            assert "multilingual-e5-large" in info["models_info"]


class TestEmbeddingManagerSingleton:
    """Tests for singleton pattern."""

    def test_get_embedding_manager_raises_without_init(self) -> None:
        """Test get_embedding_manager raises without initialization."""
        # Reset global
        import src.services.embedding_manager as em_module

        em_module._embedding_manager = None

        with pytest.raises(RuntimeError) as exc_info:
            get_embedding_manager()

        assert "не инициализирован" in str(exc_info.value)

    def test_set_and_get_embedding_manager(
        self,
        mock_presets_loader: MockPresetsLoader,
    ) -> None:
        """Test set and get embedding manager."""
        manager = EmbeddingManager(
            presets_loader=mock_presets_loader,  # type: ignore[arg-type]
            device="cpu",
            max_loaded_models=5,
        )

        set_embedding_manager(manager)

        result = get_embedding_manager()
        assert result is manager
