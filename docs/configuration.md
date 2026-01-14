# Конфигурация

## Файлы окружения

| Файл | Назначение |
|------|------------|
| `.docker/configs/.env.local` | Docker режим (всё в контейнерах) |
| `.docker/configs/.env.host` | Host режим (backend на хосте с VPN) |

## Основные переменные

```env
# === Application ===
APP_NAME="SOP LLM Service"
APP_ENV=local              # local | production
DEBUG=true
LOG_LEVEL=DEBUG            # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json

# === Server ===
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# === Redis (из sop_infrastructure) ===
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=0
REDIS_PASSWORD=change_me_in_production

# === LLM Providers API Keys ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
MISTRAL_API_KEY=...

# === Ollama (локальные модели) ===
OLLAMA_API_BASE=http://localhost:11434

# === Langfuse Observability ===
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-local-dev-public-key
LANGFUSE_SECRET_KEY=sk-lf-local-dev-secret-key

# === GPU ===
DEVICE=cpu                 # cpu | cuda
GPU_INDEX=0
MAX_VRAM_USAGE_PERCENT=90.0
VRAM_RESERVE_MB=512

# === LiteLLM ===
LITELLM_DEBUG=false
LITELLM_DROP_PARAMS=true
LITELLM_MAX_RETRIES=3
LITELLM_TIMEOUT=600
```

## Параметры по категориям

### Redis

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `REDIS_HOST` | Хост Redis | `localhost` |
| `REDIS_PORT` | Порт Redis | `6380` |
| `SESSION_TTL_SECONDS` | TTL сессий | `3600` |
| `IDEMPOTENCY_TTL_SECONDS` | TTL идемпотентности | `86400` |

### GPU

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `DEVICE` | Устройство (cpu/cuda) | `cpu` |
| `GPU_INDEX` | Индекс GPU | `0` |
| `MAX_VRAM_USAGE_PERCENT` | Макс. использование VRAM | `90.0` |
| `VRAM_RESERVE_MB` | Резерв VRAM в MB | `512` |

### LiteLLM

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `LITELLM_TIMEOUT` | Таймаут запроса (сек) | `600` |
| `LITELLM_MAX_RETRIES` | Количество retry | `3` |
| `LITELLM_DROP_PARAMS` | Игнорировать неподдерживаемые параметры | `true` |

## Режимы работы

### Host режим (рекомендуется для разработки)

```bash
# Использует .env.host
make dev
```

- Backend запускается на хосте
- Использует VPN хоста для внешних API
- Redis/PostgreSQL из sop_infrastructure

### Docker режим

```bash
# Использует .env.local
make up
```

- Всё в контейнерах
- Подключается к sop_network
