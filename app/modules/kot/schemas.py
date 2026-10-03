from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.kot.models import KotItemStatus, KotStatus
from app.modules.menu.models import PreparationArea


class KotItemRead(BaseModel):
    id: int
    kot_id: int
    order_item_id: int
    item_name: str
    quantity: int
    note: str | None
    status: KotItemStatus

    model_config = {"from_attributes": True}


class KotRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    order_id: int
    kot_number: str
    preparation_area: PreparationArea
    status: KotStatus
    created_by: int | None
    table_number: str | None = None
    order_type: str | None = None
    queue_token: str | None = None
    items: list[KotItemRead] = Field(default_factory=list)


class KotStatusUpdate(BaseModel):
    status: KotStatus


class KotItemStatusUpdate(BaseModel):
    status: KotItemStatus


class KotSummary(BaseModel):
    kot_id: int
    kot_number: str
    preparation_area: PreparationArea
