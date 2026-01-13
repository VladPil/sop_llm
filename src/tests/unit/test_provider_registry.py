"""Unit тесты для providers/registry.py."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.providers.base import ModelInfo
from src.providers.registry import ProviderRegistry


class MockProvider:
    """Mock provider для тестирования."""

    def __init__(self, name: str, should_fail_health: bool = False) -> None:
        self.name = name
        self.should_fail_health = should_fail_health
        self.cleanup_called = False

    async def generate(self, prompt: str, params: Any) -> Any:
        """Mock generate."""
        return MagicMock()

    async def generate_stream(self, prompt: str, params: Any) -> Any:
        """Mock generate_stream."""
        yield MagicMock()

    async def get_model_info(self) -> ModelInfo:
        """Mock get_model_info."""
        return ModelInfo(
            name=self.name,
            provider="local",
            context_window=4096,
            max_output_tokens=2048,
            supports_streaming=True,
            supports_structured_output=False,
            loaded=True,
        )

    async def health_check(self) -> bool:
        """Mock health_check."""
        if self.should_fail_health:
            raise RuntimeError("Health check failed")
        return True

    async def cleanup(self) -> None:
        """Mock cleanup."""
        self.cleanup_called = True


class TestProviderRegistry:
    """Тесты для ProviderRegistry."""

    def test_register_provider(self) -> None:
        """Тест регистрации provider."""
        registry = ProviderRegistry()
        provider = MockProvider("test-model")

        registry.register("test-model", provider)  # type: ignore[arg-type]

        assert "test-model" in registry
        assert len(registry) == 1
        assert registry.list_providers() == ["test-model"]

    def test_register_duplicate_raises_error(self) -> None:
        """Тест что дублирование имени вызывает ошибку."""
        registry = ProviderRegistry()
        provider1 = MockProvider("test-model")
        provider2 = MockProvider("test-model")

        registry.register("test-model", provider1)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="уже зарегистрирован"):
            registry.register("test-model", provider2)  # type: ignore[arg-type]

    def test_get_provider(self) -> None:
        """Тест получения provider по имени."""
        registry = ProviderRegistry()
        provider = MockProvider("test-model")

        registry.register("test-model", provider)  # type: ignore[arg-type]
        retrieved = registry.get("test-model")

        assert retrieved == provider

    def test_get_nonexistent_provider_raises_error(self) -> None:
        """Тест что получение несуществующего provider вызывает ошибку."""
        registry = ProviderRegistry()

        with pytest.raises(KeyError, match="не найден"):
            registry.get("nonexistent")

    def test_unregister_provider(self) -> None:
        """Тест удаления provider."""
        registry = ProviderRegistry()
        provider = MockProvider("test-model")

        registry.register("test-model", provider)  # type: ignore[arg-type]
        assert len(registry) == 1

        registry.unregister("test-model")
        assert len(registry) == 0
        assert "test-model" not in registry

    def test_unregister_nonexistent_raises_error(self) -> None:
        """Тест что удаление несуществующего provider вызывает ошибку."""
        registry = ProviderRegistry()

        with pytest.raises(KeyError, match="не найден"):
            registry.unregister("nonexistent")

    def test_list_providers(self) -> None:
        """Тест получения списка providers."""
        registry = ProviderRegistry()
        provider1 = MockProvider("model-1")
        provider2 = MockProvider("model-2")

        registry.register("model-1", provider1)  # type: ignore[arg-type]
        registry.register("model-2", provider2)  # type: ignore[arg-type]

        providers = registry.list_providers()

        assert len(providers) == 2
        assert "model-1" in providers
        assert "model-2" in providers

    @pytest.mark.asyncio
    async def test_get_all_models_info(self) -> None:
        """Тест получения метаданных всех моделей."""
        registry = ProviderRegistry()
        provider1 = MockProvider("model-1")
        provider2 = MockProvider("model-2")

        registry.register("model-1", provider1)  # type: ignore[arg-type]
        registry.register("model-2", provider2)  # type: ignore[arg-type]

        models_info = await registry.get_all_models_info()

        assert len(models_info) == 2
        assert "model-1" in models_info
        assert "model-2" in models_info
        assert models_info["model-1"].name == "model-1"
        assert models_info["model-2"].name == "model-2"

    @pytest.mark.asyncio
    async def test_get_all_models_info_with_error(self) -> None:
        """Тест что ошибка в get_model_info не ломает весь запрос."""
        registry = ProviderRegistry()

        # Создаем provider который кидает ошибку в get_model_info
        bad_provider = MockProvider("bad-model")
        bad_provider.get_model_info = AsyncMock(side_effect=RuntimeError("Test error"))  # type: ignore[method-assign]

        good_provider = MockProvider("good-model")

        registry.register("bad-model", bad_provider)  # type: ignore[arg-type]
        registry.register("good-model", good_provider)  # type: ignore[arg-type]

        models_info = await registry.get_all_models_info()

        # Должна быть только info для good-model
        assert len(models_info) == 1
        assert "good-model" in models_info
        assert "bad-model" not in models_info

    @pytest.mark.asyncio
    async def test_health_check_all(self) -> None:
        """Тест health check всех providers."""
        registry = ProviderRegistry()
        healthy_provider = MockProvider("healthy", should_fail_health=False)
        unhealthy_provider = MockProvider("unhealthy", should_fail_health=True)

        registry.register("healthy", healthy_provider)  # type: ignore[arg-type]
        registry.register("unhealthy", unhealthy_provider)  # type: ignore[arg-type]

        health_status = await registry.health_check_all()

        assert health_status["healthy"] is True
        assert health_status["unhealthy"] is False

    @pytest.mark.asyncio
    async def test_cleanup_all(self) -> None:
        """Тест cleanup всех providers."""
        registry = ProviderRegistry()
        provider1 = MockProvider("model-1")
        provider2 = MockProvider("model-2")

        registry.register("model-1", provider1)  # type: ignore[arg-type]
        registry.register("model-2", provider2)  # type: ignore[arg-type]

        await registry.cleanup_all()

        assert provider1.cleanup_called is True
        assert provider2.cleanup_called is True

    def test_len_and_contains(self) -> None:
        """Тест __len__ и __contains__."""
        registry = ProviderRegistry()
        provider = MockProvider("test-model")

        assert len(registry) == 0
        assert "test-model" not in registry

        registry.register("test-model", provider)  # type: ignore[arg-type]

        assert len(registry) == 1
        assert "test-model" in registry
