# SOP LLM Executor

**Высокопроизводительный асинхронный сервис для работы с языковыми моделями**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-1.55+-orange.svg)](https://docs.litellm.ai)

## Описание

SOP LLM Executor — production-ready асинхронный сервис на FastAPI для унифицированной работы с различными провайдерами языковых моделей. Реализует паттерн "Dumb Executor" — сервис выполняет только inference, вся бизнес-логика и промпты передаются в запросах.

### Ключевые особенности

- **Унифицированный интерфейс** — работа с 100+ моделями через LiteLLM
- **Multi-turn Conversations** — ведение диалогов с сохранением контекста в Redis
- **Model Presets** — YAML конфиги для быстрой регистрации моделей
- **Асинхронная архитектура** — полная поддержка async/await
- **GPU Guard** — эксклюзивный доступ к GPU (Single Worker)
- **Redis Storage** — хранение задач с TTL 24 часа
- **Priority Queue** — обработка задач с приоритетами
- **WebSocket Monitoring** — real-time статистика GPU и задач
- **Langfuse Observability** — трейсинг каждой генерации
- **Embeddings API** — генерация векторов и вычисление сходства
- **Structured Output** — JSON Schema + GBNF грамматики

## Поддерживаемые провайдеры

| Провайдер | Тип | Модели | Streaming |
|-----------|-----|--------|-----------|
| **Ollama** | Local GPU | Qwen, LLaMA, Mistral, Gemma, Phi | ✅ |
| **LiteLLM** | Cloud API | OpenAI, Anthropic, Google, Mistral, Groq, DeepSeek, Together AI | ✅ |
| **SentenceTransformers** | Embeddings | E5, MiniLM, BGE | — |

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      API Request                             │
│  POST /tasks {model: "claude-sonnet-4"}                     │
│  POST /embeddings {model_name: "multilingual-e5-large"}     │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────────┐     ┌─────────────────────┐
│ ProviderRegistry  │     │  EmbeddingManager   │
│ .get_or_create()  │     │  .get_or_load()     │
│                   │     │                     │
│ • Lazy loading    │     │ • Lazy loading      │
│ • Cloud + Ollama  │     │ • FIFO eviction     │
│ • No VRAM limits  │     │ • VRAM monitoring   │
└─────────┬─────────┘     └──────────┬──────────┘
          │                          │
          ▼                          ▼
┌───────────────────┐     ┌─────────────────────┐
│ ModelPresetsLoader│     │    VRAMMonitor      │
│ .get_cloud_preset │     │ .can_allocate()     │
│ .get_embedding_   │     └─────────────────────┘
│     preset        │
└───────────────────┘

┌──────────────────────────────────────────────┐
│              FastAPI Application              │
│  ┌─────────────────┐  ┌───────────────────┐  │
│  │     Routes      │  │  TaskOrchestrator │  │
│  │ tasks, models,  │  │   + Processor     │  │
│  │ monitor, embed  │  │  (Background)     │  │
│  └────────┬────────┘  └─────────┬─────────┘  │
│           │                     │            │
│           ▼                     ▼            │
│  ┌────────────────────────────────────────┐  │
│  │         Session Store (Redis)          │  │
│  │  • Tasks Queue (Sorted Set)            │  │
│  │  • Sessions (24h TTL)                  │  │
│  │  • Daily Stats (7d TTL)                │  │
│  │  • GPU Cache (5s TTL)                  │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### Lazy Loading & FIFO Eviction

**LLM модели (ProviderRegistry):**
- Провайдеры создаются автоматически при первом запросе
- Cloud модели (Claude, GPT, Gemini) — без ограничений
- Ollama модели — используют `keep_alive: 30m` для управления памятью

**Embedding модели (EmbeddingManager):**
- Модели загружаются по требованию в GPU/CPU память
- FIFO eviction при достижении лимита `max_loaded_models`
- Интеграция с VRAMMonitor для контроля VRAM

## Быстрый старт

### Требования

- **Python** 3.11+
- **Redis** 7.0+
- **NVIDIA GPU** (опционально, для локальных моделей)

### Установка

```bash
# Клонировать репозиторий
git clone git@github.com:VladPil/sop_llm.git
cd sop_llm

# Создать виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -e ".[dev]"

# Настроить переменные окружения
cp .docker/configs/.env.local .env
# Отредактировать .env

# Запустить Redis
docker run -d -p 6379:6379 redis:7-alpine

# Запустить сервис
python main.py
```

## API Endpoints

### Tasks API

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/api/v1/tasks` | Создать задачу генерации |
| `GET` | `/api/v1/tasks/{id}` | Получить статус задачи |
| `GET` | `/api/v1/tasks/{id}/report` | Детальный отчёт о выполнении |
| `DELETE` | `/api/v1/tasks/{id}` | Удалить задачу |

### Conversations API

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/api/v1/conversations` | Создать диалог |
| `GET` | `/api/v1/conversations` | Список диалогов |
| `GET` | `/api/v1/conversations/{id}` | Получить диалог с историей |
| `PATCH` | `/api/v1/conversations/{id}` | Обновить метаданные диалога |
| `DELETE` | `/api/v1/conversations/{id}` | Удалить диалог |
| `POST` | `/api/v1/conversations/{id}/messages` | Добавить сообщение |
| `GET` | `/api/v1/conversations/{id}/messages` | Получить историю сообщений |
| `DELETE` | `/api/v1/conversations/{id}/messages` | Очистить историю |

> Подробная документация: [docs/conversations.md](docs/conversations.md)

### Models API

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/api/v1/models` | Список загруженных моделей |
| `GET` | `/api/v1/models/{name}` | Информация о модели (lazy loading) |
| `GET` | `/api/v1/models/presets` | Список доступных пресетов |
| `DELETE` | `/api/v1/models/{name}` | Удалить модель из registry |

> **Lazy Loading:** Модели автоматически создаются при первом запросе к `/api/v1/models/{name}`. Ручная регистрация не требуется.

### Embeddings API

| Method | Endpoint | Описание |
|--------|----------|----------|
| `POST` | `/api/v1/embeddings` | Генерация embeddings |
| `POST` | `/api/v1/embeddings/similarity` | Вычислить сходство текстов |

### Monitor API

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/api/v1/monitor/health` | Комплексный health check |
| `GET` | `/api/v1/monitor/gpu` | Статистика GPU и VRAM |
| `GET` | `/api/v1/monitor/queue` | Статистика очереди задач |
| `GET` | `/api/v1/monitor/logs` | Логи системы |
| `GET` | `/api/v1/monitor/stats` | Дневная статистика |

### WebSocket API

| Endpoint | Описание |
|----------|----------|
| `WS /ws/monitor` | Real-time мониторинг |

**События:** `gpu_stats`, `task.queued`, `task.started`, `task.progress`, `task.completed`, `task.failed`, `model.loaded`, `model.unloaded`

## Примеры использования

### Создать задачу генерации

```python
import httpx

async with httpx.AsyncClient(base_url="http://<host>:<port>") as client:
    response = await client.post(
        "/api/v1/tasks",
        json={
            "model": "claude-3.5-sonnet",
            "prompt": "Объясни квантовую запутанность",
            "temperature": 0.7,
            "max_tokens": 500,
            "webhook_url": "https://myapp.com/callback",
            "priority": 10.0
        }
    )
    task = response.json()
    print(f"Task ID: {task['task_id']}")
```

### Использование модели (Lazy Loading)

```python
# Посмотреть доступные пресеты
response = await client.get("/api/v1/models/presets")
presets = response.json()
# cloud_models: ["claude-sonnet-4", "gpt-4-turbo", "qwen2.5:7b", ...]
# embedding_models: ["multilingual-e5-large", "all-MiniLM-L6-v2", ...]

# Модель автоматически создаётся при первом запросе
response = await client.get("/api/v1/models/claude-sonnet-4")
model_info = response.json()
# {"name": "claude-sonnet-4-20250514", "provider": "anthropic", ...}

# Или просто отправить задачу - модель загрузится автоматически
response = await client.post(
    "/api/v1/tasks",
    json={"model": "claude-sonnet-4", "prompt": "Hello!"}
)
```

### WebSocket мониторинг

```javascript
const ws = new WebSocket('ws://<host>:<port>/ws/monitor');

ws.onopen = () => {
    ws.send(JSON.stringify({
        type: 'subscribe',
        events: ['task.*', 'gpu_stats']
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data.type, data.data);
};
```

### Вычисление сходства текстов

```python
response = await client.post(
    "/api/v1/embeddings/similarity",
    json={
        "text1": "Машинное обучение - это область AI",
        "text2": "ML является частью искусственного интеллекта",
        "model_name": "multilingual-e5-large"
    }
)
result = response.json()
print(f"Similarity: {result['similarity']}")  # 0.85
```

## Конфигурация

```env
# === Application ===
APP_NAME="SOP LLM Executor"
APP_ENV=production

# === Server ===
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=1  # ВАЖНО: Single worker для GPU Guard

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === GPU ===
GPU_INDEX=0
MAX_VRAM_USAGE_PERCENT=95
VRAM_RESERVE_MB=1024

# === Models Directory ===
MODELS_DIR=/models

# === API Keys ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# === Observability ===
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Model Presets

Пресеты моделей хранятся в `config/model_presets/`:

```
config/model_presets/
├── cloud_models.yaml      # Cloud API + Ollama модели
└── embedding_models.yaml  # Embedding модели (E5, MiniLM)
```

**Пример Cloud пресета:**

```yaml
models:
  - name: "claude-sonnet-4"
    provider: "anthropic"
    api_key_env_var: "ANTHROPIC_API_KEY"
    provider_config:
      model_name: "claude-sonnet-4-20250514"
      timeout: 600
      max_retries: 3
```

**Пример Ollama пресета с keep_alive:**

```yaml
models:
  - name: "qwen2.5:7b"
    provider: "ollama"
    keep_alive: "30m"  # Держать модель в VRAM 30 минут
    provider_config:
      model_name: "ollama/qwen2.5:7b"
      base_url: "http://localhost:11434"
      timeout: 120
```

**Пример Embedding пресета:**

```yaml
models:
  - name: "multilingual-e5-large"
    huggingface_repo: "intfloat/multilingual-e5-large"
    dimensions: 1024
```

## Структура проекта

```
sop_llm/
├── config/
│   ├── model_presets/        # YAML пресеты моделей
│   ├── pytest.ini
│   └── .pre-commit-config.yaml
├── src/
│   ├── api/
│   │   ├── routes/           # Endpoints (tasks, models, monitor, embeddings, websocket)
│   │   └── schemas/          # Pydantic models
│   ├── core/                 # Config, dependencies, enums
│   ├── docs/                 # API documentation strings
│   ├── engine/               # GPU Guard, VRAM Monitor
│   ├── providers/            # LLM providers
│   │   ├── litellm_provider.py  # Cloud + Ollama (100+ models)
│   │   ├── embedding.py      # SentenceTransformers
│   │   ├── registry.py       # ProviderRegistry (lazy loading)
│   │   └── base.py           # Base classes
│   ├── services/             # Business logic
│   │   ├── session_store.py  # Redis storage
│   │   ├── embedding_manager.py  # Lazy loading + FIFO eviction
│   │   ├── model_presets/    # YAML presets loader
│   │   ├── task/             # Task orchestrator + processor
│   │   └── observability/    # Langfuse integration
│   ├── adapters/             # Request adapters
│   ├── shared/               # Shared utilities (errors, logging)
│   └── app.py                # FastAPI application
├── main.py                   # Entry point
└── pyproject.toml
```

## Тестирование

```bash
# Все тесты (270 тестов)
make test

# Unit тесты по категориям
make test-providers    # ProviderRegistry lazy loading
make test-services     # EmbeddingManager FIFO
make test-api          # API endpoints

# С coverage
make test-coverage

# Линтинг и типы
make check             # lint + type-check
```

### Структура тестов

```
src/tests/
├── conftest.py           # Fixtures (MockLLMProvider, MockPresetsLoader, etc.)
├── unit/
│   ├── api/
│   │   ├── test_models.py      # Models API endpoints
│   │   └── test_embeddings.py  # Embeddings API endpoints
│   ├── providers/
│   │   ├── test_registry.py    # ProviderRegistry lazy loading
│   │   └── test_litellm_provider.py
│   ├── services/
│   │   └── test_embedding_manager.py  # FIFO eviction tests
│   └── shared/
│       └── errors/             # Error handling tests
└── system/                     # System tests (Redis required)
```

## Docker

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - SERVER_WORKERS=1  # КРИТИЧНО для GPU Guard
    depends_on:
      - redis
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

## Документация

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`
