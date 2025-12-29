# Quick Start Guide

Быстрый старт для работы с новой Docker конфигурацией.

## Сценарий 1: Локальная разработка (Full Stack)

Запуск полного окружения с Redis, приложением и hot-reload:

```bash
cd .docker
docker-compose -f docker-compose.local.yml up --build
```

После запуска доступны:

- **API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health
- **Metrics**: http://localhost:9091
- **Redis Commander**: http://localhost:8082

**Hot-reload включен** - изменения в `src/` применяются автоматически.

### Остановка

```bash
# Ctrl+C в терминале, затем:
docker-compose -f docker-compose.local.yml down
```

### Полная очистка (с volumes)

```bash
docker-compose -f docker-compose.local.yml down -v
```

---

## Сценарий 2: Только Redis (App вне Docker)

Запуск только инфраструктуры для работы с приложением через IDE:

```bash
cd .docker
docker-compose -f docker-compose.infra.yml up
```

В другом терминале запустите приложение:

```bash
# Из корня проекта
python -m uvicorn src.main:app --reload --port 8023
```

**Преимущества:**
- Быстрая перезагрузка (без пересборки Docker)
- Удобная отладка через IDE
- Доступ к локальным файлам и переменным

### С Redis Commander

```bash
docker-compose -f docker-compose.infra.yml --profile tools up
```

---

## Сценарий 3: Deployment (Stateless App)

Запуск только приложения (Redis должен быть запущен отдельно):

```bash
cd .docker

# Установите переменные для подключения к Redis
export REDIS_HOST=redis.example.com
export REDIS_PORT=6379
export REDIS_PASSWORD=your_password

docker-compose -f docker-compose.dev.yml up --build
```

**Используется для:**
- Dev/Stage окружений
- Deployment в Kubernetes/Docker Swarm
- Когда Redis запущен как отдельный сервис

---

## Переменные окружения

### Основные переменные

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `APP_PORT` | Внешний порт API | 8001 |
| `API_PORT` | Внутренний порт контейнера | 8000 |
| `REDIS_PORT` | Порт Redis | 6381 (local), 6379 (dev/prod) |
| `INSTALL_GPU` | Включить GPU поддержку | false (local), true (dev/prod) |
| `DEVICE` | Устройство для моделей | cpu (local), cuda (dev/prod) |

### Настройка переменных

Через .env файл:

```bash
# .docker/configs/.env.local
APP_PORT=8001
INSTALL_GPU=false
DEVICE=cpu
```

Через export:

```bash
export APP_PORT=8080
export INSTALL_GPU=true
docker-compose -f docker-compose.local.yml up
```

---

## Частые задачи

### Пересборка образа

```bash
cd .docker
docker-compose -f docker-compose.local.yml build --no-cache
```

### Просмотр логов

```bash
# Все сервисы
docker-compose -f docker-compose.local.yml logs -f

# Только приложение
docker-compose -f docker-compose.local.yml logs -f app

# Только Redis
docker-compose -f docker-compose.local.yml logs -f redis
```

### Выполнение команд в контейнере

```bash
# Bash в контейнере app
docker-compose -f docker-compose.local.yml exec app bash

# Python REPL
docker-compose -f docker-compose.local.yml exec app python

# Pytest
docker-compose -f docker-compose.local.yml exec app pytest
```

### Проверка статуса

```bash
docker-compose -f docker-compose.local.yml ps
```

### Перезапуск сервиса

```bash
# Только app
docker-compose -f docker-compose.local.yml restart app

# Все сервисы
docker-compose -f docker-compose.local.yml restart
```

---

## GPU Support

### Требования

1. Установите [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. Проверьте:
```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Включение GPU

В `docker-compose.local.yml` раскомментируйте:

```yaml
app:
  runtime: nvidia  # Раскомментировать
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia  # Раскомментировать
            count: 1
            capabilities: [gpu]
```

В `.env.local` установите:

```bash
INSTALL_GPU=true
DEVICE=cuda
```

Пересоберите:

```bash
docker-compose -f docker-compose.local.yml up --build
```

---

## Troubleshooting

### Порт уже занят

```bash
# Измените порт в .env файле
echo "APP_PORT=8080" >> configs/.env.local
docker-compose -f docker-compose.local.yml up
```

### Redis недоступен

```bash
# Проверьте статус
docker-compose -f docker-compose.local.yml ps redis

# Проверьте логи
docker-compose -f docker-compose.local.yml logs redis

# Перезапустите
docker-compose -f docker-compose.local.yml restart redis
```

### Модели не загружаются

```bash
# Проверьте volume
docker volume inspect sop_llm_models_cache_local

# Очистите кэш и переустановите
docker-compose -f docker-compose.local.yml down -v
docker-compose -f docker-compose.local.yml up --build
```

### Ошибка "no space left on device"

```bash
# Очистите неиспользуемые образы и volumes
docker system prune -a --volumes
```

### Приложение зависает при старте

Проверьте:

1. Достаточно памяти (минимум 8GB для моделей)
2. Redis запущен и доступен
3. Нет конфликтов портов
4. HuggingFace токен установлен (если требуется)

```bash
# Увеличьте start_period в healthcheck
# В docker-compose.local.yml:
healthcheck:
  start_period: 120s  # Было 60s
```

---

## Следующие шаги

1. **Разработка**: Используйте `docker-compose.local.yml`
2. **Тестирование**: Запустите тесты в контейнере
3. **Deployment**: Используйте `docker-compose.dev.yml` с внешним Redis
4. **Production**: Используйте `configs/.env.prod` и secrets management

---

## Полезные ссылки

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Documentation](https://redis.io/documentation)
