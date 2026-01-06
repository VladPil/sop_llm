# =========================
# Builder Stage
# =========================
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS builder

# Build arguments
ARG INSTALL_GPU=false
ARG CUDA_VERSION=12.1.0
ARG INSTALL_DEV=false

# Системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем файлы зависимостей и код
COPY pyproject.toml /app/pyproject.toml
COPY src/ /app/src/

# Базовые настройки Python
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Устанавливаем setuptools и wheel для работы с pyproject.toml
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Устанавливаем зависимости из pyproject.toml
# Извлекаем зависимости и устанавливаем их
# CMAKE_ARGS для избежания -march=native (segfault в Docker)
ENV CMAKE_ARGS="-DLLAMA_NATIVE=OFF -DLLAMA_AVX=ON -DLLAMA_AVX2=ON -DLLAMA_F16C=ON -DLLAMA_FMA=ON"
RUN pip install --no-cache-dir -e .

# Устанавливаем dev-зависимости для локального окружения
RUN if [ "$INSTALL_DEV" = "true" ]; then \
      pip install --no-cache-dir -e ".[dev]"; \
    fi

# Если включен GPU-режим, переустанавливаем PyTorch с CUDA
RUN if [ "$INSTALL_GPU" = "true" ]; then \
      pip uninstall -y torch torchvision torchaudio || true; \
      pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121; \
    fi

# =========================
# Runtime Stage
# =========================
FROM python:${PYTHON_VERSION}-slim AS runtime

# Системные пакеты для рантайма
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем установленные Python пакеты из builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем исходный код приложения
COPY src/ /app/src/

# Создаем non-root пользователя
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app/logs

# Переключаемся на non-root пользователя
USER appuser

# Системные переменные Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Порты документации (фактический маппинг в docker-compose)
EXPOSE 8000 9090

# Используем tini как init-процесс
ENTRYPOINT ["/usr/bin/tini", "--"]

# Healthcheck (внутри контейнера порт 8000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Команда запуска
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "5"]
