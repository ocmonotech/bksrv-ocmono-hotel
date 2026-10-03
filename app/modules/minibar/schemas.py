from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.common.response import ORMSchema, TimestampSchema
from app.modules.minibar.models import MinibarPostingStatus
from app.modules.pms.schemas import FolioRead


class MinibarCatalogItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    sku_code: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    category: str = Field(default="general", max_length=64)
    unit_price: float = Field(gt=0)
    gst_percent: float = Field(default=0, ge=0, le=100)
    outlet_id: int | None = None
    menu_item_id: int | None = None
    raw_material_id: int | None = None
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def require_link_or_standalone(self) -> "MinibarCatalogItemCreate":
        # Standalone priced items are allowed without menu/raw link (no stock deduct).
        return self


class MinibarCatalogItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    sku_code: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    unit_price: float | None = Field(default=None, gt=0)
    gst_percent: float | None = Field(default=None, ge=0, le=100)
    outlet_id: int | None = None
    menu_item_id: int | None = None
    raw_material_id: int | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class MinibarCatalogItemRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None = None
    outlet_id: int | None = None
    name: str
    sku_code: str | None = None
    barcode: str | None = None
    category: str
    unit_price: float
    gst_percent: float
    menu_item_id: int | None = None
    raw_material_id: int | None = None
    sort_order: int
    is_active: bool = True


class MinibarChargeLineCreate(BaseModel):
    catalog_item_id: int
    quantity: float = Field(gt=0, le=99)


class MinibarChargeCreate(BaseModel):
    lines: list[MinibarChargeLineCreate] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=500)
    room_id: int | None = None


class MinibarPostingLineRead(ORMSchema, TimestampSchema):
    id: int
    posting_id: int
    catalog_item_id: int
    item_name: str
    quantity: float
    unit_price: float
    line_total: float
    raw_material_id: int | None = None


class MinibarPostingRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None = None
    outlet_id: int
    room_id: int
    room_number: str | None = None
    reservation_id: int
    guest_name: str | None = None
    folio_entry_id: int | None = None
    status: MinibarPostingStatus
    total_amount: float
    notes: str | None = None
    posted_by: int | None = None
    voided_by: int | None = None
    void_reason: str | None = None
    lines: list[MinibarPostingLineRead] = Field(default_factory=list)
    created_at: datetime | None = None


class MinibarChargeResponse(BaseModel):
    posting: MinibarPostingRead
    folio: FolioRead


class MinibarVoidRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
