from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema


class AuditLogRead(ORMSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int | None
    user_id: int | None
    action: str
    module_name: str
    record_type: str
    record_id: int | None
    old_data_json: str | None
    new_data_json: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditLogFilters(BaseModel):
    user_id: int | None = None
    module_name: str | None = None
    action: str | None = None
    brand_id: int | None = None
    outlet_id: int | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
