"""Shared errors module.

Система обработки ошибок приложения.
"""

from src.shared.errors.base import AppException
from src.shared.errors.context import get_trace_id, set_trace_id, trace_id_var
from src.shared.errors.decorators import safe_deco
from src.shared.errors.domain_errors import (
    ConflictError,
    JSONFixFailedError,
    JSONParseError,
    MemoryExceededError,
    ModelNotLoadedError,
    NotFoundError,
    ProviderUnavailableError,
    ServiceUnavailableError,
    TaskNotFoundError,
    ValidationError,
)
from src.shared.errors.handlers import setup_exception_handlers
from src.shared.errors.schemas import ErrorDetail, ErrorResponse

__all__ = [
    # Base
    "AppException",
    "ConflictError",
    # Schemas
    "ErrorDetail",
    "ErrorResponse",
    "JSONFixFailedError",
    "JSONParseError",
    "MemoryExceededError",
    "ModelNotLoadedError",
    # Domain errors
    "NotFoundError",
    "ProviderUnavailableError",
    "ServiceUnavailableError",
    "TaskNotFoundError",
    "ValidationError",
    "get_trace_id",
    # Decorators
    "safe_deco",
    "set_trace_id",
    # Handlers
    "setup_exception_handlers",
    # Context
    "trace_id_var",
]
