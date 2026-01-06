# SOP LLM Executor

**Высокопроизводительный асинхронный сервис для работы с языковыми моделями**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Описание

SOP LLM Executor — это production-ready асинхронный сервис на FastAPI для унифицированной работы с различными провайдерами языковых моделей. Реализует паттерн "Dumb Executor" — сервис выполняет только inference, вся бизнес-логика и промпты передаются в запросах.

### Ключевые особенности

- **🔌 Унифицированный интерфейс** — работа с локальными и удаленными моделями через единый Protocol
- **⚡ Асинхронная архитектура** — полная поддержка async/await, высокая производительность
- **🎯 Single Worker** — GPU Guard обеспечивает эксклюзивный доступ к GPU
- **📦 Redis Storage** — хранение задач с TTL 24 часа
- **🔄 Priority Queue** — обработка задач с приоритетами
- **🔐 Idempotency** — дедупликация запросов через ключи идемпотентности
- **🪝 Webhooks** — асинхронные колбеки с exponential backoff retry
- **📊 Structured Output** — JSON Schema + GBNF грамматики для валидного вывода
- **🎛️ VRAM Monitoring** — отслеживание использования GPU памяти

## Поддерживаемые провайдеры

| Провайдер | Тип | Streaming | Structured Output | VRAM Control |
|-----------|-----|-----------|-------------------|--------------|
| **Local (llama.cpp)** | GGUF | ✅ | ✅ (GBNF) | ✅ |
| **OpenAI** | API | ✅ | ✅ (JSON Schema) | — |
| **Anthropic** | API | ✅ | ✅ (JSON mode) | — |
| **OpenAI-Compatible** | API | ✅ | ⚠️ | — |

## Архитектура

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /api/tasks
       ▼
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│  ┌────────────┐  ┌──────────────────┐   │
│  │   Routes   │  │   TaskProcessor  │   │
│  │  (tasks,   │  │   (Background    │   │
│  │  models,   │  │    Worker)       │   │
│  │  monitor)  │  └─────────┬────────┘   │
│  └─────┬──────┘            │            │
│        │                   │            │
│        ▼                   ▼            │
│  ┌──────────────────────────────────┐   │
│  │       Session Store (Redis)      │   │
│  │  • Tasks (24h TTL)               │   │
│  │  • Priority Queue (Sorted Set)   │   │
│  │  • Idempotency Keys              │   │
│  │  • Logs                          │   │
│  └──────────────────────────────────┘   │
└──────────────────┬──────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌─────────────┐         ┌─────────────┐
│  GPU Guard  │         │  Provider   │
│  (Singleton)│         │  Registry   │
│             │         │             │
│  • Lock     │         │  • Local    │
│  • VRAM Mon │         │  • OpenAI   │
│             │         │  • Anthropic│
└─────────────┘         └─────────────┘
```

## Установка

### Требования

- **Python** 3.11+
- **Redis** 7.0+
- **NVIDIA GPU** (опционально, для локальных моделей)
- **CUDA 12+** (опционально)

### Быстрый старт

```bash
# Клонировать репозиторий
git clone git@github.com:VladPil/sop_llm.git
cd sop_llm

# Создать виртуальное окружение
python3.11 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -e ".[dev]"

# Настроить переменные окружения (выбрать нужное окружение)
cp .docker/configs/.env.local .env
# Отредактировать .env

# Запустить Redis
docker run -d -p 6379:6379 redis:7-alpine

# Запустить сервис
python main.py
```

## Конфигурация

Все настройки через переменные окружения или `.env` файл:

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
REDIS_POOL_SIZE=10

# === GPU ===
GPU_INDEX=0
MAX_VRAM_USAGE_PERCENT=95
VRAM_RESERVE_MB=1024

# === Local Models ===
LOCAL_MODEL_PATH=/models/qwen2.5-7b-instruct.gguf
LOCAL_MODEL_CONTEXT_WINDOW=8192
LOCAL_MODEL_GPU_LAYERS=-1  # -1 = все слои на GPU

# === API Keys (опционально) ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## API Документация

### Основные endpoints

#### Создать задачу генерации

```http
POST /api/tasks
Content-Type: application/json

