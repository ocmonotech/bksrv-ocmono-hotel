from __future__ import annotations

from fastapi import status
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, code: str | None = None):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND, "not_found")


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, "unauthorized")


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status.HTTP_403_FORBIDDEN, "forbidden")


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict"):
        super().__init__(message, status.HTTP_409_CONFLICT, "conflict")


def register_exception_handlers(app) -> None:
    from app.common.response import ErrorResponse

    @app.exception_handler(AppError)
    async def app_error_handler(_, exc: AppError):
        payload = ErrorResponse(
            ok=False,
            message=exc.message,
            errors=[exc.message],
            code=exc.code,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())
