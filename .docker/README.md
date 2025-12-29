# Docker Configuration

Структура Docker конфигурации следует стандартам wiki-engine.

## Структура

```
.docker/
├── dockerfiles/
│   └── backend/
│       └── Dockerfile          # Multi-stage build для Python приложения
├── configs/
│   ├── .env.local             # Локальная разработка (hot-reload)
│   ├── .env.dev               # Dev окружение (deployment)
│   └── .env.prod              # Production окружение
├── docker-compose.local.yml   # Полное окружение для разработки
├── docker-compose.infra.yml   # Только инфраструктура (Redis)
└── docker-compose.dev.yml     # Только app (stateless)
```

## Использование

### Локальная разработка (full stack)

Для разработки с hot-reload и всеми сервисами:

```bash
cd .docker
docker-compose -f docker-compose.local.yml up --build
```

Приложение будет доступно на:
- API: http://localhost:8001
- Metrics: http://localhost:9091
- Redis Commander: http://localhost:8082
- Docs: http://localhost:8001/docs

**Особенности:**
- Hot-reload включен (изменения в `src/` применяются автоматически)
- Redis Commander для управления Redis
- Debug режим включен
- Логирование в текстовом формате

### Только инфраструктура (Redis)

Для запуска приложения вне Docker (например, через PyCharm):

```bash
cd .docker
docker-compose -f docker-compose.infra.yml up
```

Затем запустите приложение локально:

```bash
# Убедитесь что Redis настроен на localhost:6381
python -m uvicorn src.main:app --reload --port 8023
```

**Для запуска Redis Commander:**

```bash
docker-compose -f docker-compose.infra.yml --profile tools up
```

### Dev deployment (stateless app)

Для deployment приложения (Redis должен быть запущен отдельно):

```bash
cd .docker
docker-compose -f docker-compose.dev.yml up --build
```

**Переменные окружения для подключения к внешнему Redis:**

```bash
export REDIS_HOST=redis.example.com
export REDIS_PORT=6379
export REDIS_PASSWORD=your_password
docker-compose -f docker-compose.dev.yml up --build
```

## Конфигурации окружений

### .env.local (локальная разработка)

- `DEBUG=true`
- `RELOAD=true`
- Hot-reload включен
- Текстовое логирование
- Минимальные ресурсы
- CPU режим (по умолчанию)
- Redis на `redis:6379`

### .env.dev (development deployment)

- `DEBUG=false`
- `RELOAD=false`
- JSON логирование
- 2 воркера
- GPU поддержка
- Оптимизированные настройки кэша

### .env.prod (production)

- `DEBUG=false`
- Строгое логирование (WARNING+)
- 4 воркера
- GPU поддержка
- Максимальный кэш
- Секреты через переменные окружения

## Dockerfile

Multi-stage build с:

1. **Builder stage:**
   - Установка зависимостей из `pyproject.toml`
   - Опциональная установка GPU версии PyTorch
   - Build аргументы: `PYTHON_VERSION`, `INSTALL_GPU`, `CUDA_VERSION`

2. **Runtime stage:**
   - Минимальный базовый образ
   - Копирование только необходимых файлов
   - Tini как init процесс
   - WORKDIR: `/app`
   - Entrypoint: `uvicorn src.main:app`

## Build аргументы

```bash
# CPU версия (по умолчанию)
docker build -f dockerfiles/backend/Dockerfile \
  --build-arg INSTALL_GPU=false \
  -t sop_llm:cpu ..

# GPU версия
docker build -f dockerfiles/backend/Dockerfile \
  --build-arg INSTALL_GPU=true \
  --build-arg CUDA_VERSION=12.1.0 \
  -t sop_llm:gpu ..
```

## Volumes

### Local development:
- `sop_llm_redis_data_local` - Redis данные
- `sop_llm_redis_logs_local` - Redis логи
- `sop_llm_models_cache_local` - HuggingFace кэш моделей
- `sop_llm_app_logs_local` - Логи приложения

### Dev deployment:
- `sop_llm_models_cache_dev` - HuggingFace кэш моделей
- `sop_llm_app_logs_dev` - Логи приложения

## Healthchecks

### Redis:
```bash
redis-cli --raw incr ping
```
Interval: 10s, Timeout: 3s, Retries: 5

### App:
```bash
curl -f http://localhost:8000/health
```
Interval: 30s, Timeout: 10s, Retries: 3, Start period: 60s

## GPU Support

Для использования GPU:

1. Установите [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. В `docker-compose.*.yml` раскомментируйте:
   ```yaml
   runtime: nvidia
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 1
             capabilities: [gpu]
   ```

3. Установите переменную окружения:
   ```bash
   export INSTALL_GPU=true
   ```

## Troubleshooting

### Приложение не запускается

Проверьте логи:
```bash
docker-compose -f docker-compose.local.yml logs -f app
```

### Redis недоступен

Проверьте статус:
```bash
docker-compose -f docker-compose.local.yml ps redis
docker-compose -f docker-compose.local.yml logs redis
```

### Проблемы с кэшем Docker

Очистка:
```bash
docker-compose -f docker-compose.local.yml down -v
docker system prune -a
```

### Модели не загружаются

Убедитесь что volume с кэшем моделей существует и доступен:
```bash
docker volume ls | grep models_cache
docker volume inspect sop_llm_models_cache_local
```

## Миграция со старой структуры

Старая структура:
- `docker-compose.yml` (корень)
- `.docker/app/Dockerfile`

Новая структура:
- `.docker/docker-compose.*.yml`
- `.docker/dockerfiles/backend/Dockerfile`

Для миграции используйте:
```bash
# Локальная разработка (аналог старого docker-compose.yml)
cd .docker
docker-compose -f docker-compose.local.yml up --build
```
