from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.common.base_model import RecordStatus
from app.core.exceptions import UnauthorizedError
from app.core.permissions import TENANT_WIDE_ROLE_NAMES
from app.core.security import ACCESS_TOKEN_TYPE, decode_token_safe
from app.modules.auth.models import RevokedToken
from app.modules.outlets.models import Outlet
from app.modules.users.models import User, UserOutlet

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Not authenticated")

    payload = decode_token_safe(credentials.credentials)
    if payload is None or payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid or expired token")

    jti = payload.get("jti")
    if jti and (
        db.query(RevokedToken.id).filter(RevokedToken.jti == jti).first() is not None
    ):
        raise UnauthorizedError("Token has been revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid or expired token")

    user = (
        db.query(User)
        .options(joinedload(User.role), joinedload(User.user_outlets))
        .filter(User.id == int(user_id))
        .first()
    )
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return user


def resolve_allowed_outlets(db: Session, user: User) -> list[Outlet]:
    if user.is_super_admin:
        return _all_tenant_outlets(db, user.tenant_id)

    role_name = user.role.name if user.role else None
    if role_name in TENANT_WIDE_ROLE_NAMES:
        return _all_tenant_outlets(db, user.tenant_id)

    outlet_ids = [uo.outlet_id for uo in user.user_outlets]
    if not outlet_ids:
        return []

    return (
        db.query(Outlet)
        .filter(
            Outlet.id.in_(outlet_ids),
            Outlet.tenant_id == user.tenant_id,
            Outlet.is_active.is_(True),
            Outlet.status == RecordStatus.ACTIVE,
        )
        .order_by(Outlet.outlet_name)
        .all()
    )


def resolve_brand_id(db: Session, user: User) -> int | None:
    if user.brand_id is not None:
        return user.brand_id

    outlets = resolve_allowed_outlets(db, user)
    if outlets:
        return outlets[0].brand_id

    first_outlet = (
        db.query(Outlet)
        .filter(
            Outlet.tenant_id == user.tenant_id,
            Outlet.is_active.is_(True),
            Outlet.status == RecordStatus.ACTIVE,
        )
        .order_by(Outlet.id)
        .first()
    )
    return first_outlet.brand_id if first_outlet else None


def _all_tenant_outlets(db: Session, tenant_id: int) -> list[Outlet]:
    return (
        db.query(Outlet)
        .filter(
            Outlet.tenant_id == tenant_id,
            Outlet.is_active.is_(True),
            Outlet.status == RecordStatus.ACTIVE,
        )
        .order_by(Outlet.outlet_name)
        .all()
    )
