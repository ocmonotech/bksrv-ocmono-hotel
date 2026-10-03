from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import PERMISSION_LABELS, Permission
from app.modules.roles.models import Permission as PermissionModel
from app.modules.roles.models import Role, RolePermission
from app.modules.roles.schemas import RoleCreate, RolePermissionAssign, RoleRead, RoleUpdate


DEFAULT_ROLES: list[tuple[str, str]] = [
    ("Super Admin", "Full platform access"),
    ("Owner", "Business owner with broad access"),
    ("Operations Manager", "Chain operations and outlet oversight"),
    ("Outlet Manager", "Single or multi-outlet management"),
    ("Cashier", "POS billing and payments"),
    ("Waiter", "Table service and order taking"),
    ("Kitchen Staff", "KOT and kitchen operations"),
    ("Inventory Manager", "Stock and procurement"),
    ("Marketing Manager", "CRM, campaigns and communications"),
    ("Accountant", "Reports and financial visibility"),
    ("Housekeeper", "Room cleaning and housekeeping operations"),
]

DEFAULT_ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "Super Admin": set(Permission),
    "Owner": set(Permission),
    "Operations Manager": {
        Permission.USERS_READ,
        Permission.BRANDS_READ,
        Permission.OUTLETS_READ,
        Permission.OUTLETS_WRITE,
        Permission.ROLES_READ,
        Permission.POS_READ,
        Permission.POS_WRITE,
        Permission.KOT_READ,
        Permission.KOT_WRITE,
        Permission.MENU_READ,
        Permission.MENU_WRITE,
        Permission.INVENTORY_READ,
        Permission.INVENTORY_WRITE,
        Permission.CUSTOMERS_READ,
        Permission.LEADS_READ,
        Permission.COMMS_READ,
        Permission.CAMPAIGNS_READ,
        Permission.REPORTS_READ,
        Permission.SETTINGS_READ,
        Permission.AUDIT_READ,
        Permission.DELIVERY_READ,
        Permission.DELIVERY_WRITE,
        Permission.PAYMENTS_READ,
        Permission.PAYMENTS_WRITE,
        Permission.BOOKING_READ,
        Permission.BOOKING_WRITE,
        Permission.EVENTS_READ,
        Permission.EVENTS_WRITE,
        Permission.HOUSEKEEPING_READ,
        Permission.HOUSEKEEPING_WRITE,
        Permission.PMS_READ,
        Permission.PMS_WRITE,
        Permission.OTA_READ,
        Permission.OTA_WRITE,
        Permission.SPA_READ,
        Permission.SPA_WRITE,
        Permission.BANQUET_READ,
        Permission.BANQUET_WRITE,
    },
    "Outlet Manager": {
        Permission.OUTLETS_READ,
        Permission.POS_READ,
        Permission.POS_WRITE,
        Permission.KOT_READ,
        Permission.KOT_WRITE,
        Permission.MENU_READ,
        Permission.INVENTORY_READ,
        Permission.INVENTORY_WRITE,
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_WRITE,
        Permission.LEADS_READ,
        Permission.LEADS_WRITE,
        Permission.COMMS_READ,
        Permission.REPORTS_READ,
        Permission.SETTINGS_READ,
        Permission.AUDIT_READ,
        Permission.DELIVERY_READ,
        Permission.DELIVERY_WRITE,
        Permission.PAYMENTS_READ,
        Permission.PAYMENTS_WRITE,
        Permission.BOOKING_READ,
        Permission.BOOKING_WRITE,
        Permission.EVENTS_READ,
        Permission.EVENTS_WRITE,
        Permission.HOUSEKEEPING_READ,
        Permission.HOUSEKEEPING_WRITE,
        Permission.PMS_READ,
        Permission.PMS_WRITE,
        Permission.OTA_READ,
        Permission.OTA_WRITE,
        Permission.SPA_READ,
        Permission.SPA_WRITE,
        Permission.BANQUET_READ,
        Permission.BANQUET_WRITE,
    },
    "Cashier": {
        Permission.POS_READ,
        Permission.POS_WRITE,
        Permission.KOT_READ,
        Permission.MENU_READ,
        Permission.CUSTOMERS_READ,
        Permission.DELIVERY_READ,
        Permission.PAYMENTS_READ,
        Permission.BOOKING_READ,
        Permission.PMS_READ,
    },
    "Waiter": {
        Permission.POS_READ,
        Permission.POS_WRITE,
        Permission.KOT_READ,
        Permission.MENU_READ,
        Permission.CUSTOMERS_READ,
        Permission.DELIVERY_READ,
        Permission.PAYMENTS_READ,
        Permission.BOOKING_READ,
        Permission.BOOKING_WRITE,
        Permission.EVENTS_READ,
        Permission.EVENTS_WRITE,
    },
    "Kitchen Staff": {
        Permission.KOT_READ,
        Permission.KOT_WRITE,
        Permission.MENU_READ,
    },
    "Inventory Manager": {
        Permission.INVENTORY_READ,
        Permission.INVENTORY_WRITE,
        Permission.MENU_READ,
        Permission.REPORTS_READ,
    },
    "Marketing Manager": {
        Permission.CUSTOMERS_READ,
        Permission.CUSTOMERS_WRITE,
        Permission.LEADS_READ,
        Permission.LEADS_WRITE,
        Permission.COMMS_READ,
        Permission.COMMS_WRITE,
        Permission.CAMPAIGNS_READ,
        Permission.CAMPAIGNS_WRITE,
        Permission.EVENTS_READ,
        Permission.EVENTS_WRITE,
        Permission.AI_READ,
        Permission.AI_WRITE,
        Permission.AI_APPROVE,
        Permission.REPORTS_READ,
    },
    "Accountant": {
        Permission.REPORTS_READ,
        Permission.SETTINGS_READ,
        Permission.CUSTOMERS_READ,
        Permission.OUTLETS_READ,
    },
    "Housekeeper": {
        Permission.OUTLETS_READ,
        Permission.HOUSEKEEPING_READ,
        Permission.HOUSEKEEPING_WRITE,
    },
}


