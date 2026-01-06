# Использование shared/logging модуля

Структурированное логирование с интеграцией Langfuse для sop_llm сервиса.

## Быстрый старт

### Базовая настройка

```python
from src.shared.logging import setup_logging, get_logger

# В начале приложения (app.py)
setup_logging()

# В каждом модуле
logger = get_logger(__name__)

# Использование
logger.info("Processing request", user_id="123", task_id="abc")
# Автоматически добавит trace_id из Langfuse context
```

## Основные возможности

### 1. Автоматическая интеграция с Langfuse

Каждый лог автоматически получает `trace_id` и `span_id` из Langfuse context:

```python
from src.services.observability import trace_context
from src.shared.logging import get_logger

logger = get_logger(__name__)

async with trace_context(name="llm_task", user_id="user123"):
    logger.info("Task started")  # Содержит trace_id автоматически
    # ... выполнение задачи ...
    logger.info("Task completed")  # Тот же trace_id
```

**Production JSON формат:**
```json
{
  "timestamp": "2024-01-06T12:34:56.789Z",
  "level": "INFO",
  "message": "Task started",
  "trace_id": "abc123...",
  "span_id": "xyz789...",
  "logger": "my_module",
  "function": "process_task",
  "line": 42
}
```

### 2. Логирование LLM генераций

Специализированная функция для логирования вызовов LLM:

```python
from src.shared.logging import log_llm_generation

log_llm_generation(
    provider="anthropic",
    model="claude-3.5-sonnet",
    prompt="Translate: Hello",
    response="Привет",
    params={"temperature": 0.7, "max_tokens": 100},
    usage={
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15
    },
    latency_ms=234.5,
    task_id="abc123"
)
```

**Особенности:**
- Автоматический PII sanitization в production
- Логирование только preview в production (первые 200 символов)
- Полный prompt/response в development
- Структурированный формат для анализа

### 3. Логирование ошибок провайдеров

Для логирования ошибок при работе с LLM провайдерами:

```python
from src.shared.logging import log_provider_error

try:
    result = await provider.generate(prompt)
except Exception as e:
    log_provider_error(
        provider="anthropic",
        operation="generate",
        error=e,
        context={"model": "claude-3.5-sonnet", "task_id": "abc123"},
        retry_count=1,
        will_retry=True
    )
```

### 4. Измерение времени выполнения

Context manager для автоматического логирования latency:

```python
from src.shared.logging import LogExecutionTime

with LogExecutionTime("model_loading", model="llama-7b"):
    model = await load_model("llama-7b")
    # Автоматически залогирует: "Operation completed: model_loading (1234.56ms)"
```

### 5. PII Sanitization

Автоматическое удаление личной информации:

```python
from src.shared.logging import sanitize_pii, sanitize_credentials

# Удаление PII из текста
text = "Contact: john@example.com, +1-555-123-4567"
clean_text = sanitize_pii(text)
# Результат: "Contact: ***@***.***., ***-***-****"

# Удаление credentials из словаря
data = {"user": "admin", "password": "secret", "api_key": "sk-123"}
clean_data = sanitize_credentials(data)
# Результат: {"user": "admin", "password": "***", "api_key": "***"}
```

### 6. Streaming логирование

Для логирования streaming генераций:

```python
from src.shared.logging import log_streaming_chunk

async for chunk in stream:
    log_streaming_chunk(
        provider="anthropic",
        model="claude-3.5-sonnet",
        chunk_size=len(chunk),
        total_chunks=chunk_count,
        task_id="abc123"
    )
```

## Форматы логирования

### Development формат

Human-readable с цветами и trace_id:

```
2024-01-06 12:34:56.789 | INFO     | module:function:42 | [abc12345] - Processing request
```

### Production формат

Structured JSON для Loki/Grafana:

```json
{
  "timestamp": "2024-01-06T12:34:56.789Z",
  "level": "INFO",
  "logger": "module",
  "function": "function",
  "line": 42,
  "message": "Processing request",
  "trace_id": "abc12345",
  "span_id": "xyz67890",
  "user_id": "123",
  "task_id": "abc"
}
```

