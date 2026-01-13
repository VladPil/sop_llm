# =========================
# Builder Stage (CPU)
# =========================
ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS builder-cpu

# Системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Установка uv для быстрой установки зависимостей
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src/ /app/src/

ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# CPU-only build flags для llama-cpp-python
ENV CMAKE_ARGS="-DLLAMA_NATIVE=OFF -DLLAMA_AVX=ON -DLLAMA_AVX2=ON -DLLAMA_F16C=ON -DLLAMA_FMA=ON"
RUN uv pip install -e .


# =========================
# Builder Stage (GPU/CUDA)
# =========================
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04 AS builder-gpu

ARG PYTHON_VERSION=3.11

# Избежать интерактивных вопросов при установке пакетов
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Установка Python (минимум для pre-built wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-venv \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3

# Установка uv для быстрой установки зависимостей
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src/ /app/src/

ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install pre-built llama-cpp-python with CUDA 12.1 support (no compilation needed!)
# Wheels from: https://github.com/abetlen/llama-cpp-python/releases
RUN uv pip install llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# Install PyTorch with CUDA 12.1
RUN uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install the rest of dependencies
RUN uv pip install -e "."


# =========================
# Runtime Stage (CPU) - DEFAULT
# =========================
FROM python:${PYTHON_VERSION}-slim AS runtime-cpu

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder-cpu /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder-cpu /usr/local/bin /usr/local/bin
COPY src/ /app/src/

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/logs /app/models && \
    chown -R appuser:appuser /app/logs /app/models

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000 9090

ENTRYPOINT ["/usr/bin/tini", "--"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "5"]


# =========================
# Runtime Stage (GPU/CUDA)
# =========================
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS runtime-gpu

ARG PYTHON_VERSION=3.11

# Избежать интерактивных вопросов при установке пакетов
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Установка Python runtime + OpenMP (для llama.cpp)
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    python${PYTHON_VERSION} \
    python3-pip \
    curl \
    tini \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3

WORKDIR /app

# Копируем установленные пакеты из GPU builder
COPY --from=builder-gpu /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
COPY --from=builder-gpu /usr/local/bin /usr/local/bin
COPY src/ /app/src/

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/logs /app/models && \
    chown -R appuser:appuser /app/logs /app/models

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

EXPOSE 8000 9090

ENTRYPOINT ["/usr/bin/tini", "--"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "5"]
