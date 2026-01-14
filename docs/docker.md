# Docker

## Docker Compose

```yaml
# docker-compose.yml
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
      - SERVER_WORKERS=1  # КРИТИЧНО для GPU Guard
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

## Запуск

```bash
# Собрать и запустить
docker-compose up -d

# Логи
docker-compose logs -f app

# Остановить
docker-compose down
```

## Важные замечания

- **SERVER_WORKERS=1** — критично для корректной работы GPU Guard
- Контейнер требует доступ к NVIDIA GPU через nvidia-container-toolkit
