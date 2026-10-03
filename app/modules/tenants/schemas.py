from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.common.base_model import RecordStatus
from app.common.response import ORMSchema, TimestampSchema
from app.modules.tenants.enums import BusinessType


class TenantCreate(BaseModel):
    company_name: str = Field(max_length=255)
    owner_name: str = Field(max_length=255)
    email: EmailStr
    mobile: str = Field(max_length=32)
    subscription_plan: str = "trial"
    trial_ends_at: datetime | None = None
    business_type: BusinessType = BusinessType.RESORT


class TenantUpdate(BaseModel):
    company_name: str | None = None
    owner_name: str | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    status: RecordStatus | None = None
    subscription_plan: str | None = None
    trial_ends_at: datetime | None = None
    is_active: bool | None = None
    business_type: BusinessType | None = None


class TenantRead(ORMSchema, TimestampSchema):
    id: int
    company_name: str
    owner_name: str
    email: EmailStr
    mobile: str
    status: RecordStatus
    subscription_plan: str
    trial_ends_at: datetime | None
    is_active: bool
    business_type: BusinessType
