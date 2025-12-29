# SOP LLM - План рефакторинга согласно ТЗ

## Критические изменения архитектуры

### 1. Паттерн "Dumb Executor"
**Было:** Сервис знает о бизнес-логике, хранит промпты  
**Будет:** Сервис только выполняет инференс, промпты приходят в запросе

### 2. Структура проекта
**Было:**
```
src/
├── api/
├── core/
├── modules/llm/
│   ├── providers/
│   ├── services/
│   └── formatters/
├── shared/
└── tests/
```

**Будет (плоская структура):**
```
src/
├── api/
│   ├── routes/      # tasks.py, models.py, monitor.py
│   ├── schemas/     # requests.py, responses.py, providers.py
│   └── websocket.py
├── providers/       # base.py, registry.py, local.py, openai_compatible.py, anthropic.py
├── engine/          # gpu_guard.py, vram_monitor.py
├── services/        # task_processor.py, session_store.py, structured_output.py, webhook_sender.py
├── utils/           # logging.py, validators.py
└── main.py
```

### 3. Ключевые компоненты

#### GPU Guard (НОВЫЙ - критичный!)
- **Singleton** с asyncio.Lock
- Эксклюзивный доступ к GPU для local provider
- Hot Path (пропуск загрузки если модель уже в VRAM)
- VRAM monitoring через pynvml

#### Provider Architecture (ПОЛНАЯ ПЕРЕРАБОТКА)
- **Protocol + Registry** вместо ABC + Factory
- Unified типы: `GenerateRequest`, `GenerateResult`, `ProviderCapabilities`
- Провайдеры:
  - `local` - llama-cpp-python (GGUF) вместо transformers
  - `openai_compatible` - LM Studio, vLLM, Ollama, OpenRouter, Together AI
  - `anthropic` - Claude API
  - `openai` - GPT-4, GPT-4o
  - `custom` - произвольный HTTP endpoint

#### Session Store (НОВЫЙ)
- Redis-based, TTL 24 часа
- Никакой персистентной БД!
- Статусы: created → queued → processing → completed/failed

#### Structured Output (НОВЫЙ)
- GBNF грамматики для llama-cpp-python
- 100% гарантия валидного JSON
- Grammar-based sampling

### 4. API Endpoints (ПОЛНАЯ ПЕРЕРАБОТКА)

**Новые endpoints:**
- `POST /api/v1/tasks` - создание задачи
- `GET /api/v1/tasks/{task_id}` - статус задачи
- `GET /api/v1/tasks/{task_id}/report` - детальный отчет
- `POST /api/v1/models/load` - загрузка модели в VRAM
- `POST /api/v1/models/unload` - выгрузка модели
- `GET /api/v1/models/status` - статус GPU и модели
- `GET /api/v1/monitor/status` - общий статус
- `GET /api/v1/monitor/queue` - состояние очереди
- `GET /api/v1/monitor/logs` - логи
- `WS /ws/monitor` - real-time мониторинг

**Удалить старые:**
- Все текущие endpoints (generate, embedding, similarity, tasks)

### 5. Технологический стек - изменения

**Заменить:**
- ❌ `transformers` → ✅ `llama-cpp-python` (для local)
- ❌ `sentence-transformers` → ✅ embeddings через API или отдельный сервис
- ❌ In-memory task storage → ✅ Redis Sorted Set

**Добавить:**
- ✅ `pynvml` - мониторинг GPU
- ✅ GBNF грамматики для structured output
- ✅ Webhook sender с retry

**Удалить:**
- ❌ Весь код для embedding моделей (отдельный сервис)
- ❌ JSON Fixer (заменен на GBNF)
- ❌ TaskStorage класс (заменен на Redis)

### 6. Redis Schema

**Новые ключи:**
```
queue:tasks            - Sorted Set (priority × timestamp)
queue:processing       - String (current task_id)
session:{task_id}      - Hash (task data)
idempotency:{key}      - String (task_id)
logs:recent            - List (last 1000 logs)
logs:{task_id}         - List (task logs)
pubsub:events          - Pub/Sub (WebSocket events)
pubsub:logs            - Pub/Sub (log stream)
system:gpu             - String (GPU status cache, 5s TTL)
stats:daily:{date}     - Hash (daily stats, 7d TTL)
```

