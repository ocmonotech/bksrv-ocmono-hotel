from __future__ import annotations

from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from pydantic import BaseModel, Field

from app.modules.users.schemas import RoleSummary


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class AuthUser(BaseModel):
    id: int
    email: str
    full_name: str


class OutletAccess(BaseModel):
    id: int
    outlet_name: str
    location: str
    brand_id: int


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AuthUser
    role: str
    role_id: int | None = None
    tenant_id: int
    tenant_name: str | None = None
    business_type: str = "resort"
    brand_id: int | None = None
    is_super_admin: bool = False
    permissions: list[str] = Field(default_factory=list)
    allowed_outlets: list[OutletAccess] = Field(default_factory=list)


class MeResponse(BaseModel):
    user: AuthUser
    role: str
    role_id: int | None = None
    role_details: RoleSummary | None = None
    tenant_id: int
    tenant_name: str | None = None
    business_type: str = "resort"
    brand_id: int | None = None
    is_super_admin: bool = False
    permissions: list[str] = Field(default_factory=list)
    allowed_outlets: list[OutletAccess] = Field(default_factory=list)


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    message: str = "Token refreshed successfully"


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"
