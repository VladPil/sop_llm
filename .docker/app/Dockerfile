# =========================
# Builder Stage
# =========================
FROM python:3.11-slim AS builder

# Системные зависимости для сборки некоторых пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем только файлы зависимостей для лучшего кеширования
COPY requirements.txt /app/requirements.txt

# Базовые настройки среды
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# По умолчанию считаем, что устанавливаем CPU-вариант из requirements.txt
# Если нужен GPU, можно переключить на INSTALL_GPU=true при сборке
# Внимание: если вы используете GPU-режим, лучше убрать torch из requirements.txt.
ARG INSTALL_GPU=false

# Устанавливаем зависимости: сначала requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Если включен GPU-режим — переустанавливаем PyTorch с CUDA колёсами
# Примечание:
# - Удаляем torch/torchvision/torchaudio, если они уже стоят из requirements.txt
# - Затем ставим GPU-колёса из официального индекса cu121
RUN if [ "$INSTALL_GPU" = "true" ]; then \
      pip uninstall -y torch torchvision torchaudio || true; \
      pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
    fi

# =========================
# Runtime Stage
# =========================
FROM python:3.11-slim AS runtime

# Системные пакеты, полезные в рантайме (минимум)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем установленный Python и бинарники из builder
# Это гарантирует наличие всех пакетов и скриптов (включая uvicorn)
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем исходный код приложения
COPY . /app

# Системные переменные Python для корректной работы в контейнере
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Примечание: порты настраиваются через docker-compose.yml и переменные окружения
# EXPOSE используется только для документации и не влияет на реальный маппинг портов

# Используем tini как init-процесс для корректного управления сигналами
ENTRYPOINT ["/usr/bin/tini", "--"]

# Команда запуска:
# - Если у вас основной ASGI-приложение в app.main:app — оставьте как ниже.
# - При необходимости поменяйте модуль/объект приложения.
# - --timeout-graceful-shutdown для быстрого завершения
# - Порт берется из переменной окружения API_PORT
CMD uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT} --timeout-graceful-shutdown 5
