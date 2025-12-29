"""Error context management.

Управление контекстом для trace_id.
"""

from contextvars import ContextVar
from uuid import uuid4

# Context var для trace_id
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Получить текущий trace_id или сгенерировать новый.

    Returns:
        Строка trace_id.

    """
    trace_id = trace_id_var.get()
    if not trace_id:
        trace_id = str(uuid4())
        trace_id_var.set(trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    """Установить trace_id в контекст.

    Args:
        trace_id: Идентификатор трассировки.

    """
    trace_id_var.set(trace_id)
