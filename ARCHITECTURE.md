# SOP LLM Service - Архитектура

## Общая информация

**Название**: SOP LLM Service  
**Назначение**: Асинхронный сервис для работы с множественными LLM провайдерами  
**Язык**: Python 3.11+  
**Фреймворк**: FastAPI 0.115+  
**Архитектурный стиль**: Async-first, модульная архитектура, DDD-подобная структура

## Технологический стек

### Core
- **Python**: 3.11+ (type hints, async/await)
- **FastAPI**: 0.115+ (async web framework)
- **Uvicorn**: 0.32+ (ASGI сервер)
- **Pydantic**: 2.9+ (валидация данных, настройки)
- **Pydantic-Settings**: 2.6+ (конфигурация из env)

### ML/AI
- **PyTorch**: 2.5+ (ML framework)
- **Transformers**: 4.46+ (HuggingFace моделей)
- **Sentence-Transformers**: 3.2+ (embedding модели)
- **Anthropic**: 0.39+ (Claude API)
- **llama-cpp-python**: 0.3+ (GGUF модели)

### Инфраструктура
- **Redis**: 5.2+ (кэширование, очереди)
- **FastStream**: 0.5+ (async messaging)
- **Loguru**: 0.7+ (структурированное логирование)
- **psutil**: 6.1+ (системный мониторинг)

### Качество кода
- **Ruff**: 0.7+ (линтер + форматер)
- **MyPy**: 1.13+ (статическая типизация)
- **Pytest**: 8.3+ (тестирование)
- **Pytest-asyncio**: 0.24+ (async тесты)

## Структура проекта

```
sop_llm/
├── config/                      # YAML конфигурации
│   ├── models.yaml             # Настройки LLM моделей
│   ├── embeddings.yaml         # Настройки embedding моделей
│   └── providers.yaml          # Настройки провайдеров
│
├── src/
│   ├── api/                    # HTTP API слой
│   │   ├── v1/                # API версии 1
│   │   │   ├── health.py      # Health checks
│   │   │   ├── models.py      # Endpoints для LLM
│   │   │   ├── similarity.py  # Similarity вычисления
│   │   │   └── tasks.py       # Async задачи
│   │   └── schemas.py         # Pydantic схемы API
│   │
│   ├── core/                   # Ядро приложения
│   │   ├── config.py          # Pydantic Settings (env vars)
│   │   ├── constants.py       # Константы
│   │   └── dependencies.py    # FastAPI DI
│   │
│   ├── modules/               # Бизнес-модули
│   │   ├── llm/              # LLM модуль
│   │   │   ├── providers/    # Провайдеры (Strategy pattern)
│   │   │   │   ├── base.py           # BaseLLMProvider (ABC)
│   │   │   │   ├── local_provider.py # HuggingFace
│   │   │   │   ├── claude_provider.py # Claude API
│   │   │   │   ├── lm_studio_provider.py # LM Studio
│   │   │   │   └── factory.py        # Factory pattern
│   │   │   │
│   │   │   ├── services/     # Сервисный слой
│   │   │   │   ├── llm_manager.py      # Управление LLM
│   │   │   │   ├── embedding_manager.py # Управление embeddings
│   │   │   │   ├── json_fixer.py       # JSON исправление
│   │   │   │   ├── provider_manager.py # Управление провайдерами
│   │   │   │   └── unified_llm.py      # Единый интерфейс
│   │   │   │
│   │   │   └── formatters/   # Форматирование
│   │   │       ├── base.py          # BaseFormatter
│   │   │       └── json_parser.py   # JSON парсинг
│   │   │
│   │   └── monitoring/       # Мониторинг модуль
│   │       ├── api/
│   │       │   └── websocket.py    # WebSocket endpoint
│   │       └── services/
│   │           └── statistics.py   # Статистика
│   │
│   ├── shared/               # Общий код
│   │   ├── cache/           # Кэширование
│   │   │   └── redis_cache.py     # Redis клиент
│   │   │
│   │   ├── errors/          # Обработка ошибок
│   │   │   ├── base.py            # Базовые исключения
│   │   │   ├── domain_errors.py   # Доменные ошибки
│   │   │   ├── handlers.py        # Error handlers
│   │   │   ├── context.py         # Trace context
│   │   │   └── decorators.py      # Retry, timeout
│   │   │
│   │   ├── logging/         # Логирование
│   │   │   └── config.py          # Loguru setup
│   │   │
│   │   └── utils/           # Утилиты
│   │       └── model_loader.py    # Загрузка моделей
│   │
│   ├── tests/               # Тесты
│   │   ├── conftest.py            # Pytest fixtures
│   │   ├── test_api_providers.py  # API тесты
│   │   └── test_*.py
│   │
│   └── main.py              # Entry point
│
├── docker-compose.yml       # Docker Compose
├── Makefile                 # Команды разработки
├── pyproject.toml          # Конфигурация проекта
└── .env.example            # Пример переменных окружения
```

