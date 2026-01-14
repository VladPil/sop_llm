# Docker

## Структура файлов

```
.docker/
├── configs/
│   ├── .env.local       # Для Docker режима (всё в контейнерах)
│   └── .env.host        # Для host режима (backend на хосте)
├── containers/          # Dockerfiles
├── docker-compose.local.yml   # Backend + Langfuse в Docker
├── docker-compose.infra.yml   # Только Langfuse (backend на хосте)
├── docker-compose.gpu.yml     # GPU override
└── docker-compose.dev.yml     # Dev/Kubernetes режим
```

## Режимы запуска

### 1. Локальная разработка с VPN хоста (рекомендуется)

Backend на хосте использует VPN для доступа к внешним LLM API:

```bash
# Одна команда: Langfuse в Docker + backend локально
make dev

# Или по отдельности:
make up-infra      # Запустить только Langfuse
make dev-backend   # Запустить backend на хосте
make down-infra    # Остановить Langfuse
```

**Требования:**
- Redis и PostgreSQL из `sop_infrastructure` должны быть запущены
- `.env.host` настроен на `localhost:6380` (Redis) и `localhost:5433` (PostgreSQL)

### 2. Всё в Docker

```bash
# Запустить backend + Langfuse в Docker
make up

# С GPU поддержкой
make up-gpu

# Остановить
make down
```

### 3. Только backend в Docker (без Langfuse)

```bash
docker-compose -f .docker/docker-compose.local.yml up -d sop_llm
```

## Langfuse (LLM Observability)

Langfuse используется для трейсинга LLM запросов.

**Доступ:** http://localhost:3001
- Email: `admin@local.dev`
- Password: `admin123`

**API ключи для кода:**
```env
LANGFUSE_PUBLIC_KEY=pk-lf-local-dev-public-key
LANGFUSE_SECRET_KEY=sk-lf-local-dev-secret-key
```

## GPU поддержка

```bash
# Собрать образ с CUDA
make build-gpu

# Запустить с GPU
make up-gpu
```

**Требования:**
- NVIDIA GPU
- nvidia-container-toolkit
- CUDA драйверы

## Полезные команды

```bash
make ps           # Статус контейнеров
make logs         # Все логи
make logs-app     # Логи backend
make logs-infra   # Логи Langfuse
make shell        # Shell в контейнере backend
```

## Сети

- `sop_network` - внешняя сеть из `sop_infrastructure` (для Docker режима)
- Backend на хосте подключается через `localhost` порты
