# Deployment Guide

## Требования

### Минимальные

- **CPU:** 4 cores
- **RAM:** 8 GB
- **Disk:** 20 GB
- **OS:** Linux (Ubuntu 22.04+, Debian 12+)
- **Python:** 3.11+
- **Redis:** 7.0+

### Рекомендуемые (с локальными моделями)

- **CPU:** 8+ cores
- **RAM:** 16 GB
- **GPU:** NVIDIA (8+ GB VRAM)
- **CUDA:** 12.0+
- **Disk:** 100 GB SSD

---

## Development

### Локальный запуск

```bash
# 1. Клонировать репозиторий
git clone git@github.com:VladPil/sop_llm.git
cd sop_llm

# 2. Создать venv
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Установить зависимости
pip install -e ".[dev]"

# 4. Запустить Redis
docker run -d -p 6379:6379 redis:7-alpine

# 5. Настроить .env
cat > .env <<EOF
APP_ENV=development
DEBUG=true
REDIS_URL=redis://localhost:6379/0
SERVER_PORT=8000
EOF

# 6. Запустить сервис
python main.py
```

---

## Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python зависимости
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Код приложения
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/api/monitor/health || exit 1

# ВАЖНО: Single worker для GPU Guard
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### Build & Run

```bash
# Build
docker build -t sop-llm:latest .

# Run (без GPU)
docker run -d \
  -p 8000:8000 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  --name sop-llm \
  sop-llm:latest

# Run (с GPU)
docker run -d \
  --gpus all \
  -p 8000:8000 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e GPU_INDEX=0 \
  -v /models:/models:ro \
  --name sop-llm \
  sop-llm:latest
```

---

## Docker Compose

### docker-compose.yml

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: sop-llm-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: sop-llm-app
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - REDIS_URL=redis://redis:6379/0
      - SERVER_WORKERS=1
      - LOG_LEVEL=info
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/monitor/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    # Для локальных моделей
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - /path/to/models:/models:ro

volumes:
  redis-data:
```

### Запуск

```bash
# Start
docker-compose up -d

# Logs
docker-compose logs -f app

# Stop
docker-compose down

# Restart
docker-compose restart app
```

---

## Production

### Systemd Service

```ini
# /etc/systemd/system/sop-llm.service
[Unit]
Description=SOP LLM Executor
After=network.target redis.service

[Service]
Type=simple
User=sop-llm
Group=sop-llm
WorkingDirectory=/opt/sop-llm
Environment="PATH=/opt/sop-llm/.venv/bin"
EnvironmentFile=/opt/sop-llm/.env
ExecStart=/opt/sop-llm/.venv/bin/python main.py
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Установка:**

```bash
# Создать пользователя
sudo useradd -r -s /bin/false sop-llm

# Установить приложение
sudo mkdir -p /opt/sop-llm
sudo cp -r . /opt/sop-llm/
sudo chown -R sop-llm:sop-llm /opt/sop-llm

# Установить зависимости
sudo -u sop-llm python3.11 -m venv /opt/sop-llm/.venv
sudo -u sop-llm /opt/sop-llm/.venv/bin/pip install -e /opt/sop-llm

# Настроить .env
sudo vim /opt/sop-llm/.env

# Включить и запустить
sudo systemctl daemon-reload
sudo systemctl enable sop-llm
sudo systemctl start sop-llm

# Проверить статус
sudo systemctl status sop-llm
sudo journalctl -u sop-llm -f
```

---

### Nginx Reverse Proxy

```nginx
upstream sop_llm {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name llm.example.com;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://sop_llm;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts для долгих генераций
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # Body size для больших промптов
        client_max_body_size 10M;
    }

    # Health check endpoint (без rate limit)
    location /api/monitor/health {
        proxy_pass http://sop_llm;
        limit_req off;
    }
}
```

---

### SSL с Let's Encrypt

```bash
# Установить certbot
sudo apt-get install certbot python3-certbot-nginx

# Получить сертификат
sudo certbot --nginx -d llm.example.com

# Auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

---

## Мониторинг

### Prometheus

**prometheus.yml:**

```yaml
scrape_configs:
  - job_name: 'sop-llm'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Grafana Dashboard

Ключевые метрики:

- Request rate (req/s)
- Request latency (p50, p95, p99)
- Error rate (%)
- GPU VRAM usage (%)
- GPU temperature (°C)
- Queue size
- Task processing time

---

## Backup & Recovery

### Redis Backup

```bash
# RDB snapshot
redis-cli BGSAVE

# AOF persistence (в redis.conf)
appendonly yes
appendfsync everysec

# Копирование backup
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

### Application Backup

```bash
# Конфигурация
tar -czf sop-llm-config-$(date +%Y%m%d).tar.gz \
    /opt/sop-llm/.env \
    /opt/sop-llm/config/

# Логи (опционально)
tar -czf sop-llm-logs-$(date +%Y%m%d).tar.gz \
    /var/log/sop-llm/
```

---

## Scaling

### Horizontal Scaling (без GPU)

Для remote providers (OpenAI, Anthropic):

```yaml
# docker-compose.yml
services:
  app:
    deploy:
      replicas: 3  # 3 инстанса
```

⚠️ **ВАЖНО:** GPU Guard требует Single Worker архитектуры для локальных моделей.

### Load Balancing

```nginx
upstream sop_llm {
    least_conn;
    server app1:8000;
    server app2:8000;
    server app3:8000;
}
```

---

## Troubleshooting

### Проверка здоровья

```bash
# Health check
curl http://localhost:8000/api/monitor/health

# GPU stats
curl http://localhost:8000/api/monitor/gpu

# Redis connection
redis-cli -u $REDIS_URL ping
```

### Логи

```bash
# Docker
docker logs sop-llm-app --tail 100 -f

# Systemd
journalctl -u sop-llm -n 100 -f

# Файлы (если настроено)
tail -f /var/log/sop-llm/app.log
```

### Частые проблемы

**1. CUDA out of memory**
```bash
# Уменьшить gpu_layers или увеличить vram_reserve_mb
export LOCAL_MODEL_GPU_LAYERS=20
export VRAM_RESERVE_MB=2048
```

**2. Redis connection timeout**
```bash
# Увеличить pool size и timeout
export REDIS_POOL_SIZE=20
export REDIS_TIMEOUT=10
```

**3. Task stuck in processing**
```bash
# Проверить worker
curl http://localhost:8000/api/monitor/queue

# Рестарт сервиса
systemctl restart sop-llm
```

---

## Security Checklist

- [ ] Настроить firewall (ufw/iptables)
- [ ] Использовать HTTPS (SSL/TLS)
- [ ] Ограничить доступ к Redis (bind + requirepass)
- [ ] Настроить rate limiting
- [ ] Регулярные обновления зависимостей
- [ ] Мониторинг логов безопасности
- [ ] Backup конфигурации
- [ ] Изолировать сервис (Docker/VM)
