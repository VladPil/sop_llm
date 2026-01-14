# Model Presets

Пресеты моделей хранятся в `config/model_presets/`:

```
config/model_presets/
├── cloud_models.yaml      # Cloud API модели (OpenAI, Anthropic, Gemini, Ollama)
├── embedding_models.yaml  # Embedding модели (E5, MiniLM)
└── local_models.yaml      # Локальные GPU модели (deprecated, используйте Ollama)
```

## Cloud модели (через LiteLLM)

```yaml
# cloud_models.yaml
models:
  # OpenAI
  - name: "gpt-4-turbo"
    provider: "openai"
    api_key_env_var: "OPENAI_API_KEY"
    provider_config:
      model_name: "gpt-4-turbo"
      timeout: 600
      max_retries: 3

  # Anthropic
  - name: "claude-sonnet-4"
    provider: "anthropic"
    api_key_env_var: "ANTHROPIC_API_KEY"
    provider_config:
      model_name: "claude-sonnet-4-20250514"

  # Ollama (локальные через LiteLLM)
  - name: "qwen2.5:7b"
    provider: "ollama"
    keep_alive: "30m"           # Держать модель в VRAM
    provider_config:
      model_name: "ollama/qwen2.5:7b"
      base_url: "http://localhost:11434"
```

## Ollama модели с keep_alive

Параметр `keep_alive` указывает сколько держать модель загруженной в VRAM:

```yaml
- name: "llama3.2:3b"
  provider: "ollama"
  keep_alive: "10m"    # 10 минут
  provider_config:
    model_name: "ollama/llama3.2:3b"
```

Значения: `"5m"`, `"30m"`, `"1h"`, `"0"` (выгрузить сразу), `"-1"` (держать всегда)

## Embedding модели

```yaml
# embedding_models.yaml
models:
  - name: "multilingual-e5-large"
    huggingface_repo: "intfloat/multilingual-e5-large"
    dimensions: 1024
    max_tokens: 512

  - name: "all-MiniLM-L6-v2"
    huggingface_repo: "sentence-transformers/all-MiniLM-L6-v2"
    dimensions: 384
```

## Lazy Loading

Модели загружаются автоматически при первом запросе:

```bash
# Модель создаётся автоматически
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -d '{"model": "gpt-4-turbo", "prompt": "Hello"}'
```

## API: Список доступных моделей

```bash
# Все активные провайдеры
GET /api/v1/models/

# Все пресеты из YAML
GET /api/v1/models/presets
```
