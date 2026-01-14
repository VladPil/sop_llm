"""Pytest configuration для интеграционных тестов.

Этот файл содержит общие фикстуры для тестирования SOP LLM сервиса.
"""

import asyncio
from collections.abc import AsyncGenerator, Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from src.app import app
from src.core.config import settings
from src.core.enums import ProviderType
from src.core.model_presets import (
    CloudModelPreset,
    CloudProviderConfig,
    EmbeddingModelPreset,
)
from src.providers.base import ModelInfo
from src.providers.registry import ProviderRegistry
from src.services.embedding_manager import EmbeddingManager


@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для всей сессии тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Redis клиент для интеграционных тестов.

    Требования:
    - Redis должен быть запущен и доступен
    """
    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=False,
    )

    try:
        # Проверяем подключение
        await client.ping()  # type: ignore[misc]
        print(f"\n✓ Redis connected: {settings.redis_host}:{settings.redis_port}")
    except Exception as e:
        pytest.fail(
            f"Redis is not available: {e}\n"
            f"Please ensure Redis is running and accessible at {settings.redis_host}:{settings.redis_port}"
        )

    yield client

    # Cleanup: удаляем тестовые ключи
    async for key in client.scan_iter(match="test:*"):
        await client.delete(key)

    await client.aclose()


@pytest.fixture
async def clean_redis(redis_client: Redis):
    """Очищает Redis перед каждым тестом."""
    # Удаляем все тестовые ключи перед тестом
    async for key in redis_client.scan_iter(match="test:*"):
        await redis_client.delete(key)

    yield

    # Очищаем после теста
    async for key in redis_client.scan_iter(match="test:*"):
        await redis_client.delete(key)


@pytest.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient для тестирования API endpoints.

    Использует ASGI приложение напрямую (без запуска сервера).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        print("\n✓ Test client created")
        yield client


@pytest.fixture
def sample_prompts() -> list[str]:
    """Примеры промптов для тестирования."""
    return [
        "What is the capital of France?",
        "Explain quantum computing in one sentence.",
        "Write a haiku about programming.",
    ]


@pytest.fixture
def sample_task_data() -> dict[str, Any]:
    """Пример данных для создания задачи."""
    return {
        "model": "test-model",
        "prompt": "Test prompt for generation",
        "temperature": 0.7,
        "max_tokens": 100,
    }


# Маркеры для pytest
def pytest_configure(config):
    """Регистрация маркеров."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated, use mocks)")
    config.addinivalue_line("markers", "integration: Integration tests (real components)")
    config.addinivalue_line("markers", "api: API tests (HTTP endpoints)")
    config.addinivalue_line("markers", "slow: Slow running tests (> 1s)")
    config.addinivalue_line("markers", "requires_redis: Tests requiring Redis")
    config.addinivalue_line("markers", "requires_gpu: Tests requiring GPU")
    config.addinivalue_line("markers", "requires_api_key: Tests requiring API keys")
    config.addinivalue_line(
        "markers", "requires_external_service: Tests requiring external services"
    )


