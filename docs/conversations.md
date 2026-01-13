# Multi-turn Conversations

SOP LLM Executor поддерживает multi-turn диалоги — сохранение контекста между запросами для ведения полноценных разговоров с LLM.

## Обзор

Multi-turn conversations позволяют:
- Вести диалог с сохранением истории сообщений
- Использовать контекст предыдущих сообщений в новых запросах
- Задавать системный промпт один раз для всего диалога
- Работать с любыми моделями (локальными и удалёнными)

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      SOP LLM Executor                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   POST /conversations/     ──►  ConversationStore (Redis)   │
│   GET /conversations/{id}  ──►  conversation:{id}           │
│                                 conversation:{id}:messages   │
│                                                              │
│   POST /tasks/             ──►  TaskOrchestrator            │
│   + conversation_id        ──►  Загрузка контекста          │
│                            ──►  LiteLLM Provider            │
│                            ──►  Сохранение ответа           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Быстрый старт

### 1. Создание диалога

```bash
curl -X POST http://localhost:8000/api/v1/conversations/ \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "Ты - опытный Python разработчик",
    "model": "gpt-4-turbo"
  }'
```

Ответ:
```json
{
  "conversation_id": "conv_abc123def456",
  "model": "gpt-4-turbo",
  "system_prompt": "Ты - опытный Python разработчик",
  "message_count": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### 2. Отправка сообщения в диалог

```bash
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_abc123def456",
    "prompt": "Напиши функцию сортировки массива"
  }'
```

**Примечание:** Модель берётся из диалога (gpt-4-turbo), если не указана явно.

### 3. Продолжение диалога

```bash
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_abc123def456",
    "prompt": "Добавь документацию и unit-тесты"
  }'
```

Модель автоматически получит контекст:
1. Системный промпт: "Ты - опытный Python разработчик"
2. User: "Напиши функцию сортировки массива"
3. Assistant: [предыдущий ответ]
4. User: "Добавь документацию и unit-тесты"

## API Reference

### Conversations API

#### POST /api/v1/conversations/
Создать новый диалог.

**Request Body:**
```json
{
  "model": "string (optional)",
  "system_prompt": "string (optional)",
  "metadata": {"key": "value"}
}
```

**Response:** `201 Created`
```json
{
  "conversation_id": "conv_xxx",
  "model": "...",
  "system_prompt": "...",
  "message_count": 0,
  "created_at": "...",
  "updated_at": "..."
}
```

#### GET /api/v1/conversations/
Получить список диалогов.

**Query Parameters:**
- `limit` (int, default=100) — максимум диалогов
- `offset` (int, default=0) — смещение для пагинации

#### GET /api/v1/conversations/{conversation_id}
Получить информацию о диалоге.

**Query Parameters:**
- `include_messages` (bool, default=true) — включить историю сообщений

#### PATCH /api/v1/conversations/{conversation_id}
Обновить метаданные диалога.

**Request Body:**
```json
{
  "model": "new-model (optional)",
  "system_prompt": "new prompt (optional)",
  "metadata": {"key": "value"}
}
```

#### DELETE /api/v1/conversations/{conversation_id}
Удалить диалог и всю историю.

#### POST /api/v1/conversations/{conversation_id}/messages
Добавить сообщение в историю.

**Request Body:**
```json
{
  "role": "user | assistant | system",
  "content": "Текст сообщения"
}
```

#### GET /api/v1/conversations/{conversation_id}/messages
Получить историю сообщений.

**Query Parameters:**
- `limit` (int, optional) — последние N сообщений

#### DELETE /api/v1/conversations/{conversation_id}/messages
Очистить историю сообщений (сохранить метаданные).

### Tasks API с conversation_id

При создании задачи через POST /api/v1/tasks/ можно указать `conversation_id`:

```json
{
  "conversation_id": "conv_xxx",
  "prompt": "Сообщение пользователя",
  "model": "gpt-4-turbo (optional, берётся из диалога)",
  "save_to_conversation": true
}
```

**Поведение:**
1. Если указан `conversation_id`:
   - Загружается история сообщений из диалога
   - `prompt` добавляется как новое user сообщение
   - Ответ модели добавляется как assistant сообщение (если `save_to_conversation=true`)

2. Если указан `messages`:
   - Используется явная история вместо загрузки из диалога
   - `conversation_id` игнорируется

## Примеры использования

### Python (httpx)

```python
import httpx

BASE_URL = "http://localhost:8000/api/v1"

async def chat_example():
    async with httpx.AsyncClient() as client:
        # Создать диалог
        resp = await client.post(f"{BASE_URL}/conversations/", json={
            "system_prompt": "Ты - полезный ассистент",
            "model": "claude-3.5-sonnet"
        })
        conv = resp.json()
        conv_id = conv["conversation_id"]

        # Первое сообщение
        resp = await client.post(f"{BASE_URL}/tasks/", json={
            "conversation_id": conv_id,
            "prompt": "Привет! Как тебя зовут?"
        })
        task = resp.json()

        # Получить результат
        while True:
            resp = await client.get(f"{BASE_URL}/tasks/{task['task_id']}")
            result = resp.json()
            if result["status"] == "completed":
                print(f"Assistant: {result['result']['text']}")
                break

        # Продолжить диалог
        resp = await client.post(f"{BASE_URL}/tasks/", json={
            "conversation_id": conv_id,
            "prompt": "Расскажи о себе подробнее"
        })
        # ... получить результат

        # Получить всю историю
        resp = await client.get(f"{BASE_URL}/conversations/{conv_id}")
        history = resp.json()
        print(f"Всего сообщений: {history['message_count']}")
