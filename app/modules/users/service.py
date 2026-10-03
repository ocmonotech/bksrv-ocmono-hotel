from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import get_password_hash
from app.modules.outlets.models import Outlet
from app.modules.roles.models import Role
from app.modules.users.models import User, UserOutlet
from app.modules.users.schemas import RoleSummary, UserCreate, UserOutletAssign, UserRead, UserUpdate


def list_users(db: Session, tenant_id: int, page: int, page_size: int) -> tuple[list[UserRead], int]:
    query = (
        db.query(User)
        .options(joinedload(User.role), joinedload(User.user_outlets))
        .filter(User.tenant_id == tenant_id)
        .order_by(User.full_name)
    )
    items, total = paginate_query(query, page, page_size)
    return [_to_user_read(user) for user in items], total


def get_user(db: Session, tenant_id: int, user_id: int) -> UserRead:
    user = _get_user_entity(db, tenant_id, user_id)
    return _to_user_read(user)


def create_user(db: Session, tenant_id: int, data: UserCreate) -> UserRead:
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise ConflictError("Email already registered")

    if data.role_id is not None:
        _validate_role(db, tenant_id, data.role_id)

    user = User(
        tenant_id=tenant_id,
        brand_id=data.brand_id,
        full_name=data.full_name,
        email=data.email,
        mobile=data.mobile,
        hashed_password=get_password_hash(data.password),
        role_id=data.role_id,
        is_super_admin=data.is_super_admin,
    )
    db.add(user)
    db.flush()

    if data.outlet_ids:
        _replace_user_outlets(db, user, tenant_id, data.outlet_ids)

    db.commit()
    return get_user(db, tenant_id, user.id)


def update_user(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: UserUpdate,
    actor_user_id: int | None = None,
) -> UserRead:
    user = _get_user_entity(db, tenant_id, user_id)

    payload = data.model_dump(exclude_unset=True)
    password = payload.pop("password", None)
    if password:
        user.hashed_password = get_password_hash(password)

    old_role_id = user.role_id
    if "role_id" in payload and payload["role_id"] is not None:
        _validate_role(db, tenant_id, payload["role_id"])

    for key, value in payload.items():
        setattr(user, key, value)

    if "role_id" in payload and payload["role_id"] != old_role_id:
        from app.modules.audit.models import AuditAction
        from app.modules.audit.service import log_audit

        log_audit(
            db,
            tenant_id=tenant_id,
            brand_id=user.brand_id,
            user_id=actor_user_id,
            action=AuditAction.USER_ROLE_UPDATED.value,
            module_name="users",
            record_type="user",
            record_id=user.id,
            old_data={"role_id": old_role_id},
            new_data={"role_id": payload["role_id"]},
        )

    db.commit()
    return get_user(db, tenant_id, user_id)


def delete_user(db: Session, tenant_id: int, user_id: int) -> None:
    user = _get_user_entity(db, tenant_id, user_id)
    user.is_active = False
    db.commit()


def assign_outlets(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: UserOutletAssign,
) -> UserRead:
    user = _get_user_entity(db, tenant_id, user_id)
    _replace_user_outlets(db, user, tenant_id, data.outlet_ids)
    db.commit()
    return get_user(db, tenant_id, user_id)


def _get_user_entity(db: Session, tenant_id: int, user_id: int) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.role), joinedload(User.user_outlets))
        .filter(User.id == user_id, User.tenant_id == tenant_id)
        .first()
    )
    if user is None:
        raise NotFoundError("User not found")
    return user


def _validate_role(db: Session, tenant_id: int, role_id: int) -> None:
    role = db.query(Role).filter(Role.id == role_id, Role.tenant_id == tenant_id).first()
    if role is None:
        raise NotFoundError("Role not found")


def _replace_user_outlets(
    db: Session,
    user: User,
    tenant_id: int,
    outlet_ids: list[int],
) -> None:
    if not outlet_ids:
        db.query(UserOutlet).filter(UserOutlet.user_id == user.id).delete()
        return

    outlets = (
        db.query(Outlet)
        .filter(Outlet.id.in_(outlet_ids), Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True))
        .all()
    )
    if len(outlets) != len(set(outlet_ids)):
        raise NotFoundError("One or more outlets not found for this tenant")

    db.query(UserOutlet).filter(UserOutlet.user_id == user.id).delete()
    for outlet in outlets:
        db.add(UserOutlet(user_id=user.id, outlet_id=outlet.id))


def _to_user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        brand_id=user.brand_id,
        full_name=user.full_name,
        email=user.email,
        mobile=user.mobile,
        role_id=user.role_id,
        role=RoleSummary(id=user.role.id, name=user.role.name) if user.role else None,
        is_super_admin=user.is_super_admin,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        outlet_ids=[uo.outlet_id for uo in user.user_outlets],
    )
