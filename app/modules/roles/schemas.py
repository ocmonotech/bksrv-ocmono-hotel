from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema


class PermissionRead(BaseModel):
    id: int
    code: str
    name: str
    module: str

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    name: str = Field(max_length=128)
    description: str | None = None
    brand_id: int | None = None
    permission_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    brand_id: int | None = None
    is_active: bool | None = None


class RolePermissionAssign(BaseModel):
    permission_ids: list[int]


class RoleRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    name: str
    description: str | None
    is_system_role: bool
    is_active: bool
    permissions: list[PermissionRead] = Field(default_factory=list)
