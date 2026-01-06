"""WebSocket API Routes для SOP LLM Executor.

Real-time мониторинг через WebSocket согласно ТЗ (раздел 2.5).
Подробная документация: src/docs/websocket.py
"""

import asyncio
import time
from typing import Any

import orjson
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from src.engine.gpu_guard import get_gpu_guard
from src.engine.vram_monitor import get_vram_monitor
from src.services.session_store import get_session_store
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Менеджер WebSocket соединений.

    Управляет активными соединениями и рассылкой событий.
    """

    def __init__(self) -> None:
        """Инициализировать менеджер соединений."""
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, set[str]] = {}  # connection_id -> event_types
        self.task_filters: dict[str, str | None] = {}  # connection_id -> task_id filter
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        """Принять новое соединение.

        Args:
            websocket: WebSocket соединение
            connection_id: Уникальный ID соединения
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections[connection_id] = websocket
            # По умолчанию подписка на все события
            self.subscriptions[connection_id] = {"*"}
            self.task_filters[connection_id] = None

        logger.info("WebSocket подключен", connection_id=connection_id)

    async def disconnect(self, connection_id: str) -> None:
        """Отключить соединение.

        Args:
            connection_id: ID соединения
        """
        async with self._lock:
            self.active_connections.pop(connection_id, None)
            self.subscriptions.pop(connection_id, None)
            self.task_filters.pop(connection_id, None)

        logger.info("WebSocket отключен", connection_id=connection_id)

    async def subscribe(self, connection_id: str, events: list[str]) -> None:
        """Подписаться на события.

        Args:
            connection_id: ID соединения
            events: Список типов событий
        """
        async with self._lock:
            if connection_id in self.subscriptions:
                self.subscriptions[connection_id] = set(events)

        logger.debug("WebSocket подписка обновлена", connection_id=connection_id, events=events)

    async def unsubscribe(self, connection_id: str, events: list[str]) -> None:
        """Отписаться от событий.

        Args:
            connection_id: ID соединения
            events: Список типов событий для отписки
        """
        async with self._lock:
            if connection_id in self.subscriptions:
                self.subscriptions[connection_id] -= set(events)

        logger.debug("WebSocket отписка", connection_id=connection_id, events=events)

    async def set_task_filter(self, connection_id: str, task_id: str | None) -> None:
        """Установить фильтр по task_id.

        Args:
            connection_id: ID соединения
            task_id: ID задачи для фильтрации (None = все задачи)
        """
        async with self._lock:
            self.task_filters[connection_id] = task_id

        logger.debug("WebSocket фильтр задачи", connection_id=connection_id, task_id=task_id)

    def _should_send(self, connection_id: str, event_type: str, task_id: str | None = None) -> bool:
        """Проверить нужно ли отправлять событие.

        Args:
            connection_id: ID соединения
            event_type: Тип события
            task_id: ID задачи (для task.* событий)

        Returns:
            True если событие должно быть отправлено
        """
        subscriptions = self.subscriptions.get(connection_id, set())

        # Проверка подписки на тип события
        if "*" not in subscriptions:
            # Проверить точное совпадение или wildcard (task.*)
            if event_type not in subscriptions:
                prefix = event_type.split(".")[0] + ".*"
                if prefix not in subscriptions:
                    return False

        # Проверка фильтра по task_id
        task_filter = self.task_filters.get(connection_id)
        if task_filter and task_id and task_id != task_filter:
            return False

        return True

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
        task_id: str | None = None,
    ) -> None:
        """Разослать событие всем подписанным клиентам.

        Args:
            event_type: Тип события
            data: Данные события
            task_id: ID задачи (для фильтрации)
        """
        message = orjson.dumps({
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        }).decode("utf-8")

        async with self._lock:
            connections_to_remove = []

            for connection_id, websocket in self.active_connections.items():
                if not self._should_send(connection_id, event_type, task_id):
                    continue

                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(message)
                except Exception as e:
                    logger.warning(
                        "Ошибка отправки WebSocket сообщения",
                        connection_id=connection_id,
                        error=str(e),
                    )
                    connections_to_remove.append(connection_id)

            # Удалить битые соединения
            for connection_id in connections_to_remove:
                self.active_connections.pop(connection_id, None)
                self.subscriptions.pop(connection_id, None)
                self.task_filters.pop(connection_id, None)

    async def send_personal(self, connection_id: str, message: dict[str, Any]) -> None:
        """Отправить персональное сообщение.

        Args:
            connection_id: ID соединения
            message: Сообщение для отправки
        """
        async with self._lock:
            websocket = self.active_connections.get(connection_id)
            if websocket and websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(orjson.dumps(message).decode("utf-8"))
                except Exception as e:
                    logger.warning(
                        "Ошибка отправки персонального сообщения",
                        connection_id=connection_id,
                        error=str(e),
                    )

    @property
    def connection_count(self) -> int:
        """Количество активных соединений."""
        return len(self.active_connections)


