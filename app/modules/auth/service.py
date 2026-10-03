from __future__ import annotations

from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import UnauthorizedError
from app.core.permissions import Permission, TENANT_WIDE_ROLE_NAMES
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    TOKEN_TYPE_BEARER,
    create_access_token,
    create_refresh_token,
    decode_token_safe,
    verify_password,
)
from app.modules.audit.models import AuditAction
from app.modules.audit.service import log_audit
from app.modules.auth.dependencies import resolve_allowed_outlets, resolve_brand_id
from app.modules.auth.models import RevokedToken
from app.modules.auth.schemas import (
    AuthUser,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    OutletAccess,
    RefreshTokenResponse,
)
from app.modules.roles.models import Permission as PermissionModel
from app.modules.roles.models import RolePermission
from app.modules.tenants.models import Tenant
from app.modules.tenants.enums import BusinessType
from app.modules.tenants.service import seed_demo_tenant
from app.modules.users.models import User
from app.modules.users.schemas import RoleSummary

MANAGER_ROLE_NAMES = TENANT_WIDE_ROLE_NAMES | {"Outlet Manager", "General Manager", "Store Manager"}


def login(db: Session, credentials: LoginRequest) -> LoginResponse:
    user = (
        db.query(User)
        .options(joinedload(User.role), joinedload(User.user_outlets))
        .filter(User.email == credentials.email)
        .first()
    )
    if user is None or not verify_password(credentials.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("User account is inactive")

    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    response = _build_login_response(db, user)
    log_audit(
        db,
        tenant_id=user.tenant_id,
        brand_id=user.brand_id,
        outlet_id=None,
        user_id=user.id,
        action=AuditAction.USER_LOGIN.value,
        module_name="auth",
        record_type="user",
        record_id=user.id,
        old_data=None,
        new_data={"email": user.email},
    )
    db.commit()
    return response


def get_me(db: Session, user: User) -> MeResponse:
    user = (
        db.query(User)
        .options(joinedload(User.role), joinedload(User.user_outlets))
        .filter(User.id == user.id)
        .first()
    )
    context = _build_auth_context(db, user)
    return MeResponse(
        user=context["user"],
        role=context["role"],
        role_id=user.role_id,
        role_details=context["role_details"],
        tenant_id=user.tenant_id,
        tenant_name=context["tenant_name"],
        business_type=context["business_type"],
        brand_id=context["brand_id"],
        is_super_admin=user.is_super_admin,
        permissions=context["permissions"],
        allowed_outlets=context["allowed_outlets"],
    )


def refresh_access_token(db: Session, refresh_token: str) -> RefreshTokenResponse:
    payload = decode_token_safe(refresh_token)
    if payload is None or payload.get("type") != REFRESH_TOKEN_TYPE:
        raise UnauthorizedError("Invalid refresh token")

    if _is_token_revoked(db, payload.get("jti")):
        raise UnauthorizedError("Refresh token has been revoked")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid refresh token")

    _revoke_token(db, payload, user.id)
    claims = _token_claims(user)
    new_refresh = create_refresh_token(user.id)
    return RefreshTokenResponse(
        access_token=create_access_token(user.id, claims),
        refresh_token=new_refresh,
        token_type=TOKEN_TYPE_BEARER,
    )


def logout(db: Session, user: User, token: str | None = None) -> LogoutResponse:
    if token:
        payload = decode_token_safe(token)
        if payload and payload.get("jti"):
            _revoke_token(db, payload, user.id)

    log_audit(
        db,
        tenant_id=user.tenant_id,
        brand_id=user.brand_id,
        outlet_id=None,
        user_id=user.id,
        action=AuditAction.USER_LOGOUT.value,
        module_name="auth",
        record_type="user",
        record_id=user.id,
        old_data=None,
        new_data={"logged_out_at": datetime.now(UTC).isoformat()},
    )
    db.commit()
    return LogoutResponse()


def user_can_approve_pos_actions(user: User) -> bool:
    if user.is_super_admin:
        return True
    role_name = user.role.name if user.role else None
    return role_name in MANAGER_ROLE_NAMES


def seed_demo_data(db: Session) -> None:
    seed_demo_tenant(db)


def _build_login_response(db: Session, user: User) -> LoginResponse:
    context = _build_auth_context(db, user)
    claims = _token_claims(user)
    return LoginResponse(
        access_token=create_access_token(user.id, claims),
        refresh_token=create_refresh_token(user.id),
        token_type=TOKEN_TYPE_BEARER,
        user=context["user"],
        role=context["role"],
        role_id=user.role_id,
        tenant_id=user.tenant_id,
        tenant_name=context["tenant_name"],
        business_type=context["business_type"],
        brand_id=context["brand_id"],
        is_super_admin=user.is_super_admin,
        permissions=context["permissions"],
        allowed_outlets=context["allowed_outlets"],
    )


def resolve_user_permissions(db: Session, user: User) -> list[str]:
    if user.is_super_admin:
        return [permission.value for permission in Permission]

    if user.role_id is None:
        return []

    rows = (
        db.query(PermissionModel.code)
        .join(RolePermission, RolePermission.permission_id == PermissionModel.id)
        .filter(RolePermission.role_id == user.role_id)
        .order_by(PermissionModel.code)
        .all()
    )
    return [row[0] for row in rows]


def _build_auth_context(db: Session, user: User) -> dict:
    role_name = user.role.name if user.role else "Unassigned"
    outlets = resolve_allowed_outlets(db, user)
    tenant = db.get(Tenant, user.tenant_id)
    return {
        "user": AuthUser(id=user.id, email=user.email, full_name=user.full_name),
        "role": role_name,
        "role_details": RoleSummary(id=user.role.id, name=user.role.name) if user.role else None,
        "tenant_name": tenant.company_name if tenant else None,
        "business_type": tenant.business_type.value if tenant else BusinessType.RESORT.value,
        "brand_id": resolve_brand_id(db, user),
        "permissions": resolve_user_permissions(db, user),
        "allowed_outlets": [
            OutletAccess(
                id=o.id,
                outlet_name=o.outlet_name,
                location=o.location,
                brand_id=o.brand_id,
            )
            for o in outlets
        ],
    }


def _token_claims(user: User) -> dict:
    return {
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
        "tenant_id": user.tenant_id,
        "brand_id": user.brand_id,
        "is_super_admin": user.is_super_admin,
    }


def _is_token_revoked(db: Session, jti: str | None) -> bool:
    if not jti:
        return False
    return (
        db.query(RevokedToken.id)
        .filter(RevokedToken.jti == jti)
        .first()
        is not None
    )


def _revoke_token(db: Session, payload: dict, user_id: int | None) -> None:
    jti = payload.get("jti")
    if not jti:
        return
    if _is_token_revoked(db, jti):
        return
    expires_at = datetime.utcnow()
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        expires_at = datetime.utcfromtimestamp(exp)
    db.add(
        RevokedToken(
            jti=jti,
            token_type=str(payload.get("type", "access")),
            user_id=user_id,
            expires_at=expires_at,
        )
    )
