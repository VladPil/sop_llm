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

## Быстрый старт

### Требования

- **Python** 3.11+
- **Redis** 7.0+
- **NVIDIA GPU** (опционально, для локальных моделей)

### Установка

1. Клонировать репозиторий и создать виртуальное окружение
2. Установить зависимости: `pip install -e ".[dev]"`
3. Настроить переменные окружения (см. [docs/configuration.md](docs/configuration.md))
4. Запустить Redis
5. Запустить сервис: `python main.py`

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

### Models API

| Method | Endpoint | Описание |
|--------|----------|----------|
| `GET` | `/api/v1/models` | Список загруженных моделей |
| `GET` | `/api/v1/models/{name}` | Информация о модели (lazy loading) |
| `GET` | `/api/v1/models/presets` | Список доступных пресетов |
| `DELETE` | `/api/v1/models/{name}` | Удалить модель из registry |

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

## Документация

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`

### Дополнительно

- [Conversations API](docs/conversations.md)
- [Конфигурация](docs/configuration.md)
- [Model Presets](docs/model-presets.md)
- [Тестирование](docs/testing.md)
- [Docker](docs/docker.md)