def seed_permissions(db: Session) -> dict[str, PermissionModel]:
    permission_map: dict[str, PermissionModel] = {}
    for code, (label, module) in PERMISSION_LABELS.items():
        existing = db.query(PermissionModel).filter(PermissionModel.code == code.value).first()
        if existing:
            permission_map[code.value] = existing
            continue
        record = PermissionModel(code=code.value, name=label, module=module)
        db.add(record)
        db.flush()
        permission_map[code.value] = record
    return permission_map


def seed_default_roles(
    db: Session,
    tenant_id: int,
    brand_id: int | None,
    permission_map: dict[str, PermissionModel],
) -> dict[str, Role]:
    role_map: dict[str, Role] = {}
    for name, description in DEFAULT_ROLES:
        existing = (
            db.query(Role)
            .filter(Role.tenant_id == tenant_id, Role.name == name)
            .first()
        )
        if existing:
            role_map[name] = existing
            continue

        role = Role(
            tenant_id=tenant_id,
            brand_id=brand_id,
            name=name,
            description=description,
            is_system_role=True,
        )
        db.add(role)
        db.flush()

        for permission in DEFAULT_ROLE_PERMISSIONS.get(name, set()):
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission_map[permission.value].id,
                )
            )
        db.flush()
        role_map[name] = role
    return role_map


def sync_system_role_permissions(
    db: Session,
    tenant_id: int,
    permission_map: dict[str, PermissionModel],
) -> None:
    """Add newly introduced permissions to existing system roles."""
    from app.modules.roles.models import RolePermission

    for role_name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        role = (
            db.query(Role)
            .filter(
                Role.tenant_id == tenant_id,
                Role.name == role_name,
                Role.is_system_role.is_(True),
            )
            .first()
        )
        if role is None:
            continue

        existing_permission_ids = {
            row.permission_id
            for row in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        }
        for permission in permissions:
            perm_record = permission_map.get(permission.value)
            if perm_record is None or perm_record.id in existing_permission_ids:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=perm_record.id))


