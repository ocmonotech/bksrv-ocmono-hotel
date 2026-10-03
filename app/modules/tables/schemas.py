from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.tables.models import TableStatus


class FloorCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    name: str = Field(max_length=128)
    sort_order: int = 0


class FloorRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    name: str
    sort_order: int
    is_active: bool


class TableCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    floor_id: int | None = None
    table_number: str = Field(max_length=32)
    capacity: int = Field(default=4, ge=1)


class TableRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    floor_id: int | None
    floor_name: str | None = None
    table_number: str
    capacity: int
    status: TableStatus
    assigned_waiter_id: int | None
    waiter_name: str | None = None
    current_order_id: int | None
    occupied_since: datetime | None
    is_active: bool
    running_bill: float = 0


class TableStatusUpdate(BaseModel):
    status: TableStatus


class AssignWaiterRequest(BaseModel):
    waiter_id: int


class MoveTableRequest(BaseModel):
    target_table_id: int


class MergeTablesRequest(BaseModel):
    source_table_id: int
    target_table_id: int


class ReserveTableRequest(BaseModel):
    notes: str | None = None


class MergeTablePlaceholderResponse(MessageResponse):
    source_table_id: int
    target_table_id: int