{
  "model": "qwen-7b",
  "prompt": "Напиши функцию для сортировки массива",
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": false,
  "webhook_url": "https://myapp.com/webhook",
  "idempotency_key": "user-123-req-456",
  "priority": 10.0
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "model": "qwen-7b",
  "created_at": "2024-12-30T00:00:00Z",
  "updated_at": "2024-12-30T00:00:00Z"
}
```

#### Получить статус задачи

```http
GET /api/tasks/{task_id}
```

**Response (completed):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "model": "qwen-7b",
  "result": {
    "text": "def sort_array(arr):\\n    return sorted(arr)",
    "finish_reason": "stop",
    "usage": {
      "prompt_tokens": 15,
      "completion_tokens": 12,
      "total_tokens": 27
    }
  },
  "created_at": "2024-12-30T00:00:00Z",
  "updated_at": "2024-12-30T00:00:01Z",
  "finished_at": "2024-12-30T00:00:01Z"
}
```

#### Регистрация модели

```http
POST /api/models
Content-Type: application/json

{
  "name": "qwen-7b",
  "provider": "local",
  "config": {
    "model_path": "/models/qwen2.5-7b-instruct.gguf",
    "context_window": 8192,
    "gpu_layers": -1
  }
}
```

#### Мониторинг

```http
GET /api/monitor/health
GET /api/monitor/gpu
GET /api/monitor/queue
```

### Swagger UI

Полная интерактивная документация доступна по адресу:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Примеры использования

### Python клиент

```python
import httpx

async def generate_text():
    async with httpx.AsyncClient() as client:
        # Создать задачу
        response = await client.post(
            "http://localhost:8000/api/tasks",
            json={
                "model": "qwen-7b",
                "prompt": "Объясни квантовую запутанность",
                "temperature": 0.7,
                "max_tokens": 500
            }
        )
        task = response.json()
        task_id = task["task_id"]

        # Дождаться завершения
        while True:
            response = await client.get(
                f"http://localhost:8000/api/tasks/{task_id}"
            )
            task = response.json()
            if task["status"] in ["completed", "failed"]:
                break
            await asyncio.sleep(1)

        if task["status"] == "completed":
            print(task["result"]["text"])
```

### С webhook callback

```python
# Создать задачу с webhook
response = await client.post(
    "http://localhost:8000/api/tasks",
    json={
        "model": "qwen-7b",
        "prompt": "Напиши стихотворение",
        "webhook_url": "https://myapp.com/llm-callback"
    }
)

# Сервис отправит POST запрос на webhook_url при завершении
```

### С JSON Schema (structured output)

```python
response = await client.post(
    "http://localhost:8000/api/tasks",
    json={
        "model": "gpt-4",
        "prompt": "Извлеки имя, возраст и город из текста: 'Меня зовут Иван, мне 25 лет, живу в Москве'",
        "response_format": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "city": {"type": "string"}
            },
            "required": ["name", "age", "city"]
        }
    }
)
```

## Тестирование

```bash
# Все тесты
pytest

# Unit тесты
pytest src/tests/unit -v

# С coverage
pytest --cov=src --cov-report=html

# Линтинг
ruff check src

# Типы
mypy src
```

## Структура проекта

```
sop_llm/
├── config/               # Pydantic Settings
│   ├── __init__.py
│   └── settings.py
├── src/
│   ├── api/             # FastAPI routes
│   │   ├── routes/      # Endpoints (tasks, models, monitor)
│   │   └── schemas/     # Pydantic models (requests, responses)
│   ├── engine/          # GPU управление
│   │   ├── gpu_guard.py       # Singleton GPU lock
│   │   └── vram_monitor.py    # VRAM tracking
│   ├── providers/       # LLM providers
│   │   ├── base.py            # Protocol + Pydantic models
│   │   ├── registry.py        # Provider registry
│   │   ├── local.py           # llama.cpp (GGUF)
│   │   ├── openai.py          # OpenAI API
│   │   ├── anthropic.py       # Anthropic API
│   │   └── openai_compatible.py
│   ├── services/        # Business logic
│   │   ├── session_store.py   # Redis storage
│   │   └── task_processor.py  # Background worker
│   ├── utils/           # Утилиты
│   │   └── logging.py
│   ├── tests/           # Тесты
│   │   └── unit/
│   ├── app.py           # FastAPI app
│   └── __init__.py
├── main.py              # Entry point
├── pyproject.toml       # Зависимости
├── README.md
├── config/              # Конфигурационные файлы (pytest.ini, pre-commit)
└── .docker/configs/     # Environment файлы (.env.local, .env.dev, .env.prod)
```

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -e .

# ВАЖНО: Single worker
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### Docker Compose

```yaml
version: '3.8'

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
      - SERVER_WORKERS=1  # КРИТИЧНО
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

## Лицензия

MIT License - смотрите [LICENSE](LICENSE)

## Автор

Vladislav <vladislav@example.com>
