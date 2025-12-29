"""WebSocket endpoints for real-time monitoring.

WebSocket endpoints для мониторинга в реальном времени.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from src.modules.monitoring.services.statistics import task_statistics


async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for receiving statistics updates in real-time.

    WebSocket endpoint для получения обновлений статистики в реальном времени.

    Args:
        websocket: WebSocket connection.

    """
    await websocket.accept()
    logger.info(f"WebSocket client connected: {websocket.client}")

    # Create queue for this subscriber
    queue = task_statistics.subscribe()

    try:
        # Send initial state
        initial_data = {
            "type": "initial",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": task_statistics.get_summary(),
        }
        await websocket.send_json(initial_data)

        # Create task for receiving messages from client
        async def receive_messages() -> None:
            """Receive and process messages from WebSocket client."""
            try:
                while True:
                    message = await websocket.receive_text()
                    # Process commands from client
                    try:
                        data = json.loads(message)
                        command = data.get("command")

                        if command == "get_stats":
                            # Send current statistics
                            response = {
                                "type": "stats",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "data": task_statistics.get_stats(),
                            }
                            await websocket.send_json(response)

                        elif command == "get_task":
                            # Get information about specific task
                            task_id = data.get("task_id")
                            task = task_statistics.get_task(task_id)
                            response = {
                                "type": "task_details",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "data": {"task_id": task_id, "task": task},
                            }
                            await websocket.send_json(response)

                        elif command == "get_errors":
                            # Get list of errors
                            limit = data.get("limit", 50)
                            errors = task_statistics.get_errors_log(limit=limit)
                            response = {
                                "type": "errors_log",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "data": {"errors": errors},
                            }
                            await websocket.send_json(response)

                        elif command == "get_active_tasks":
                            # Get active tasks
                            tasks = task_statistics.get_active_tasks()
                            response = {
                                "type": "active_tasks",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "data": {"tasks": tasks},
                            }
                            await websocket.send_json(response)

                        elif command == "ping":
                            # Respond to ping
                            await websocket.send_json(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            )

                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON received: {message}")
                    except Exception:
                        logger.exception("Error processing command")

            except WebSocketDisconnect:
                logger.info("Client disconnected")
            except Exception:
                logger.exception("Error in receive_messages")

        # Start task for receiving messages
        receive_task = asyncio.create_task(receive_messages())

        try:
            # Main loop for sending updates
            while True:
                # Get update from queue
                try:
                    update = await asyncio.wait_for(queue.get(), timeout=30.0)
                    await websocket.send_json(update)
                except TimeoutError:
                    # Send heartbeat every 30 seconds
                    heartbeat = {
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": {"stats": task_statistics.get_stats()},
                    }
                    await websocket.send_json(heartbeat)

        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {websocket.client}")
        except Exception:
            logger.exception("Error in websocket connection")
        finally:
            # Cancel receiving task
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

    finally:
        # Unsubscribe from updates
        task_statistics.unsubscribe(queue)
        logger.info(f"WebSocket connection closed: {websocket.client}")


async def websocket_task_detail_endpoint(websocket: WebSocket, task_id: str) -> None:
    """WebSocket endpoint for monitoring specific task.

    WebSocket endpoint для мониторинга конкретной задачи.

    Args:
        websocket: WebSocket connection.
        task_id: Task ID to monitor.

    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for task {task_id}: {websocket.client}")

    # Create queue for this subscriber
    queue = task_statistics.subscribe()

    try:
        # Send initial task state
        task = task_statistics.get_task(task_id)
        initial_data = {
            "type": "task_initial",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"task_id": task_id, "task": task},
        }
        await websocket.send_json(initial_data)

        # Loop for sending updates only for this task
        while True:
            try:
                update = await asyncio.wait_for(queue.get(), timeout=30.0)

                # Filter updates - send only for our task
                if update.get("data", {}).get("task_id") == task_id:
                    await websocket.send_json(update)

            except TimeoutError:
                # Send heartbeat
                task = task_statistics.get_task(task_id)
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {"task_id": task_id, "task": task},
                }
                await websocket.send_json(heartbeat)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for task {task_id}")
    except Exception:
        logger.exception("Error in websocket task detail connection")
    finally:
        # Unsubscribe from updates
        task_statistics.unsubscribe(queue)
        logger.info(f"WebSocket connection closed for task {task_id}")