# Глобальный менеджер соединений
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Получить глобальный менеджер соединений.

    Returns:
        ConnectionManager instance
    """
    return manager


async def gpu_stats_broadcaster() -> None:
    """Фоновая задача для рассылки GPU статистики каждые 2 секунды."""
    while True:
        try:
            if manager.connection_count > 0:
                try:
                    vram_monitor = get_vram_monitor()
                    gpu_guard = get_gpu_guard()

                    gpu_info = vram_monitor.get_gpu_info()
                    vram_usage = vram_monitor.get_vram_usage()

                    data = {
                        "gpu_info": gpu_info,
                        "vram_usage": vram_usage,
                        "is_locked": gpu_guard.is_locked(),
                        "current_task_id": gpu_guard.get_current_task_id(),
                    }

                    await manager.broadcast("gpu_stats", data)
                except Exception as e:
                    # GPU недоступен - это нормально для cloud-only deployments
                    logger.debug("GPU stats недоступны", error=str(e))

            await asyncio.sleep(2)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("Ошибка в gpu_stats_broadcaster", error=str(e))
            await asyncio.sleep(2)


# Глобальная задача broadcaster
_broadcaster_task: asyncio.Task | None = None


async def start_broadcaster() -> None:
    """Запустить фоновый broadcaster."""
    global _broadcaster_task
    if _broadcaster_task is None or _broadcaster_task.done():
        _broadcaster_task = asyncio.create_task(gpu_stats_broadcaster())
        logger.info("GPU stats broadcaster запущен")


async def stop_broadcaster() -> None:
    """Остановить фоновый broadcaster."""
    global _broadcaster_task
    if _broadcaster_task and not _broadcaster_task.done():
        _broadcaster_task.cancel()
        try:
            await _broadcaster_task
        except asyncio.CancelledError:
            pass
        logger.info("GPU stats broadcaster остановлен")


@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket) -> None:
    """WebSocket endpoint для real-time мониторинга.

    Подключение:
    ```
    ws://localhost:8200/ws/monitor
    ```

    Команды клиента:
    ```json
    {"type": "subscribe", "events": ["gpu_stats", "task.*"]}
    {"type": "unsubscribe", "events": ["gpu_stats"]}
    {"type": "filter_task", "task_id": "task_abc123"}
    {"type": "ping"}
    ```

    События сервера:
    ```json
    {"type": "gpu_stats", "timestamp": 1234567890.123, "data": {...}}
    {"type": "task.queued", "timestamp": 1234567890.123, "data": {"task_id": "..."}}
    {"type": "task.completed", "timestamp": 1234567890.123, "data": {...}}
    {"type": "pong", "timestamp": 1234567890.123}
    ```
    """
    import uuid
    connection_id = str(uuid.uuid4())

    await manager.connect(websocket, connection_id)

    # Запустить broadcaster если еще не запущен
    await start_broadcaster()

    try:
        # Отправить приветственное сообщение
        await manager.send_personal(connection_id, {
            "type": "connected",
            "connection_id": connection_id,
            "message": "Подключено к SOP LLM Monitor",
            "available_events": [
                "gpu_stats",
                "task.queued",
                "task.started",
                "task.progress",
                "task.completed",
                "task.failed",
                "model.loaded",
                "model.unloaded",
                "log",
            ],
        })

        # Слушать команды от клиента
        while True:
            try:
                data = await websocket.receive_text()
                message = orjson.loads(data)

                msg_type = message.get("type")

                if msg_type == "subscribe":
                    events = message.get("events", ["*"])
                    await manager.subscribe(connection_id, events)
                    await manager.send_personal(connection_id, {
                        "type": "subscribed",
                        "events": events,
                    })

                elif msg_type == "unsubscribe":
                    events = message.get("events", [])
                    await manager.unsubscribe(connection_id, events)
                    await manager.send_personal(connection_id, {
                        "type": "unsubscribed",
                        "events": events,
                    })

                elif msg_type == "filter_task":
                    task_id = message.get("task_id")
                    await manager.set_task_filter(connection_id, task_id)
                    await manager.send_personal(connection_id, {
                        "type": "filter_set",
                        "task_id": task_id,
                    })

                elif msg_type == "ping":
                    await manager.send_personal(connection_id, {
                        "type": "pong",
                        "timestamp": time.time(),
                    })

                elif msg_type == "get_queue_stats":
                    session_store = get_session_store()
                    stats = await session_store.get_stats()
                    await manager.send_personal(connection_id, {
                        "type": "queue_stats",
                        "data": stats,
                    })

                else:
                    await manager.send_personal(connection_id, {
                        "type": "error",
                        "message": f"Неизвестная команда: {msg_type}",
                    })

            except orjson.JSONDecodeError:
                await manager.send_personal(connection_id, {
                    "type": "error",
                    "message": "Невалидный JSON",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket клиент отключился", connection_id=connection_id)
    except Exception as e:
        logger.exception("Ошибка WebSocket", connection_id=connection_id, error=str(e))
    finally:
        await manager.disconnect(connection_id)


# === Event Broadcasting Functions ===
# Эти функции вызываются из других частей приложения для рассылки событий


async def broadcast_task_queued(task_id: str, model: str, priority: float) -> None:
    """Разослать событие о добавлении задачи в очередь.

    Args:
        task_id: ID задачи
        model: Название модели
        priority: Приоритет задачи
    """
    await manager.broadcast(
        "task.queued",
        {"task_id": task_id, "model": model, "priority": priority},
        task_id=task_id,
    )


async def broadcast_task_started(task_id: str, model: str) -> None:
    """Разослать событие о начале выполнения задачи.

    Args:
        task_id: ID задачи
        model: Название модели
    """
    await manager.broadcast(
        "task.started",
        {"task_id": task_id, "model": model},
        task_id=task_id,
    )


async def broadcast_task_progress(
    task_id: str,
    tokens_generated: int,
    partial_text: str | None = None,
) -> None:
    """Разослать событие о прогрессе генерации.

    Args:
        task_id: ID задачи
        tokens_generated: Количество сгенерированных токенов
        partial_text: Частичный текст (для streaming)
    """
    data: dict[str, Any] = {
        "task_id": task_id,
        "tokens_generated": tokens_generated,
    }
    if partial_text is not None:
        data["partial_text"] = partial_text

    await manager.broadcast("task.progress", data, task_id=task_id)


async def broadcast_task_completed(
    task_id: str,
    model: str,
    tokens_used: int,
    duration_ms: float,
) -> None:
    """Разослать событие о завершении задачи.

    Args:
        task_id: ID задачи
        model: Название модели
        tokens_used: Использовано токенов
        duration_ms: Время выполнения в мс
    """
    await manager.broadcast(
        "task.completed",
        {
            "task_id": task_id,
            "model": model,
            "tokens_used": tokens_used,
            "duration_ms": duration_ms,
        },
        task_id=task_id,
    )


async def broadcast_task_failed(task_id: str, model: str, error: str) -> None:
    """Разослать событие об ошибке задачи.

    Args:
        task_id: ID задачи
        model: Название модели
        error: Сообщение об ошибке
    """
    await manager.broadcast(
        "task.failed",
        {"task_id": task_id, "model": model, "error": error},
        task_id=task_id,
    )


async def broadcast_model_loaded(model_name: str, vram_used_mb: int) -> None:
    """Разослать событие о загрузке модели.

    Args:
        model_name: Название модели
        vram_used_mb: Использовано VRAM в MB
    """
    await manager.broadcast(
        "model.loaded",
        {"model_name": model_name, "vram_used_mb": vram_used_mb},
    )


async def broadcast_model_unloaded(model_name: str, vram_freed_mb: int) -> None:
    """Разослать событие о выгрузке модели.

    Args:
        model_name: Название модели
        vram_freed_mb: Освобождено VRAM в MB
    """
    await manager.broadcast(
        "model.unloaded",
        {"model_name": model_name, "vram_freed_mb": vram_freed_mb},
    )


async def broadcast_log(level: str, message: str, task_id: str | None = None) -> None:
    """Разослать лог событие.

    Args:
        level: Уровень лога (INFO, WARNING, ERROR, etc.)
        message: Сообщение
        task_id: ID задачи (опционально)
    """
    data: dict[str, Any] = {"level": level, "message": message}
    if task_id:
        data["task_id"] = task_id

    await manager.broadcast("log", data, task_id=task_id)
