from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.base_model import RecordStatus
from app.common.response import ORMSchema, TimestampSchema


class OutletCreate(BaseModel):
    brand_id: int
    outlet_name: str = Field(max_length=255)
    location: str = Field(max_length=128)
    address: str | None = None
    manager_name: str | None = None
    manager_mobile: str | None = None
    opening_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    closing_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    gst_number: str | None = None
    fssai_number: str | None = None


class OutletUpdate(BaseModel):
    outlet_name: str | None = None
    location: str | None = None
    address: str | None = None
    manager_name: str | None = None
    manager_mobile: str | None = None
    opening_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    closing_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    gst_number: str | None = None
    fssai_number: str | None = None
    status: RecordStatus | None = None
    is_active: bool | None = None


class OutletRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int
    outlet_name: str
    location: str
    address: str | None
    manager_name: str | None
    manager_mobile: str | None
    opening_time: str | None
    closing_time: str | None
    status: RecordStatus
    gst_number: str | None
    fssai_number: str | None
    is_active: bool