## Интеграция с сторонними библиотеками

Автоматический перехват логов от:
- uvicorn
- fastapi
- litellm
- anthropic SDK
- openai SDK
- redis
- httpx

Все логи от этих библиотек автоматически получают trace_id и форматируются в едином стиле.

## Конфигурация

Настройка через переменные окружения (src/config.py):

```bash
# Окружение
APP_ENV=production  # development | production

# Уровень логирования
LOG_LEVEL=INFO  # DEBUG | INFO | WARNING | ERROR

# Langfuse (для trace_id интеграции)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=http://langfuse:3000
```

## Особенности архитектуры

### Langfuse Patcher

`patchers.py` содержит patcher который автоматически добавляет `trace_id` в каждый лог:

- Использует `langfuse_context` для получения текущего trace_id
- Fallback на "NO_TRACE" если trace недоступен
- Не прерывает логирование при ошибках

### JSON Formatter

`formatters.py` содержит custom serializer для production:

- Использует `orjson` для быстрой сериализации
- Автоматический PII sanitization в production
- Структурированный формат совместимый с Loki/Grafana

### Helper функции

`helpers.py` содержит специализированные функции для:

- Логирования LLM операций с полным контекстом
- PII sanitization (email, phone, credit cards, SSN, IP)
- Credential sanitization (password, api_key, token)
- Timing measurement с context manager

## Миграция со старого модуля

Старый модуль: `src/utils/logging`
Новый модуль: `src/shared/logging`

### Замена импортов

```python
# Старый способ
from src.utils.logging import setup_logging, get_logger

# Новый способ
from src.shared.logging import setup_logging, get_logger
```

### Дополнительные возможности

```python
# Новые функции
from src.shared.logging import (
    log_llm_generation,     # Логирование LLM вызовов
    log_provider_error,     # Логирование ошибок провайдеров
    LogExecutionTime,       # Context manager для timing
    sanitize_pii,           # PII sanitization
    sanitize_credentials,   # Credentials sanitization
)
```

## Best Practices

1. **Всегда передавайте `__name__` в get_logger():**
   ```python
   logger = get_logger(__name__)
   ```

2. **Используйте structured logging (key=value):**
   ```python
   logger.info("Processing task", task_id="abc", user_id="123")
   ```

3. **Используйте специализированные helpers для LLM:**
   ```python
   log_llm_generation(...)  # Вместо logger.info()
   ```

4. **Используйте trace_context для группировки логов:**
   ```python
   async with trace_context(name="task", user_id="123"):
       logger.info("Step 1")
       logger.info("Step 2")
       # Все логи будут иметь одинаковый trace_id
   ```

5. **Не логируйте чувствительные данные напрямую:**
   ```python
   # Плохо
   logger.info(f"User password: {password}")

   # Хорошо
   clean_data = sanitize_credentials(data)
   logger.info("User data", **clean_data)
   ```

## Troubleshooting

### Trace_id показывает "NO_TRACE"

**Причина:** Логирование происходит вне Langfuse trace context.

**Решение:**
```python
async with trace_context(name="my_operation"):
    logger.info("Now has trace_id")
```

### Логи не появляются в Grafana

**Проверьте:**
1. `APP_ENV=production` установлен
2. Формат логов JSON (`serialize=True` в config.py)
3. Loki правильно настроен на чтение stdout

### PII не sanitized в production

**Проверьте:**
1. `APP_ENV=production` установлен
2. Используете `log_llm_generation()` вместо прямого `logger.info()`
3. Вызываете `sanitize_pii()` для пользовательских данных

## Примеры использования

См. файлы проекта:
- `/home/vladislav/projects/python/sop_infrastructure/services/sop_llm/src/app.py` - настройка при старте
- `/home/vladislav/projects/python/sop_infrastructure/services/sop_llm/src/providers/litellm_provider.py` - логирование LLM вызовов
- `/home/vladislav/projects/python/sop_infrastructure/services/sop_llm/src/services/task_processor.py` - логирование с trace context
