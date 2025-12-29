"""Monitoring API module.

Модуль API мониторинга.
"""

from src.modules.monitoring.api.websocket import (
    websocket_endpoint,
    websocket_task_detail_endpoint,
)

__all__ = [
    "websocket_endpoint",
    "websocket_task_detail_endpoint",
]
