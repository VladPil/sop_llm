"""
Фикстуры для РЕАЛЬНЫХ интеграционных тестов
Использует настоящие модели и Redis
"""
import pytest
import asyncio
import os
import torch
import yaml
from pathlib import Path
from redis.asyncio import Redis
from typing import AsyncGenerator
from httpx import AsyncClient

from app.models.llm_manager import LLMManager
from app.models.embedding_manager import EmbeddingManager
from app.models.provider_manager import ProviderManager
from app.models.json_fixer import JSONFixerManager
from app.cache.redis_cache import RedisCache
from app.config import settings
from src.main import app


# Легкие модели для тестирования
TEST_LLM_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"  # ~500MB
TEST_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # ~80MB


@pytest.fixture(scope="session")
def event_loop():
    """
    Создает event loop для всей сессии тестов
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def real_redis() -> AsyncGenerator[Redis, None]:
    """
    РЕАЛЬНЫЙ Redis клиент для интеграционных тестов

    Требования:
    - Redis должен быть запущен на localhost:6379
    """
    redis_client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=False
    )

    try:
        # Проверяем подключение
        await redis_client.ping()
        print(f"\n✓ Redis connected: {settings.redis_host}:{settings.redis_port}")
    except Exception as e:
        pytest.fail(f"Redis is not available: {e}\nPlease start Redis with: docker run -d -p 6379:6379 redis")

    yield redis_client

    # Cleanup: удаляем тестовые ключи
    async for key in redis_client.scan_iter(match="test:*"):
        await redis_client.delete(key)

    await redis_client.close()


@pytest.fixture(scope="session")
async def real_redis_cache(real_redis: Redis) -> AsyncGenerator[RedisCache, None]:
    """
    РЕАЛЬНЫЙ RedisCache с настроенным клиентом
    """
    cache = RedisCache()
    cache.client = real_redis
    cache.ttl = 300  # 5 минут для тестов

    yield cache


@pytest.fixture(scope="session")
async def real_llm_manager() -> AsyncGenerator[LLMManager, None]:
    """
    РЕАЛЬНЫЙ LLMManager с загруженной моделью

    Использует легкую модель Qwen2.5-0.5B-Instruct
    Первый запуск может занять время на скачивание модели
    """
    manager = LLMManager(max_concurrent_requests=2)

    print(f"\n⏳ Loading LLM model: {TEST_LLM_MODEL}")
    print("   (First run may take time to download model...)")

    await manager.load_model(model_name=TEST_LLM_MODEL)

    print(f"✓ LLM model loaded: {manager.model_name}")
    print(f"  Device: {manager.device}")

    yield manager

    # Cleanup
    if manager.model:
        del manager.model
        del manager.tokenizer
        torch.cuda.empty_cache()


@pytest.fixture(scope="session")
async def real_embedding_manager() -> AsyncGenerator[EmbeddingManager, None]:
    """
    РЕАЛЬНЫЙ EmbeddingManager с загруженной моделью

    Использует легкую модель all-MiniLM-L6-v2
    """
    manager = EmbeddingManager()

    print(f"\n⏳ Loading Embedding model: {TEST_EMBEDDING_MODEL}")

    await manager.load_model(model_name=TEST_EMBEDDING_MODEL)

    print(f"✓ Embedding model loaded: {manager.model_name}")
    print(f"  Device: {manager.device}")

    yield manager

    # Cleanup
    if manager.model:
        del manager.model
        del manager.tokenizer
        torch.cuda.empty_cache()


@pytest.fixture(scope="function")
async def clean_redis(real_redis: Redis):
    """
    Очищает Redis перед каждым тестом
    """
    # Удаляем все тестовые ключи перед тестом
    async for key in real_redis.scan_iter(match="test:*"):
        await real_redis.delete(key)

    yield

    # Очищаем после теста
    async for key in real_redis.scan_iter(match="test:*"):
        await real_redis.delete(key)


@pytest.fixture
def sample_prompts():
    """
    Примеры промптов для тестирования
    """
    return [
        "What is the capital of France?",
        "Explain quantum computing in one sentence.",
        "Write a haiku about programming.",
    ]


@pytest.fixture
def sample_texts_for_embedding():
    """
    Примеры текстов для embedding
    """
    return [
        "The quick brown fox jumps over the lazy dog.",
        "Python is a high-level programming language.",
        "Machine learning is a subset of artificial intelligence.",
    ]


# Маркеры для pytest
def pytest_configure(config):
    """
    Регистрация маркеров
    """
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (requires real models and Redis)"
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (model loading, generation, etc)"
    )
    config.addinivalue_line(
        "markers",
        "requires_redis: marks tests that require Redis to be running"
    )
    config.addinivalue_line(
        "markers",
        "requires_gpu: marks tests that require GPU (optional)"
    )
    config.addinivalue_line(
        "markers",
        "requires_api_key: marks tests that require API keys (Claude, OpenAI, etc)"
    )
    config.addinivalue_line(
        "markers",
        "requires_external_service: marks tests that require external services (LM Studio, etc)"
    )


# ==================== НОВЫЕ FIXTURES ДЛЯ PROVIDER ARCHITECTURE ====================


@pytest.fixture(scope="session")
async def provider_manager() -> AsyncGenerator[ProviderManager, None]:
    """
    РЕАЛЬНЫЙ ProviderManager с инициализированными провайдерами

    Загружает конфигурацию из config/providers.yaml
    """
    pm = ProviderManager()

    # Загружаем конфигурацию провайдеров
    config_path = Path(__file__).parent.parent / "config" / "providers.yaml"

    if not config_path.exists():
        pytest.fail(f"Providers config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        providers_yaml = yaml.safe_load(f)
        providers_config = providers_yaml.get("providers", [])

    # Модифицируем конфигурацию для тестов - используем легкую модель
    for provider_config in providers_config:
        if provider_config.get("name") == "local":
            provider_config["config"]["default_model"] = TEST_LLM_MODEL

    print(f"\n⏳ Initializing ProviderManager with {len(providers_config)} providers...")

    try:
        await pm.initialize(providers_config)
        print(f"✓ ProviderManager initialized")
        print(f"  Providers: {list(pm.providers.keys())}")
        print(f"  Default: {pm.default_provider}")
    except Exception as e:
        print(f"⚠ Warning: Some providers failed to initialize: {e}")
        # Продолжаем если хотя бы один провайдер инициализирован
        if not pm.providers:
            pytest.fail(f"No providers initialized: {e}")

    yield pm

    # Cleanup
    await pm.cleanup()


@pytest.fixture(scope="session")
async def json_fixer_manager() -> AsyncGenerator[JSONFixerManager, None]:
    """
    РЕАЛЬНЫЙ JSONFixerManager для тестирования JSON исправления

    Использует легкую модель для тестов
    """
    if not settings.enable_json_fixing:
        pytest.skip("JSON Fixer disabled in settings")

    fixer = JSONFixerManager()

    print(f"\n⏳ Loading JSON Fixer model...")

    try:
        # Используем легкую модель для тестов (если не указана другая)
        test_fixer_model = os.getenv("TEST_JSON_FIXER_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
        await fixer.load_model(model_name=test_fixer_model)
        print(f"✓ JSON Fixer model loaded: {fixer.model_name}")
    except Exception as e:
        print(f"⚠ Warning: JSON Fixer failed to load: {e}")
        pytest.skip(f"JSON Fixer not available: {e}")

    yield fixer

    # Cleanup
    if fixer.model:
        del fixer.model
        del fixer.tokenizer
        torch.cuda.empty_cache()


@pytest.fixture(scope="session")
async def test_client(provider_manager: ProviderManager) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient для тестирования API endpoints

    Использует ASGI приложение напрямую (без запуска сервера)
    Переопределяет зависимость get_provider_manager для использования тестового provider_manager
    """
    from app.dependencies import get_provider_manager

    # Переопределяем зависимость
    app.dependency_overrides[get_provider_manager] = lambda: provider_manager

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        print(f"\n✓ Test client created with provider_manager override")
        yield client

    # Очищаем переопределения после тестов
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def clean_provider_stats(provider_manager: ProviderManager):
    """
    Сбрасывает статистику провайдеров перед каждым тестом
    (если нужно для изоляции тестов)
    """
    # Перед тестом - ничего не делаем

    yield

    # После теста - можно сбросить счетчики если нужно
    # (зависит от реализации провайдеров)
    pass


@pytest.fixture
def sample_json_prompts():
    """
    Примеры промптов для JSON генерации
    """
    return [
        'Create a JSON object: {"name": "Alice", "age": 30}',
        'Generate JSON with fields: status, message, code',
        'Return a JSON array of three numbers',
    ]


@pytest.fixture
def sample_json_schemas():
    """
    Примеры JSON Schema для валидации
    """
    return {
        "user": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "email": {"type": "string", "format": "email"}
            },
            "required": ["name", "age"]
        },
        "response": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"},
                "code": {"type": "integer"}
            },
            "required": ["status", "code"]
        },
        "list": {
            "type": "array",
            "items": {"type": "number"}
        }
    }


@pytest.fixture(scope="session")
def sop_llm_base_url():
    """
    Базовый URL для sop_llm API

    Можно переопределить через переменную окружения SOP_LLM_BASE_URL:
    - Внутри контейнера: http://localhost:8023/api/v1
    - Снаружи контейнера: http://localhost:8001/api/v1
    """
    return os.getenv("SOP_LLM_BASE_URL", "http://localhost:8023/api/v1")
