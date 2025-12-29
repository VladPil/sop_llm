# API Reference

## Базовый URL

```
http://localhost:8000
```

## Аутентификация

В текущей версии аутентификация не требуется. Для production рекомендуется добавить API key или JWT.

---

## Tasks API

### Создать задачу

Создает новую задачу генерации текста.

**Endpoint:** `POST /api/tasks`

**Request Body:**

```json
{
  "model": "string",              // Обязательно: имя модели
  "prompt": "string",             // Обязательно: промпт для генерации
  "temperature": 0.7,             // Опционально (default: 0.1)
  "max_tokens": 2048,             // Опционально (default: 2048)
  "top_p": 1.0,                   // Опционально (default: 1.0)
  "top_k": 40,                    // Опционально (default: 40)
  "frequency_penalty": 0.0,       // Опционально (default: 0.0)
  "presence_penalty": 0.0,        // Опционально (default: 0.0)
  "stop_sequences": [],           // Опционально
  "seed": null,                   // Опционально: для воспроизводимости
  "response_format": {},          // Опционально: JSON Schema
  "grammar": null,                // Опционально: GBNF grammar
  "stream": false,                // Опционально: streaming (default: false)
  "webhook_url": null,            // Опционально: callback URL
  "idempotency_key": null,        // Опционально: ключ дедупликации
  "priority": 0.0                 // Опционально: приоритет (default: 0.0)
}
```

**Response:** `201 Created`

```json
{
  "task_id": "uuid",
  "status": "pending",
  "model": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**Errors:**

- `400 Bad Request` - невалидные параметры
- `404 Not Found` - модель не найдена
- `409 Conflict` - дубликат idempotency_key

---

### Получить статус задачи

**Endpoint:** `GET /api/tasks/{task_id}`

**Response:** `200 OK`

```json
{
  "task_id": "uuid",
  "status": "pending|processing|completed|failed",
  "model": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "finished_at": "ISO8601",  // Только для completed/failed
  "result": {                // Только для completed
    "text": "string",
    "finish_reason": "stop|length|...",
    "usage": {
      "prompt_tokens": 10,
      "completion_tokens": 20,
      "total_tokens": 30
    }
  },
  "error": "string"          // Только для failed
}
```

**Errors:**

- `404 Not Found` - задача не найдена

---

### Отменить задачу

**Endpoint:** `DELETE /api/tasks/{task_id}`

**Response:** `204 No Content`

**Errors:**

- `404 Not Found` - задача не найдена
- `409 Conflict` - задача уже завершена

---

### Получить логи задачи

**Endpoint:** `GET /api/tasks/{task_id}/logs`

**Query Parameters:**

- `limit` (int, default: 100) - количество записей
- `level` (string) - фильтр по уровню (info, warning, error)

**Response:** `200 OK`

```json
[
  {
    "timestamp": "ISO8601",
    "level": "info",
    "message": "string",
    "metadata": {}
  }
]
```

---

## Models API

### Список моделей

**Endpoint:** `GET /api/models`

**Response:** `200 OK`

```json
{
  "model-name": {
    "name": "string",
    "provider": "local|openai|anthropic|...",
    "context_window": 8192,
    "max_output_tokens": 2048,
    "supports_streaming": true,
    "supports_structured_output": true,
    "loaded": true
  }
}
```

---

### Зарегистрировать модель

**Endpoint:** `POST /api/models`

**Request Body:**

```json
{
  "name": "string",
  "provider": "local|openai_compatible|anthropic|openai|custom",
  "config": {
    // Local provider
    "model_path": "/path/to/model.gguf",
    "context_window": 8192,
    "gpu_layers": -1,

    // OpenAI provider
    "api_key": "sk-...",
    "model_name": "gpt-4-turbo",
    "base_url": "https://api.openai.com/v1"
  }
}
```

**Response:** `201 Created`

```json
{
  "name": "string",
  "provider": "string",
  "status": "registered"
}
```

**Errors:**

- `400 Bad Request` - невалидная конфигурация
- `409 Conflict` - модель уже зарегистрирована

---

### Удалить модель

**Endpoint:** `DELETE /api/models/{model_name}`

**Response:** `204 No Content`

**Errors:**

- `404 Not Found` - модель не найдена

---

## Monitoring API

### Health Check

**Endpoint:** `GET /api/monitor/health`

**Response:** `200 OK`

```json
{
  "status": "healthy|degraded|unhealthy",
  "redis": true,
  "providers": {
    "model-1": true,
    "model-2": false
  },
  "gpu": {
    "available": true,
    "vram_used_percent": 45.5
  }
}
```

---

### GPU Stats

**Endpoint:** `GET /api/monitor/gpu`

**Response:** `200 OK`

```json
{
  "index": 0,
  "name": "NVIDIA RTX 4090",
  "vram": {
    "used_mb": 4096.0,
    "total_mb": 24576.0,
    "free_mb": 20480.0,
    "used_percent": 16.7
  },
  "temperature": 65,
  "utilization": 75,
  "driver_version": "545.29.06",
  "cuda_version": 12040
}
```

---

### Queue Stats

**Endpoint:** `GET /api/monitor/queue`

**Response:** `200 OK`

```json
{
  "size": 5,
  "processing": true,
  "current_task": "task-id-123"
}
```

---

## Webhooks

При указании `webhook_url` в запросе создания задачи, сервис отправит POST запрос на указанный URL при завершении задачи.

**Webhook Request:**

```http
POST {webhook_url}
Content-Type: application/json

{
  "task_id": "uuid",
  "status": "completed|failed",
  "model": "string",
  "result": {...},  // Только для completed
  "error": "string" // Только для failed
}
```

**Retry Policy:**

- Максимум 3 попытки
- Exponential backoff: 1s, 2s, 4s
- Timeout: 30s

---

## HTTP Status Codes

| Code | Значение | Описание |
|------|----------|----------|
| 200 | OK | Успешный запрос |
| 201 | Created | Ресурс создан |
| 204 | No Content | Успешное удаление |
| 400 | Bad Request | Невалидные параметры |
| 404 | Not Found | Ресурс не найден |
| 409 | Conflict | Конфликт (дубликат) |
| 422 | Unprocessable Entity | Ошибка валидации Pydantic |
| 500 | Internal Server Error | Внутренняя ошибка |

---

## Error Response Format

```json
{
  "error": "ErrorType",
  "message": "Human-readable message",
  "details": {
    "field": "value"
  }
}
```

---

## Rate Limiting

В текущей версии rate limiting не реализован. Для production рекомендуется:

- Nginx rate limiting
- Redis-based rate limiter
- API Gateway (Kong, Tyk)

---

## Idempotency

Используйте `idempotency_key` для гарантированной дедупликации запросов:

```python
response = client.post("/api/tasks", json={
    "model": "gpt-4",
    "prompt": "Test",
    "idempotency_key": "user-123-request-456"
})
```

Повторный запрос с тем же ключом вернет существующую задачу.

TTL ключа: 24 часа.
