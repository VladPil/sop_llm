# Конфигурация

## Переменные окружения

```env
# === Application ===
APP_NAME="SOP LLM Executor"
APP_ENV=production

# === Server ===
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=1  # ВАЖНО: Single worker для GPU Guard

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === GPU ===
GPU_INDEX=0
MAX_VRAM_USAGE_PERCENT=95
VRAM_RESERVE_MB=1024

# === Models Directory ===
MODELS_DIR=/models

# === API Keys ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# === Observability ===
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Описание параметров

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `SERVER_WORKERS` | Количество воркеров (1 для GPU Guard) | `1` |
| `GPU_INDEX` | Индекс используемой GPU | `0` |
| `MAX_VRAM_USAGE_PERCENT` | Максимальный % использования VRAM | `95` |
| `VRAM_RESERVE_MB` | Резерв VRAM в MB | `1024` |