def list_permissions(db: Session) -> list[PermissionModel]:
    return db.query(PermissionModel).order_by(PermissionModel.module, PermissionModel.code).all()


def list_roles(db: Session, tenant_id: int) -> list[RoleRead]:
    roles = (
        db.query(Role)
        .options(joinedload(Role.role_permissions).joinedload(RolePermission.permission))
        .filter(Role.tenant_id == tenant_id)
        .order_by(Role.name)
        .all()
    )
    return [_to_role_read(role) for role in roles]


def get_role(db: Session, tenant_id: int, role_id: int) -> RoleRead:
    role = _get_role_entity(db, tenant_id, role_id)
    return _to_role_read(role)


def create_role(db: Session, tenant_id: int, data: RoleCreate) -> RoleRead:
    existing = (
        db.query(Role)
        .filter(Role.tenant_id == tenant_id, Role.name == data.name)
        .first()
    )
    if existing:
        raise ConflictError("Role name already exists for this tenant")

    role = Role(
        tenant_id=tenant_id,
        brand_id=data.brand_id,
        name=data.name,
        description=data.description,
        is_system_role=False,
    )
    db.add(role)
    db.flush()

    if data.permission_ids:
        _replace_role_permissions(db, role, data.permission_ids)

    db.commit()
    db.refresh(role)
    return get_role(db, tenant_id, role.id)


def update_role(db: Session, tenant_id: int, role_id: int, data: RoleUpdate) -> RoleRead:
    role = _get_role_entity(db, tenant_id, role_id)
    if role.is_system_role and data.name is not None and data.name != role.name:
        raise ForbiddenError("System roles cannot be renamed")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(role, key, value)

    db.commit()
    return get_role(db, tenant_id, role_id)


def delete_role(db: Session, tenant_id: int, role_id: int) -> None:
    role = _get_role_entity(db, tenant_id, role_id)
    if role.is_system_role:
        raise ForbiddenError("System roles cannot be deleted")
    role.is_active = False
    db.commit()


def assign_permissions(
    db: Session,
    tenant_id: int,
    role_id: int,
    data: RolePermissionAssign,
) -> RoleRead:
    role = _get_role_entity(db, tenant_id, role_id)
    _replace_role_permissions(db, role, data.permission_ids)
    db.commit()
    return get_role(db, tenant_id, role_id)


def _get_role_entity(db: Session, tenant_id: int, role_id: int) -> Role:
    role = (
        db.query(Role)
        .options(joinedload(Role.role_permissions).joinedload(RolePermission.permission))
        .filter(Role.id == role_id, Role.tenant_id == tenant_id)
        .first()
    )
    if role is None:
        raise NotFoundError("Role not found")
    return role


def _replace_role_permissions(db: Session, role: Role, permission_ids: list[int]) -> None:
    permissions = db.query(PermissionModel).filter(PermissionModel.id.in_(permission_ids)).all()
    if len(permissions) != len(set(permission_ids)):
        raise NotFoundError("One or more permissions not found")

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
    for permission in permissions:
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))


def _to_role_read(role: Role) -> RoleRead:
    from app.modules.roles.schemas import PermissionRead

    return RoleRead(
        id=role.id,
        tenant_id=role.tenant_id,
        brand_id=role.brand_id,
        name=role.name,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        created_at=role.created_at,
        updated_at=role.updated_at,
        permissions=[
            PermissionRead(
                id=rp.permission.id,
                code=rp.permission.code,
                name=rp.permission.name,
                module=rp.permission.module,
            )
            for rp in role.role_permissions
        ],
    )
