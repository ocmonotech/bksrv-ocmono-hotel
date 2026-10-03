from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.common.response import ORMSchema, TimestampSchema


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    mobile: str | None = None
    brand_id: int | None = None
    role_id: int | None = None
    is_super_admin: bool = False
    outlet_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = None
    mobile: str | None = None
    brand_id: int | None = None
    role_id: int | None = None
    is_super_admin: bool | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class UserOutletAssign(BaseModel):
    outlet_ids: list[int]


class RoleSummary(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class UserRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    full_name: str
    email: EmailStr
    mobile: str | None
    role_id: int | None
    role: RoleSummary | None = None
    is_super_admin: bool
    is_active: bool
    last_login_at: str | None = None
    outlet_ids: list[int] = Field(default_factory=list)
