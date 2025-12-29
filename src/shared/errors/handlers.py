"""Exception handlers for FastAPI.

Обработчики исключений для FastAPI приложения.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from src.shared.errors.base import AppException
from src.shared.errors.context import get_trace_id
from src.shared.errors.schemas import ErrorResponse


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Обработчик доменных исключений.

    Args:
        request: HTTP запрос.
        exc: Исключение AppException.

    Returns:
        JSON ответ с ошибкой.

    """
    logger.error(
        f"Business error: {exc.code}",
        error_code=exc.code,
        message=exc.message,
        details=exc.details,
        trace_id=get_trace_id(),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response().model_dump(),
        headers={"X-Error-Code": exc.code, "X-Trace-Id": get_trace_id()},
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic.

    Args:
        request: HTTP запрос.
        exc: Исключение валидации.

    Returns:
        JSON ответ с ошибкой валидации.

    """
    trace_id = get_trace_id()

    logger.warning(
        "Validation error",
        errors=exc.errors(),
        trace_id=trace_id,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="VALIDATION_ERROR",
            message="Ошибка валидации входных данных",
            details={"errors": exc.errors()},
            trace_id=trace_id,
        ).model_dump(),
        headers={"X-Trace-Id": trace_id},
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Последний обработчик для непредвиденных ошибок.

    Args:
        request: HTTP запрос.
        exc: Любое исключение.

    Returns:
        JSON ответ с общей ошибкой.

    """
    trace_id = get_trace_id()

    logger.exception(
        "Unhandled exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        trace_id=trace_id,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="INTERNAL_SERVER_ERROR",
            message="Внутренняя ошибка сервера",
            details={},
            trace_id=trace_id,
        ).model_dump(),
        headers={"X-Trace-Id": trace_id},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Зарегистрировать обработчики исключений в FastAPI.

    Args:
        app: Экземпляр FastAPI приложения.

    """
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    logger.info("Exception handlers registered")