## Архитектурные паттерны

### 1. Dependency Injection (FastAPI)
```python
# src/core/dependencies.py
def get_llm_manager() -> LLMManager:
    return llm_manager

# src/api/v1/models.py
async def generate(llm: LLMManagerDep):
    return await llm.generate(...)
```

### 2. Strategy Pattern (Провайдеры)
```python
# Базовый интерфейс
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str: ...

# Реализации
class LocalProvider(BaseLLMProvider): ...
class ClaudeProvider(BaseLLMProvider): ...
class LMStudioProvider(BaseLLMProvider): ...
```

### 3. Factory Pattern
```python
# src/modules/llm/providers/factory.py
def register_provider(name: str):
    def decorator(cls):
        _registry[name] = cls
        return cls
    return decorator

@register_provider("local")
class LocalProvider(BaseLLMProvider): ...
```

### 4. Singleton Pattern
```python
# Глобальные инстансы менеджеров
llm_manager = LLMManager()
embedding_manager = EmbeddingManager()
provider_manager = ProviderManager()
```

### 5. Repository Pattern (частично)
```python
# Redis как хранилище
class RedisCache:
    async def get(self, key: str) -> Any: ...
    async def set(self, key: str, value: Any): ...
```

## Ключевые сущности

### 1. LLM Провайдеры
**Назначение**: Абстракция над различными LLM API  
**Реализации**:
- `LocalProvider` - HuggingFace Transformers (локальные модели)
- `ClaudeProvider` - Anthropic Claude API
- `LMStudioProvider` - LM Studio API

**Capabilities** (enum):
- `TEXT_GENERATION` - генерация текста
- `CHAT` - чат режим
- `STREAMING` - потоковая генерация
- `FUNCTION_CALLING` - вызов функций

### 2. Менеджеры

#### LLMManager
- Управление локальными LLM моделями
- Пул запросов (Semaphore для concurrency control)
- Проверка памяти
- Async генерация через executor

#### EmbeddingManager
- Генерация векторных представлений
- Batch processing
- Кэширование результатов
- Косинусное сходство

#### ProviderManager
- Регистрация провайдеров
- Динамическая инициализация
- Fallback механизм
- Health checks

#### UnifiedLLM
- Единый интерфейс для всех провайдеров
- Автоматический выбор провайдера
- Fallback между провайдерами

### 3. JSON Fixer
**Проблема**: Слабые LLM возвращают невалидный JSON  
**Решение**: Использование более мощной модели для исправления
- Валидация через jsonschema
- Retry механизм
- Structured output

### 4. Task System
**Паттерн**: Async/Background tasks  
**Компоненты**:
- In-memory storage (`TaskStorage`)
- Async execution
- Status tracking (`pending`, `processing`, `completed`, `failed`)

### 5. Мониторинг
- WebSocket для real-time статистики
- Метрики: requests, tokens, latency
- Prometheus-ready (через `prometheus-client`)

## Поток данных

### Генерация текста
```
User → API endpoint → UnifiedLLM → ProviderManager
                                      ↓
                              выбор провайдера
                                      ↓
                          LocalProvider / ClaudeProvider
                                      ↓
                              model.generate()
                                      ↓
                          форматирование ответа
                                      ↓
                              User ← Response
```

### Embedding + Similarity
```
User → similarity endpoint → EmbeddingManager
                                    ↓
                            проверка cache
                                    ↓
                            генерация embeddings
                                    ↓
                            косинусное сходство
                                    ↓
                            сохранение в cache
                                    ↓
                            User ← similarity score
```

## Конфигурация

### Переменные окружения (.env)
```env
# App
APP_NAME=SOP LLM Service
ENVIRONMENT=development|staging|production
DEBUG=true|false

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8023
SERVER_WORKERS=4

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# LLM
LLM_DEFAULT_MODEL=Qwen/Qwen2.5-7B-Instruct
LLM_MAX_TOKENS_PER_REQUEST=2048
LLM_MAX_CONCURRENT_REQUESTS=5

# Embeddings
LLM_DEFAULT_EMBEDDING_MODEL=intfloat/multilingual-e5-large

# JSON Fixer
JSON_FIXER_ENABLED=true
JSON_FIXER_MODEL=Qwen/Qwen2.5-7B-Instruct
```