### 7. Конфигурация

**Новые переменные окружения:**
```bash
# GPU
GPU_INDEX=0
MAX_VRAM_USAGE_PERCENT=95
VRAM_RESERVE_MB=1024

# Models
MODELS_DIR=/app/models

# Sessions
SESSION_TTL_HOURS=24
IDEMPOTENCY_TTL_HOURS=24

# Webhooks
WEBHOOK_TIMEOUT_SECONDS=30
WEBHOOK_MAX_RETRIES=3

# Remote Providers
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENAI_COMPATIBLE_BASE_URL=
OPENROUTER_API_KEY=
TOGETHER_API_KEY=
```

## План миграции

### Этап 1: Подготовка (текущий этап)
- [x] Анализ ТЗ
- [x] Создание REFACTORING_PLAN.md
- [ ] Backup текущего кода
- [ ] Создание ветки `refactor/dumb-executor`

### Этап 2: Infrastructure
- [ ] Обновить config/settings.py (новые env vars)
- [ ] Создать src/services/session_store.py (Redis wrapper)
- [ ] Создать src/utils/logging.py (Loguru setup)
- [ ] Обновить docker-compose.yml (Redis, CUDA 12.x)

### Этап 3: Provider Architecture
- [ ] Создать src/providers/base.py (Protocol, базовые типы)
- [ ] Создать src/providers/registry.py
- [ ] Реализовать src/providers/local.py (llama-cpp-python)
- [ ] Реализовать src/providers/openai_compatible.py
- [ ] Реализовать src/providers/anthropic.py
- [ ] Реализовать src/providers/custom.py

### Этап 4: GPU Engine
- [ ] Создать src/engine/gpu_guard.py (Singleton, asyncio.Lock)
- [ ] Создать src/engine/vram_monitor.py (pynvml wrapper)
- [ ] Интегрировать GPU Guard в LocalProvider

### Этап 5: API Layer
- [ ] Создать src/api/schemas/requests.py (Pydantic schemas)
- [ ] Создать src/api/schemas/responses.py
- [ ] Создать src/api/schemas/providers.py
- [ ] Создать src/api/routes/tasks.py
- [ ] Создать src/api/routes/models.py
- [ ] Создать src/api/routes/monitor.py
- [ ] Удалить старые endpoints

### Этап 6: Worker
- [ ] Создать src/services/task_processor.py (Queue worker)
- [ ] Создать src/services/structured_output.py (GBNF grammars)
- [ ] Создать src/services/webhook_sender.py
- [ ] Интегрировать fallback strategy

### Этап 7: Monitoring
- [ ] Создать src/api/websocket.py (WebSocket handler)
- [ ] Настроить Redis Pub/Sub для событий
- [ ] GPU stats ticker (каждые 2 сек)

### Этап 8: Cleanup
- [ ] Удалить src/modules/ (старая структура)
- [ ] Удалить src/shared/ (больше не нужна)
- [ ] Обновить tests
- [ ] Обновить ARCHITECTURE.md

## Порядок коммитов

1. `refactor: добавить базовую инфраструктуру (Redis, settings)`
2. `refactor: реализовать Provider Protocol и Registry`
3. `refactor: добавить LocalProvider с llama-cpp-python`
4. `refactor: добавить remote провайдеры (OpenAI, Anthropic)`
5. `refactor: реализовать GPU Guard и VRAM monitor`
6. `refactor: добавить новые API endpoints (Tasks, Models, Monitor)`
7. `refactor: реализовать Task Queue Worker`
8. `refactor: добавить Structured Output (GBNF)`
9. `refactor: добавить WebSocket мониторинг`
10. `refactor: удалить старый код, финальная очистка`
11. `docs: обновить документацию под новую архитектуру`

## Критичные моменты

⚠️ **GPU Guard** - самый критичный компонент, должен работать идеально
⚠️ **llama-cpp-python** - нужны GGUF модели, не HuggingFace
⚠️ **Protocol вместо ABC** - duck typing для провайдеров
⚠️ **Только Redis** - никаких файлов, никакой БД
⚠️ **Структура проекта** - плоская, без вложенности modules/

## Что НЕ менять

✅ Docker структура (.docker/)
✅ Makefile
✅ config/ директория (YAML конфиги)
✅ pyproject.toml (добавить зависимости)
