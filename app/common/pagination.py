from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.common.response import SuccessResponse

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# Backward-compatible alias
PaginatedResponse = PaginatedData


class PaginatedSuccessResponse(SuccessResponse[PaginatedData[T]], Generic[T]):
    pass


def compute_pages(total: int, page_size: int) -> int:
    if page_size <= 0:
        return 0
    return math.ceil(total / page_size) if total > 0 else 0


def paginate_query(query, page: int, page_size: int):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def paginated_response(
    items: list[T],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedData[T]:
    return PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=compute_pages(total, page_size),
    )


def success_paginated(
    items: list[T],
    total: int,
    page: int,
    page_size: int,
    message: str = "Success",
) -> PaginatedSuccessResponse[T]:
    return PaginatedSuccessResponse(
        ok=True,
        message=message,
        data=paginated_response(items, total, page, page_size),
    )


SuccessResponse.model_rebuild()
PaginatedData.model_rebuild()
PaginatedSuccessResponse.model_rebuild()
