# Model Presets

Пресеты моделей хранятся в `config/model_presets/`:

```
config/model_presets/
├── cloud_models.yaml      # Cloud API + Ollama модели
└── embedding_models.yaml  # Embedding модели (E5, MiniLM)
```

## Cloud пресет

```yaml
models:
  - name: "claude-sonnet-4"
    provider: "anthropic"
    api_key_env_var: "ANTHROPIC_API_KEY"
    provider_config:
      model_name: "claude-sonnet-4-20250514"
      timeout: 600
      max_retries: 3
```

## Ollama пресет с keep_alive

```yaml
models:
  - name: "qwen2.5:7b"
    provider: "ollama"
    keep_alive: "30m"  # Держать модель в VRAM 30 минут
    provider_config:
      model_name: "ollama/qwen2.5:7b"
      base_url: "http://localhost:11434"
      timeout: 120
```

## Embedding пресет

```yaml
models:
  - name: "multilingual-e5-large"
    huggingface_repo: "intfloat/multilingual-e5-large"
    dimensions: 1024
```
