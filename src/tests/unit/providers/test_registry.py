"""Tests for ProviderRegistry with lazy loading."""

from unittest.mock import patch

import pytest

from src.providers.registry import ProviderRegistry
from src.tests.conftest import MockLLMProvider, MockPresetsLoader


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def test_init(self) -> None:
        """Test registry initialization."""
        registry = ProviderRegistry()
        assert registry._providers == {}
        assert registry._presets_loader is None

    def test_set_presets_loader(
        self,
        provider_registry: ProviderRegistry,
        mock_presets_loader: MockPresetsLoader,
    ) -> None:
        """Test setting presets loader."""
        assert provider_registry._presets_loader is mock_presets_loader

    def test_register_provider(self, provider_registry: ProviderRegistry) -> None:
        """Test manual provider registration."""
        provider = MockLLMProvider(model_name="test-model")
        provider_registry.register("test-model", provider)

        assert "test-model" in provider_registry
        assert provider_registry.get("test-model") is provider

    def test_unregister_provider(self, provider_registry: ProviderRegistry) -> None:
        """Test provider unregistration."""
        provider = MockLLMProvider(model_name="test-model")
        provider_registry.register("test-model", provider)

        assert "test-model" in provider_registry
        provider_registry.unregister("test-model")
        assert "test-model" not in provider_registry

    def test_get_nonexistent_provider(self, provider_registry: ProviderRegistry) -> None:
        """Test getting non-existent provider raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            provider_registry.get("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_list_providers(self, provider_registry: ProviderRegistry) -> None:
        """Test listing registered providers."""
        provider1 = MockLLMProvider(model_name="model-1")
        provider2 = MockLLMProvider(model_name="model-2")

        provider_registry.register("model-1", provider1)
        provider_registry.register("model-2", provider2)

        providers = provider_registry.list_providers()
        assert "model-1" in providers
        assert "model-2" in providers


class TestProviderRegistryLazyLoading:
    """Tests for lazy loading functionality."""

    def test_get_or_create_returns_existing(
        self,
        provider_registry: ProviderRegistry,
    ) -> None:
        """Test get_or_create returns existing provider."""
        provider = MockLLMProvider(model_name="existing")
        provider_registry.register("existing", provider)

        result = provider_registry.get_or_create("existing")
        assert result is provider

    def test_get_or_create_creates_from_preset(
        self,
        provider_registry: ProviderRegistry,
        mock_env_vars: None,
    ) -> None:
        """Test get_or_create creates provider from preset."""
        # Mock LiteLLMProvider creation (imported inside _create_cloud_provider)
        with patch("src.providers.litellm_provider.LiteLLMProvider") as mock_litellm:
            mock_provider = MockLLMProvider(model_name="claude-sonnet-4-20250514")
            mock_litellm.return_value = mock_provider

            result = provider_registry.get_or_create("claude-sonnet-4")

            assert result is mock_provider
            assert "claude-sonnet-4" in provider_registry
            mock_litellm.assert_called_once()

    def test_get_or_create_caches_provider(
        self,
        provider_registry: ProviderRegistry,
        mock_env_vars: None,
    ) -> None:
        """Test get_or_create caches created provider."""
        with patch("src.providers.litellm_provider.LiteLLMProvider") as mock_litellm:
            mock_provider = MockLLMProvider(model_name="gpt-4-turbo")
            mock_litellm.return_value = mock_provider

            # First call creates provider
            result1 = provider_registry.get_or_create("gpt-4-turbo")
            # Second call returns cached
            result2 = provider_registry.get_or_create("gpt-4-turbo")

            assert result1 is result2
            assert mock_litellm.call_count == 1  # Only created once

    def test_get_or_create_raises_for_unknown_preset(
        self,
        provider_registry: ProviderRegistry,
    ) -> None:
        """Test get_or_create raises KeyError for unknown preset."""
        with pytest.raises(KeyError) as exc_info:
            provider_registry.get_or_create("unknown-model")

        assert "unknown-model" in str(exc_info.value)
        assert "не найдена в пресетах" in str(exc_info.value)

    def test_get_or_create_without_presets_loader(self) -> None:
        """Test get_or_create raises RuntimeError without presets_loader."""
        registry = ProviderRegistry()  # No presets_loader set

        with pytest.raises(RuntimeError) as exc_info:
            registry.get_or_create("any-model")

        assert "presets_loader не установлен" in str(exc_info.value)


class TestProviderRegistryCleanup:
    """Tests for provider cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_all(self, provider_registry: ProviderRegistry) -> None:
        """Test cleanup_all cleans up all providers."""
        provider1 = MockLLMProvider(model_name="model-1")
        provider2 = MockLLMProvider(model_name="model-2")

        provider_registry.register("model-1", provider1)
        provider_registry.register("model-2", provider2)

        await provider_registry.cleanup_all()

        assert provider1._cleaned_up
        assert provider2._cleaned_up

    @pytest.mark.asyncio
    async def test_get_all_models_info(
        self,
        provider_registry: ProviderRegistry,
    ) -> None:
        """Test get_all_models_info returns info for all providers."""
        provider1 = MockLLMProvider(model_name="model-1")
        provider2 = MockLLMProvider(model_name="model-2")

        provider_registry.register("model-1", provider1)
        provider_registry.register("model-2", provider2)

        info = await provider_registry.get_all_models_info()

        assert "model-1" in info
        assert "model-2" in info
        assert info["model-1"].name == "model-1"
        assert info["model-2"].name == "model-2"
