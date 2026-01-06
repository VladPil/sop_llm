"""Task Management Module - модульная архитектура для задач.

Этот модуль заменяет монолитный TaskProcessor на SOLID-compliant архитектуру:

- TaskExecutor: выполнение LLM генерации
- WebhookService: отправка HTTP callbacks
- TaskStateManager: управление состоянием задач
- TaskOrchestrator: координация компонентов

Архитектура:
    ┌─────────────────────┐
    │  TaskOrchestrator   │  (координатор)
    └──────────┬──────────┘
               │
       ┌───────┼───────┬─────────────┐
       │       │       │             │
       ▼       ▼       ▼             ▼
    Executor Webhook State    SessionStore
                Manager

Example:
    >>> from src.services.task import get_task_orchestrator
    >>> orchestrator = get_task_orchestrator()
    >>> task_id = await orchestrator.submit_task(model, prompt, params)

Public API:
    - TaskOrchestrator (главный класс)
    - get_task_orchestrator() (singleton)
    - create_task_orchestrator() (фабрика)

Internal components (не экспортируются):
    - TaskExecutor
    - WebhookService
    - TaskStateManager

See Also:
    - DOC-02-09: Стандарты документирования
    - SOLID principles: Single Responsibility, Dependency Inversion

"""

from src.services.task.task_orchestrator import (
    TaskOrchestrator,
    create_task_orchestrator,
    get_task_orchestrator,
    set_task_orchestrator,
)

# Публичный API (только orchestrator)
__all__ = [
    "TaskOrchestrator",
    "create_task_orchestrator",
    "get_task_orchestrator",
    "set_task_orchestrator",
]
