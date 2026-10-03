from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SuccessResponse(BaseModel, Generic[T]):
    ok: bool = True
    message: str = "Success"
    data: T


class ErrorResponse(BaseModel):
    ok: bool = False
    message: str
    errors: list[str] = Field(default_factory=list)
    code: str | None = None


class MessageResponse(BaseModel):
    message: str


def success(data: T, message: str = "Success") -> SuccessResponse[T]:
    return SuccessResponse(ok=True, message=message, data=data)


def error(message: str, errors: list[str] | None = None, code: str | None = None) -> ErrorResponse:
    return ErrorResponse(
        ok=False,
        message=message,
        errors=errors or [],
        code=code,
    )
