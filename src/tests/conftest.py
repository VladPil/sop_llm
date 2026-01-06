"""Pytest configuration для интеграционных тестов.

Этот файл содержит общие фикстуры для тестирования SOP LLM сервиса.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from src.app import app
from src.core.config import settings


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
        await client.ping()
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