```

### TypeScript (fetch)

```typescript
const BASE_URL = "http://localhost:8000/api/v1";

async function chatExample() {
  // Создать диалог
  const convResp = await fetch(`${BASE_URL}/conversations/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      system_prompt: "Ты - полезный ассистент",
      model: "gpt-4-turbo"
    })
  });
  const conv = await convResp.json();

  // Отправить сообщение
  const taskResp = await fetch(`${BASE_URL}/tasks/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conv.conversation_id,
      prompt: "Привет!"
    })
  });
  const task = await taskResp.json();

  // Polling для результата
  let result;
  while (true) {
    const statusResp = await fetch(`${BASE_URL}/tasks/${task.task_id}`);
    result = await statusResp.json();
    if (result.status === "completed" || result.status === "failed") break;
    await new Promise(r => setTimeout(r, 1000));
  }

  console.log("Response:", result.result?.text);
}
```

## Конфигурация

### Redis ключи

Диалоги хранятся в Redis с префиксом `conversation:`:

```
conversation:{conv_id}           # Hash: метаданные диалога
conversation:{conv_id}:messages  # List: история сообщений
conversations:index              # Set: все conversation_id
```

### TTL и лимиты

| Параметр | Значение | Описание |
|----------|----------|----------|
| `DEFAULT_CONVERSATION_TTL` | 7 дней | TTL диалога после последней активности |
| `DEFAULT_MAX_CONVERSATION_MESSAGES` | 100 | Максимум сообщений в истории |
| `DEFAULT_CONTEXT_MESSAGES_LIMIT` | 50 | Сколько сообщений отправлять в LLM |

Константы определены в `src/core/constants.py`.

### Поведение при превышении лимитов

- **MAX_CONVERSATION_MESSAGES**: При добавлении нового сообщения старые удаляются (FIFO)
- **CONTEXT_MESSAGES_LIMIT**: В LLM отправляются только последние N сообщений
- **TTL**: Диалог автоматически удаляется через 7 дней неактивности

## Best Practices

### 1. Используйте системный промпт

Задайте системный промпт при создании диалога — он будет отправляться с каждым запросом:

```json
{
  "system_prompt": "Ты - эксперт по Python. Отвечай кратко и по делу. Приводи примеры кода."
}
```

### 2. Не злоупотребляйте длиной диалога

Длинные диалоги увеличивают:
- Количество токенов (= стоимость)
- Время ответа
- Вероятность потери фокуса моделью

Рекомендуется очищать историю при смене темы:

```bash
curl -X DELETE http://localhost:8000/api/v1/conversations/{conv_id}/messages
```

### 3. Используйте metadata для tracking

```json
{
  "metadata": {
    "user_id": "user_123",
    "session_id": "sess_456",
    "department": "support"
  }
}
```

### 4. Обрабатывайте ошибки

Диалог может не существовать (TTL, удаление). Обрабатывайте 404:

```python
resp = await client.post(f"{BASE_URL}/tasks/", json={
    "conversation_id": conv_id,
    "prompt": "..."
})
if resp.status_code == 404:
    # Создать новый диалог
    ...
```

### 5. save_to_conversation=false для preview

Если нужно получить ответ без сохранения в историю:

```json
{
  "conversation_id": "conv_xxx",
  "prompt": "Покажи preview",
  "save_to_conversation": false
}
```

## FAQ

### Q: Как использовать разные модели в одном диалоге?

Укажите `model` в запросе на создание задачи:

```json
{
  "conversation_id": "conv_xxx",
  "model": "gpt-4-turbo",
  "prompt": "Используй GPT-4 для этого сообщения"
}
```

### Q: Поддерживается ли streaming с диалогами?

Да, добавьте `"stream": true` в запрос. Контекст загружается так же.

### Q: Как импортировать историю из другой системы?

Используйте POST /conversations/{id}/messages для добавления сообщений:

```bash
# Добавить user сообщение
curl -X POST http://localhost:8000/api/v1/conversations/{conv_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"role": "user", "content": "Старое сообщение пользователя"}'

# Добавить assistant сообщение
curl -X POST http://localhost:8000/api/v1/conversations/{conv_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"role": "assistant", "content": "Старый ответ ассистента"}'
```

### Q: Работает ли с локальными моделями?

Да, диалоги работают с любыми провайдерами: OpenAI, Anthropic, Gemini, локальные GGUF модели.

### Q: Как мониторить использование диалогов?

Через endpoint `/api/v1/conversations/` можно получить список всех диалогов с metadata.
Для более детального мониторинга используйте Langfuse — каждый запрос к LLM трейсится.
