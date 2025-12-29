# Тесты интеграции sop_llm

## Конфигурация базового URL

Базовый URL для API sop_llm настраивается через переменную окружения `SOP_LLM_BASE_URL`.

### Запуск тестов

#### Внутри Docker контейнера (по умолчанию)

```bash
docker compose exec app python -m pytest tests/test_sop_integration.py -v
```

Используется URL: `http://localhost:8023/api/v1` (внутренний порт контейнера)

#### Снаружи контейнера (с хоста)

```bash
# Установить URL для внешнего доступа
export SOP_LLM_BASE_URL="http://localhost:8001/api/v1"

# Запустить тесты
pytest tests/test_sop_integration.py -v
```

#### Пользовательский URL

```bash
# Для любого другого URL (например, удаленный сервер)
export SOP_LLM_BASE_URL="http://remote-server:8080/api/v1"
pytest tests/test_sop_integration.py -v
```

## Описание тестов

### test_create_task_sop_format
Проверяет совместимость с форматом запросов из проекта `sop`.
Использует точно такой же payload, как в `sop/app/shared/sop_llm_client.py`.

### test_create_task_with_json_format
Тестирует создание задачи с `expected_format="json"`.
Проверяет работу JSON Fixer для автоматического исправления невалидного JSON.

### test_create_task_with_system_prompt
Проверяет передачу `system_prompt` в параметрах задачи.

### test_embedding_task
Тестирует генерацию embeddings для текста.

### test_task_detail_contains_processing_details
Проверяет, что API возвращает детали обработки (`processing_details`),
необходимые для Web UI.

### test_cache_functionality
Проверяет работу кэша - второй идентичный запрос должен вернуться из кэша.

## Требования

- Сервис `sop_llm` должен быть запущен и доступен
- Redis должен быть запущен (для кэша)
- Модели должны быть загружены

## Запуск всех тестов

```bash
# Все тесты интеграции с sop
docker compose exec app python -m pytest tests/test_sop_integration.py -v -s

# Конкретный тест
docker compose exec app python -m pytest tests/test_sop_integration.py::test_create_task_sop_format -v -s

# С coverage
docker compose exec app python -m pytest tests/test_sop_integration.py --cov=app --cov-report=html
```

## Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `SOP_LLM_BASE_URL` | Базовый URL для API | `http://localhost:8023/api/v1` |

## Проект sop

Эти тесты проверяют совместимость с проектом `sop`, который использует `sop_llm` через HTTP API.

Конфигурация в проекте `sop`:
```python
# sop/app/config.py
sop_llm_base_url: str = Field(
    default="http://localhost:8001/api/v1",
    validation_alias="SOP_LLM_BASE_URL"
)
```

**Важно**: Проект `sop` использует порт `8001` (внешний порт Docker), а тесты внутри контейнера используют `8023` (внутренний порт).
