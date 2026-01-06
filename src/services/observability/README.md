# Observability Module

Модуль для distributed tracing, мониторинга и аналитики LLM операций через Langfuse.

## Архитектура

Модуль следует принципам SOLID и разбит на несколько специализированных модулей:

### 📦 Структура

```
observability/
├── __init__.py          # Публичный API модуля
├── client.py            # Langfuse client initialization & singleton
├── context.py           # Context managers (trace_context, span_context)
├── decorators.py        # Decorators (@trace_llm_generation, @trace_operation)
├── integrations.py      # LiteLLM callbacks configuration
├── logging_helpers.py   # Manual logging functions (log_generation, log_error)
└── utils.py             # Utility functions (get_current_trace_id, is_enabled)
```

### 🎯 Принципы разделения ответственности

| Модуль | Ответственность | Принцип SOLID |
|--------|----------------|---------------|
| `client.py` | Управление жизненным циклом Langfuse клиента (Singleton) | Single Responsibility |
| `context.py` | Async context managers для trace/span lifecycle | Single Responsibility |
| `decorators.py` | Декораторы для автоматического трейсинга | Open/Closed Principle |
| `integrations.py` | Конфигурация внешних интеграций (LiteLLM) | Dependency Inversion |
| `logging_helpers.py` | Ручное логирование событий | Single Responsibility |
| `utils.py` | Вспомогательные функции, проверка состояния | Interface Segregation |

## Использование

### Инициализация

```python
from src.services.observability import initialize_langfuse, configure_litellm_callbacks

# При старте приложения
initialize_langfuse(
    public_key="pk_xxx",
    secret_key="sk_xxx",
    host="https://cloud.langfuse.com",
    enabled=True
)

# Настройка автоматического трейсинга для LiteLLM
configure_litellm_callbacks()
```

### Trace Context

```python
from src.services.observability import trace_context

async with trace_context(
    name="llm_task",
    user_id="user123",
    session_id="session456",
    metadata={"task_id": "abc"},
    tags=["production", "high-priority"]
):
    result = await process_llm_request(...)
```

### Span Context

```python
from src.services.observability import span_context

async with span_context(
    name="load_model",
    metadata={"model_name": "llama-7b"}
):
    model = await load_model(...)
```

### Декораторы

```python
from src.services.observability import trace_llm_generation, trace_operation

@trace_llm_generation(name="local_llm_inference")
async def generate(self, prompt: str, **kwargs) -> str:
    return await self._generate(prompt, **kwargs)

@trace_operation(name="redis_cache_lookup", metadata={"cache_type": "session"})
async def get_from_cache(self, key: str) -> Any:
    return await self.redis.get(key)
```

### Ручное логирование

```python
from src.services.observability import log_generation, log_error

# Логирование LLM generation
log_generation(
    model="llama-7b",
    input_text="What is Python?",
    output_text="Python is a programming language...",
    metadata={"provider": "local", "task_id": "123"},
    usage={"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60}
)

# Логирование ошибок
try:
    await risky_operation()
except Exception as e:
    log_error(e, metadata={"operation": "model_load"})
    raise
```

### Утилиты

```python
from src.services.observability import (
    is_observability_enabled,
    get_current_trace_id,
    get_current_span_id,
    flush_observations
)

# Проверка состояния
if is_observability_enabled():
    trace_id = get_current_trace_id()
    print(f"Current trace: {trace_id}")

# Перед shutdown приложения
flush_observations()
```

## Публичный API

### Client Management
- `initialize_langfuse()` - инициализация Langfuse клиента
- `get_langfuse_client()` - получение глобального экземпляра клиента
- `flush_observations()` - отправка pending observations на сервер

### Context Managers
- `trace_context()` - создание нового trace
- `span_context()` - создание span внутри trace

### Decorators
- `@trace_llm_generation` - декоратор для LLM generation вызовов
- `@trace_operation` - декоратор для любых async операций

### Integrations
- `configure_litellm_callbacks()` - настройка LiteLLM для автоматического трейсинга

### Manual Logging
- `log_generation()` - ручное логирование LLM generation
- `log_error()` - логирование ошибок в trace

### Utilities
- `is_observability_enabled()` - проверка состояния observability
- `get_current_trace_id()` - получение ID текущего trace
- `get_current_span_id()` - получение ID текущего span

## Рефакторинг из монолита

Этот модуль является результатом рефакторинга монолитного файла `observability.py` по принципам SOLID:

**До:**
- 1 файл, 324 строки
- Смешанная ответственность
- Сложность сопровождения

**После:**
- 7 специализированных модулей
- Четкое разделение ответственности
- Легкость тестирования и расширения
- Публичный API через `__init__.py`

## Расширение

Благодаря SOLID архитектуре, модуль легко расширяется:

1. **Новые интеграции** - добавить в `integrations.py`
2. **Новые типы логирования** - добавить в `logging_helpers.py`
3. **Новые декораторы** - добавить в `decorators.py`
4. **Новые утилиты** - добавить в `utils.py`

Все изменения локализованы в одном модуле и не затрагивают остальные.
