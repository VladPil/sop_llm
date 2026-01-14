"""Documentation strings для WebSocket API."""

WS_MONITOR = """
WebSocket endpoint для real-time мониторинга системы.

## Подключение

```
ws://localhost:8200/ws/monitor
```

## События сервера

| Событие | Частота | Описание |
|---------|---------|----------|
| `gpu_stats` | 2 сек | Статистика GPU и VRAM |
| `task.queued` | по событию | Задача добавлена в очередь |
| `task.started` | по событию | Задача начала выполнение |
| `task.progress` | 500 мс | Прогресс генерации (streaming) |
| `task.completed` | по событию | Задача успешно завершена |
| `task.failed` | по событию | Задача завершена с ошибкой |
| `model.loaded` | по событию | Модель загружена в VRAM |
| `model.unloaded` | по событию | Модель выгружена из VRAM |
| `log` | по событию | Лог событие |

## Команды клиента

### Подписка на события
```json
{"type": "subscribe", "events": ["gpu_stats", "task.*"]}
```

### Отписка от событий
```json
{"type": "unsubscribe", "events": ["gpu_stats"]}
```

### Фильтрация по задаче
```json
{"type": "filter_task", "task_id": "task_abc123"}
```

### Ping/Pong
```json
{"type": "ping"}
```

### Получить статистику очереди
```json
{"type": "get_queue_stats"}
```

## Формат событий

```json
{
    "type": "task.completed",
    "timestamp": 1234567890.123,
    "data": {
        "task_id": "task_abc123",
        "model": "gpt-4-turbo",
        "tokens_used": 150,
        "duration_ms": 3500
    }
}
```

## Wildcard подписки

- `*` — все события
- `task.*` — все события задач
- `model.*` — все события моделей

## Использование

```javascript
const ws = new WebSocket('ws://localhost:8200/ws/monitor');

ws.onopen = () => {
    // Подписаться только на события задач
    ws.send(JSON.stringify({
        type: 'subscribe',
        events: ['task.*']
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data.type, data.data);
};
```
"""