### YAML конфигурация
- `config/models.yaml` - параметры моделей
- `config/embeddings.yaml` - параметры embedding
- `config/providers.yaml` - настройки провайдеров

## Async архитектура

### Lifespan Management
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_cache.connect()
    await provider_manager.initialize()
    await llm_manager.load_model()
    
    yield
    
    # Shutdown
    await provider_manager.cleanup()
    await redis_cache.disconnect()
```

### Concurrency Control
- **Semaphore**: ограничение параллельных запросов
- **asyncio.Queue**: очередь задач
- **run_in_executor**: блокирующие операции (model.generate)

### Timeout Management
```python
async def generate_with_timeout(prompt, timeout=60):
    return await asyncio.wait_for(
        self.generate(prompt),
        timeout=timeout
    )
```

## Обработка ошибок

### Иерархия исключений
```
AppError (базовый)
├── ModelNotLoadedError
├── MemoryExceededError
├── ProviderError
│   ├── ProviderNotFoundError
│   ├── ProviderNotAvailableError
│   └── ProviderInitializationError
├── JSONFixFailedError
└── ServiceUnavailableError
```

### Error Handlers
- Автоматическое логирование
- Structured response (trace_id, error_code, message)
- HTTP status mapping

### Trace Context
```python
# Каждый запрос получает уникальный trace_id
trace_id = get_trace_id()  # из context
logger.info("Processing", extra={"trace_id": trace_id})
```

## Кэширование

### Стратегия
- **TTL**: по умолчанию 1 час
- **Key pattern**: `{prefix}:{hash(params)}`
- **Invalidation**: TTL-based (нет manual invalidation)

### Что кэшируется
- Embedding vectors
- Similarity results
- Provider health checks

## Логирование

### Loguru
- Структурированное логирование
- Ротация по размеру (50MB)
- Retention: 7 дней
- JSON формат для production

### Уровни
- `DEBUG`: детальная информация
- `INFO`: основные события
- `WARNING`: предупреждения
- `ERROR`: ошибки с trace

## Тестирование

### Маркеры
- `@pytest.mark.unit` - юнит-тесты (моки)
- `@pytest.mark.system` - системные (Redis)
- `@pytest.mark.api` - API endpoints
- `@pytest.mark.integration` - интеграционные
- `@pytest.mark.slow` - медленные (> 1s)

### Coverage
- Минимальный порог: 80%
- Отчеты: HTML, XML, terminal

## Безопасность

### Валидация
- Pydantic для всех входных данных
- Max длина промптов
- Rate limiting (через Redis)

### Secrets
- Переменные окружения
- Нет хардкода в коде
- `.env` в `.gitignore`

## Производительность

### Оптимизации
- Async I/O везде
- Connection pooling (Redis)
- Batch processing (embeddings)
- Model quantization (8-bit)

### Ограничения
- Max concurrent: 5 LLM requests
- Max tokens: 2048 per request
- Memory threshold: 90%

## Deployment

### Docker
- Multi-stage builds
- Healthchecks
- Volume для моделей

### Docker Compose
- App + Redis + Monitoring
- Networks для изоляции
- Restart policies

## Мониторинг

### Метрики
- Request count
- Token usage
- Latency (p50, p95, p99)
- Memory usage
- Active connections

### Health Checks
- `/api/v1/health` - базовый
- Проверка Redis
- Проверка моделей

## Расширяемость

### Добавление провайдера
1. Наследоваться от `BaseLLMProvider`
2. Реализовать `generate()`, `health_check()`
3. Декоратор `@register_provider("name")`

### Добавление endpoint
1. Создать схемы в `api/schemas.py`
2. Реализовать handler в `api/v1/`
3. Подключить в `router.py`

## Известные ограничения

1. **In-memory task storage** - при рестарте теряются
2. **Нет персистентности** - только Redis cache
3. **Single instance** - нет распределенной обработки
4. **Model loading** - блокирует startup (можно улучшить)

## Следующие шаги

1. **Персистентность**: PostgreSQL для задач
2. **Distributed**: Celery/FastStream для задач
3. **Streaming**: Server-Sent Events для генерации
4. **Auth**: JWT токены
5. **Rate limiting**: Redis-based
