# Core Module - Ядро SOP LLM Executor

Модуль `src/core` содержит базовые компоненты системы: конфигурацию, enum'ы, константы.

## 📁 Структура

```
src/core/
├── __init__.py          # Публичный API модуля
├── config.py            # Настройки приложения (Settings классы)
├── enums.py             # Все enum'ы проекта
├── constants.py         # Все константы и магические значения
├── model_defaults.py    # Дефолты для LLM моделей
├── dependencies.py      # FastAPI зависимости (DI)
└── README.md            # Эта документация
```

## 🔧 Компоненты

### 1. Enums (`enums.py`)

Все enum'ы проекта собраны в одном месте для централизованного управления.

**Доступные enum'ы:**

- **`TaskStatus`** - Статус задачи генерации
  - `PENDING` - Ожидает обработки
  - `PROCESSING` - В процессе выполнения
  - `COMPLETED` - Успешно завершена
  - `FAILED` - Завершена с ошибкой

- **`FinishReason`** - Причина завершения генерации
  - `STOP` - Нормальное завершение (stop sequence или EOS)
  - `LENGTH` - Достигнут max_tokens
  - `ERROR` - Ошибка во время генерации

- **`ProviderType`** - Тип провайдера LLM
  - `OLLAMA` - Локальные модели через Ollama
  - `OPENAI` - OpenAI API
  - `OPENAI_COMPATIBLE` - OpenAI-совместимые API
  - `ANTHROPIC` - Anthropic Claude API
  - `LITELLM` - LiteLLM универсальный провайдер
  - `EMBEDDING` - Embedding провайдер
  - `CUSTOM` - Кастомный провайдер

- **`HealthStatus`** - Статус здоровья сервиса
  - `HEALTHY` - Все компоненты работают
  - `DEGRADED` - Есть проблемы, но сервис работает
  - `UNHEALTHY` - Критические проблемы

- **`ModelType`** - Тип модели для специфичной обработки промптов
  - `LLAMA`, `MISTRAL`, `QWEN`, `PHI`, `GEMMA`, `GENERIC`

- **`LogLevel`** - Уровень логирования
  - `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

- **`AppEnvironment`** - Окружение приложения
  - `LOCAL`, `DEVELOPMENT`, `STAGING`, `PRODUCTION`

**Пример использования:**

```python
from src.core import TaskStatus, FinishReason, ProviderType

# В коде используйте enum значения, а не строки
if session["status"] == TaskStatus.COMPLETED:
    print("Task is done!")

# Получить строковое значение
status_str = TaskStatus.COMPLETED.value  # "completed"

# Сравнение с строкой (работает благодаря str mixin)
if status == "completed":  # ❌ Плохо
if status == TaskStatus.COMPLETED:  # ✅ Хорошо
```

### 2. Constants (`constants.py`)

Все магические числа и строки вынесены в константы.

**Категории констант:**

- **API**: `DEFAULT_API_PREFIX`, `DEFAULT_DOCS_URL`, etc.
- **Timeouts**: `DEFAULT_HTTP_TIMEOUT`, `DEFAULT_WEBHOOK_TIMEOUT`, etc.
- **Retries**: `DEFAULT_HTTP_MAX_RETRIES`, `DEFAULT_WEBHOOK_MAX_RETRIES`, etc.
- **TTL**: `DEFAULT_SESSION_TTL`, `DEFAULT_IDEMPOTENCY_TTL`
- **LLM**: `DEFAULT_CONTEXT_WINDOW`, `DEFAULT_MAX_TOKENS`
- **GPU**: `DEFAULT_GPU_INDEX`, `DEFAULT_MAX_VRAM_USAGE_PERCENT`, etc.
- **Models**: `DEFAULT_EMBEDDING_MODEL`, `DEFAULT_MODELS_DIR`
- **Redis**: `REDIS_SESSION_PREFIX`, `REDIS_QUEUE_KEY`, etc.
- **Formats**: `ISO_8601_FORMAT`

**Пример использования:**

```python
from src.core import DEFAULT_SESSION_TTL, REDIS_SESSION_PREFIX

# Вместо хардкода
await redis.setex(f"session:{task_id}", 3600, data)  # ❌ Плохо

# Используйте константы
await redis.setex(
    f"{REDIS_SESSION_PREFIX}{task_id}",
    DEFAULT_SESSION_TTL,
    data
)  # ✅ Хорошо
```

### 3. Config (`config.py`)

Настройки приложения разбиты на логические классы:

- **`ApplicationSettings`** - Основные настройки приложения
- **`ServerSettings`** - Настройки сервера
- **`RedisSettings`** - Настройки Redis
- **`KafkaSettings`** - Настройки Kafka
- **`SessionSettings`** - Настройки сессий
- **`WebhookSettings`** - Настройки webhook'ов
- **`HttpSettings`** - Настройки HTTP клиента
- **`ModelSettings`** - Настройки моделей
- **`GPUSettings`** - Настройки GPU
- **`LLMProviderKeys`** - API ключи провайдеров
- **`LiteLLMSettings`** - Настройки LiteLLM
- **`LangfuseSettings`** - Настройки Langfuse
- **`JSONFixingSettings`** - Настройки JSON fixing
- **`CORSSettings`** - Настройки CORS

**⚠️ Важно:** Все значения в Settings **БЕЗ** default значений и должны быть заданы в `.env` файлах или переменных окружения!

**Пример использования:**

```python
from src.core import settings

# Доступ к настройкам
print(settings.app_name)
print(settings.redis_host)
print(settings.litellm_debug)
```

## 🎯 Принципы

### 1. Нет хардкода

❌ **Плохо:**
```python
if status == "completed":
    await redis.setex(f"session:{id}", 3600, data)
```

✅ **Хорошо:**
```python
from src.core import TaskStatus, REDIS_SESSION_PREFIX, DEFAULT_SESSION_TTL

if status == TaskStatus.COMPLETED:
    await redis.setex(f"{REDIS_SESSION_PREFIX}{id}", DEFAULT_SESSION_TTL, data)
```

### 2. Централизованное управление

Все enum'ы и константы в одном месте (`src/core/`):
- Легко найти и изменить
- Избежание дублирования
- Типобезопасность (для enum'ов)

### 3. Обязательная конфигурация

Settings **БЕЗ** default значений - все должно быть явно задано в `.env`:
- Прозрачность конфигурации
- Защита от забытых настроек
- Легкость отладки

## 📝 Миграция существующего кода

Если вы видите хардкодные значения в коде:

1. Проверьте, есть ли уже соответствующий enum/константа в `src/core/`
2. Если нет - добавьте в `enums.py` или `constants.py`
3. Обновите `__init__.py` для экспорта
4. Замените хардкод на импорт из `src.core`

Пример:

```python
# Было:
if provider_type == "ollama":
    ...

# Стало:
from src.core import ProviderType

if provider_type == ProviderType.OLLAMA:
    ...
```

## 🔍 Где используется

Импортируйте через `src.core`:

```python
# Импорт enum'ов
from src.core import TaskStatus, FinishReason, ProviderType

# Импорт констант
from src.core import DEFAULT_SESSION_TTL, REDIS_SESSION_PREFIX

# Импорт настроек
from src.core import settings
```

Используется в:
- `src/api/schemas/` - Pydantic схемы
- `src/api/routes/` - FastAPI эндпоинты
- `src/services/` - Бизнес-логика
- `src/providers/` - LLM провайдеры
- `src/tests/` - Тесты
