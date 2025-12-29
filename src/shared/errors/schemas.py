"""Error schemas.

Pydantic схемы для ошибок.
"""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Детальная информация об ошибке."""

    field: str | None = Field(default=None, description="Поле с ошибкой")
    message: str | None = Field(default=None, description="Сообщение об ошибке")
    code: str | None = Field(default=None, description="Код ошибки")
    context: dict[str, Any] | None = Field(default=None, description="Дополнительный контекст")


class ErrorResponse(BaseModel):
    """Стандартный ответ с ошибкой."""

    error: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Человекочитаемое сообщение")
    details: dict[str, Any] = Field(default_factory=dict, description="Дополнительные детали")
    trace_id: str = Field(default="", description="ID трассировки для отладки")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "MODEL_NOT_LOADED",
                "message": "Модель не загружена",
                "details": {"model": "Qwen/Qwen2.5-3B-Instruct"},
                "trace_id": "a1b2c3d4-e5f6-4789-9012-345678901234",
            }
        }
