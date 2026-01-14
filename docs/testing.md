# Тестирование

## Запуск тестов

```bash
# Все тесты (270 тестов)
make test

# Unit тесты по категориям
make test-providers    # ProviderRegistry lazy loading
make test-services     # EmbeddingManager FIFO
make test-api          # API endpoints

# С coverage
make test-coverage

# Линтинг и типы
make check             # lint + type-check
```

## Структура тестов

```
src/tests/
├── conftest.py           # Fixtures (MockLLMProvider, MockPresetsLoader, etc.)
├── unit/
│   ├── api/
│   │   ├── test_models.py      # Models API endpoints
│   │   └── test_embeddings.py  # Embeddings API endpoints
│   ├── providers/
│   │   ├── test_registry.py    # ProviderRegistry lazy loading
│   │   └── test_litellm_provider.py
│   ├── services/
│   │   └── test_embedding_manager.py  # FIFO eviction tests
│   └── shared/
│       └── errors/             # Error handling tests
└── system/                     # System tests (Redis required)
```
