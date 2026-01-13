"""Dependency Injection для FastAPI routes.

FastAPI Depends functions для внедрения зависимостей в endpoints.
Убирает глобальные синглтоны и tight coupling.

Example:
    >>> from fastapi import APIRouter, Depends
    >>> from src.core.dependencies import get_task_orchestrator
    >>>
    >>> @router.post("/tasks")
    >>> async def create_task(
    ...     orchestrator: TaskOrchestrator = Depends(get_task_orchestrator)
    ... ):
    ...     return await orchestrator.submit_task(...)

See Also:
    - DOC-02-09: Стандарты документирования
    - FastAPI Depends: https://fastapi.tiangolo.com/tutorial/dependencies/

"""

from typing import Annotated

from fastapi import Depends

from src.adapters import IntakeAdapter, get_intake_adapter
from src.services.conversation_store import ConversationStore, get_conversation_store
from src.services.model_presets import (
    CompatibilityChecker,
    ModelPresetsLoader,
    get_compatibility_checker,
    get_presets_loader,
)
from src.services.prompt_service import PromptService, get_prompt_service
from src.services.session_store import SessionStore, get_session_store
from src.services.task import TaskOrchestrator, get_task_orchestrator

# Dependency Injection Aliases

# TaskOrchestrator dependency
TaskOrchestratorDep = Annotated[TaskOrchestrator, Depends(get_task_orchestrator)]

# PromptService dependency
PromptServiceDep = Annotated[PromptService, Depends(get_prompt_service)]

# IntakeAdapter dependency
IntakeAdapterDep = Annotated[IntakeAdapter, Depends(get_intake_adapter)]

# SessionStore dependency
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]

# ModelPresetsLoader dependency
PresetsLoaderDep = Annotated[ModelPresetsLoader, Depends(get_presets_loader)]

# CompatibilityChecker dependency
CompatibilityCheckerDep = Annotated[CompatibilityChecker, Depends(get_compatibility_checker)]

# ConversationStore dependency
ConversationStoreDep = Annotated[ConversationStore, Depends(get_conversation_store)]


# Dependency Provider Functions
# (Используются через Depends() в routes)


def get_orchestrator() -> TaskOrchestrator:
    """Получить TaskOrchestrator dependency.

    Returns:
        TaskOrchestrator instance

    Note:
        Используется через Depends(get_orchestrator) в FastAPI routes.

    """
    return get_task_orchestrator()


def get_prompt_service_dep() -> PromptService:
    """Получить PromptService dependency.

    Returns:
        PromptService instance

    Note:
        Используется через Depends(get_prompt_service_dep) в FastAPI routes.

    """
    return get_prompt_service()


def get_adapter() -> IntakeAdapter:
    """Получить IntakeAdapter dependency.

    Returns:
        IntakeAdapter instance

    Note:
        Используется через Depends(get_adapter) в FastAPI routes.

    """
    return get_intake_adapter()


def get_session() -> SessionStore:
    """Получить SessionStore dependency.

    Returns:
        SessionStore instance

    Note:
        Используется через Depends(get_session) в FastAPI routes.

    """
    return get_session_store()


def get_loader() -> ModelPresetsLoader:
    """Получить ModelPresetsLoader dependency.

    Returns:
        ModelPresetsLoader instance

    Note:
        Используется через Depends(get_loader) в FastAPI routes.

    """
    return get_presets_loader()


def get_checker() -> CompatibilityChecker:
    """Получить CompatibilityChecker dependency.

    Returns:
        CompatibilityChecker instance

    Note:
        Используется через Depends(get_checker) в FastAPI routes.

    """
    return get_compatibility_checker()


def get_conversation() -> ConversationStore:
    """Получить ConversationStore dependency.

    Returns:
        ConversationStore instance

    Note:
        Используется через Depends(get_conversation) в FastAPI routes.

    """
    return get_conversation_store()