# ============================================================================
# Mock Providers for Unit Tests
# ============================================================================


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(
        self,
        model_name: str = "mock-model",
        api_key: str | None = None,
        timeout: int = 60,
        **kwargs: Any,
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout
        self.extra_params = kwargs
        self._cleaned_up = False

    async def generate(
        self,
        prompt: str,
        **params: Any,
    ) -> dict[str, Any]:
        """Mock generate method."""
        return {
            "content": f"Mock response to: {prompt[:50]}",
            "model": self.model_name,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

    async def get_model_info(self) -> ModelInfo:
        """Mock get_model_info method."""
        return ModelInfo(
            name=self.model_name,
            provider=ProviderType.CUSTOM,
            context_window=4096,
            max_output_tokens=1024,
            supports_streaming=True,
            supports_structured_output=True,
            loaded=True,
            extra={},
        )

    async def cleanup(self) -> None:
        """Mock cleanup method."""
        self._cleaned_up = True


class MockEmbeddingProvider:
    """Mock embedding provider for testing."""

    def __init__(
        self,
        model_name: str = "mock-embedding",
        device: str = "cpu",
        **kwargs: Any,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.dimensions = 768
        self.model = None
        self._loaded = False
        self._cleaned_up = False

    async def load(self) -> None:
        """Mock load method."""
        self._loaded = True
        self.model = MagicMock()

    async def cleanup(self) -> None:
        """Mock cleanup method."""
        self._cleaned_up = True
        self.model = None

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Mock generate_embeddings method."""
        if not self._loaded:
            raise ValueError("Model not loaded")
        return [[0.1 * i] * self.dimensions for i in range(len(texts))]

    def get_info(self) -> dict[str, Any]:
        """Mock get_info method."""
        return {
            "model_name": self.model_name,
            "provider_type": "mock",
            "dimensions": self.dimensions,
            "device": self.device,
            "loaded": self._loaded,
        }


class MockPresetsLoader:
    """Mock presets loader for testing."""

    def __init__(self) -> None:
        self._cloud_presets: dict[str, CloudModelPreset] = {}
        self._embedding_presets: dict[str, EmbeddingModelPreset] = {}

    def add_cloud_preset(
        self,
        name: str,
        provider: ProviderType = ProviderType.ANTHROPIC,
        model_name: str = "mock-model",
        api_key_env_var: str = "MOCK_API_KEY",
    ) -> None:
        """Add a cloud preset for testing."""
        self._cloud_presets[name] = CloudModelPreset(
            name=name,
            provider=provider,
            api_key_env_var=api_key_env_var,
            provider_config=CloudProviderConfig(
                model_name=model_name,
                timeout=60,
                max_retries=2,
            ),
        )

    def add_embedding_preset(
        self,
        name: str,
        huggingface_repo: str = "mock/model",
        dimensions: int = 768,
    ) -> None:
        """Add an embedding preset for testing."""
        self._embedding_presets[name] = EmbeddingModelPreset(
            name=name,
            huggingface_repo=huggingface_repo,
            dimensions=dimensions,
        )

    def get_cloud_preset(self, name: str) -> CloudModelPreset | None:
        """Get cloud preset by name."""
        return self._cloud_presets.get(name)

    def get_embedding_preset(self, name: str) -> EmbeddingModelPreset | None:
        """Get embedding preset by name."""
        return self._embedding_presets.get(name)

    def list_cloud(self) -> list[CloudModelPreset]:
        """List all cloud presets."""
        return list(self._cloud_presets.values())

    def list_cloud_names(self) -> list[str]:
        """List cloud preset names."""
        return list(self._cloud_presets.keys())

    def list_embedding(self) -> list[EmbeddingModelPreset]:
        """List all embedding presets."""
        return list(self._embedding_presets.values())

    def list_embedding_names(self) -> list[str]:
        """List embedding preset names."""
        return list(self._embedding_presets.keys())

    def list_local(self) -> list[Any]:
        """List local presets (empty for mock)."""
        return []

    def list_local_names(self) -> list[str]:
        """List local preset names."""
        return []


# ============================================================================
# Unit Test Fixtures
# ============================================================================


@pytest.fixture
def mock_presets_loader() -> MockPresetsLoader:
    """Create mock presets loader with sample presets."""
    loader = MockPresetsLoader()
    loader.add_cloud_preset("claude-sonnet-4", ProviderType.ANTHROPIC, "claude-sonnet-4-20250514")
    loader.add_cloud_preset("gpt-4-turbo", ProviderType.OPENAI, "gpt-4-turbo")
    loader.add_cloud_preset("qwen2.5:7b", ProviderType.OLLAMA, "ollama/qwen2.5:7b")
    loader.add_embedding_preset("multilingual-e5-large", "intfloat/multilingual-e5-large", 1024)
    loader.add_embedding_preset("all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2", 384)
    return loader


@pytest.fixture
def provider_registry(mock_presets_loader: MockPresetsLoader) -> ProviderRegistry:
    """Create provider registry with mock presets loader."""
    registry = ProviderRegistry()
    registry.set_presets_loader(mock_presets_loader)  # type: ignore[arg-type]
    return registry


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    """Create mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_embedding_provider() -> MockEmbeddingProvider:
    """Create mock embedding provider."""
    return MockEmbeddingProvider()


@pytest.fixture
def mock_vram_monitor() -> MagicMock:
    """Create mock VRAM monitor."""
    monitor = MagicMock()
    monitor.can_allocate = MagicMock(return_value=True)
    monitor.get_vram_usage = MagicMock(return_value={"used_mb": 1000, "total_mb": 24000})
    return monitor


@pytest.fixture
def embedding_manager(mock_presets_loader: MockPresetsLoader) -> EmbeddingManager:
    """Create embedding manager with mock presets loader."""
    return EmbeddingManager(
        presets_loader=mock_presets_loader,  # type: ignore[arg-type]
        device="cpu",
        max_loaded_models=3,
    )


@pytest.fixture
def embedding_manager_with_vram(
    mock_presets_loader: MockPresetsLoader,
    mock_vram_monitor: MagicMock,
) -> EmbeddingManager:
    """Create embedding manager with VRAM monitor."""
    manager = EmbeddingManager(
        presets_loader=mock_presets_loader,  # type: ignore[arg-type]
        device="cuda",
        max_loaded_models=3,
    )
    manager.set_vram_monitor(mock_vram_monitor)
    return manager


@pytest.fixture
def mock_env_vars() -> Iterator[None]:
    """Mock environment variables for API keys."""
    with patch.dict(
        "os.environ",
        {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "OPENAI_API_KEY": "test-openai-key",
            "MOCK_API_KEY": "test-mock-key",
        },
    ):
        yield
