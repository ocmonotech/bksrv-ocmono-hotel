from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.base_model import RecordStatus
from app.common.response import ORMSchema, TimestampSchema


class BrandCreate(BaseModel):
    brand_name: str = Field(max_length=255)
    gst_number: str | None = None
    fssai_number: str | None = None
    support_number: str | None = None
    address: str | None = None
    logo_url: str | None = None


class BrandUpdate(BaseModel):
    brand_name: str | None = None
    gst_number: str | None = None
    fssai_number: str | None = None
    support_number: str | None = None
    address: str | None = None
    logo_url: str | None = None
    status: RecordStatus | None = None
    is_active: bool | None = None


class BrandRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_name: str
    gst_number: str | None
    fssai_number: str | None
    support_number: str | None
    address: str | None
    logo_url: str | None
    status: RecordStatus
    is_active: bool
