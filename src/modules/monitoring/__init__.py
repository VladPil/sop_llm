"""Monitoring and statistics module.

Модуль мониторинга и статистики.
"""

from src.modules.monitoring.api.websocket import (
    websocket_endpoint,
    websocket_task_detail_endpoint,
)
from src.modules.monitoring.services.statistics import (
    TaskStatistics,
    serialize_for_json,
    task_statistics,
)

__all__ = [
    # Services
    "TaskStatistics",
    "serialize_for_json",
    "task_statistics",
    # API
    "websocket_endpoint",
    "websocket_task_detail_endpoint",
]
