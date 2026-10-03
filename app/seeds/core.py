"""Core tenant, brand, outlet, RBAC, and user seeds."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.common.base_model import RecordStatus
from app.core.security import get_password_hash
from app.modules.brands.models import Brand
from app.modules.outlets.models import Outlet
from app.modules.roles import service as roles_service
from app.modules.tenants.enums import BusinessType
from app.modules.tenants.models import Tenant
from app.modules.users.models import User, UserOutlet
from app.seeds.base import SeedContext
from app.modules.outlets.demo_locations import sync_demo_outlet_locations
from app.seeds.constants import (
    DEMO_BRAND_NAME,
    DEMO_TENANT_COMPANY,
    DEMO_TENANT_EMAIL,
    DEMO_USER_PASSWORD,
    DEMO_USERS,
    OUTLET_SPECS,
    SUPER_ADMIN_EMAIL,
    SUPER_ADMIN_PASSWORD,
)


def seed_core(db: Session) -> SeedContext:
    tenant = _get_or_create_tenant(db)
    brand = _get_or_create_brand(db, tenant)
    outlets = _get_or_create_outlets(db, tenant, brand)

    permission_map = roles_service.seed_permissions(db)
    roles = roles_service.seed_default_roles(db, tenant.id, brand.id, permission_map)
    roles_service.sync_system_role_permissions(db, tenant.id, permission_map)

    users: dict[str, User] = {}
    users[SUPER_ADMIN_EMAIL] = _seed_super_admin(db, tenant, brand, outlets, roles["Super Admin"])
    users.update(_seed_demo_users(db, tenant, brand, outlets, roles))

    return SeedContext(tenant=tenant, brand=brand, outlets=outlets, roles=roles, users=users)


def _get_or_create_tenant(db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.company_name == DEMO_TENANT_COMPANY).first()
    if tenant is not None:
        return tenant

    tenant = Tenant(
        company_name=DEMO_TENANT_COMPANY,
        owner_name="Chain Owner",
        email=DEMO_TENANT_EMAIL,
        mobile="+919876543210",
        status=RecordStatus.ACTIVE,
        subscription_plan="enterprise",
        trial_ends_at=datetime.utcnow() + timedelta(days=30),
        business_type=BusinessType.RESORT,
    )
    db.add(tenant)
    db.flush()
    return tenant


def _get_or_create_brand(db: Session, tenant: Tenant) -> Brand:
    brand = (
        db.query(Brand)
        .filter(Brand.tenant_id == tenant.id, Brand.brand_name == DEMO_BRAND_NAME)
        .first()
    )
    if brand is not None:
        if not brand.logo_url:
            brand.logo_url = (
                "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=240&q=80"
            )
            db.flush()
        return brand

    brand = Brand(
        tenant_id=tenant.id,
        brand_name=DEMO_BRAND_NAME,
        gst_number="27AABCB1234A1Z5",
        fssai_number="21521000000000",
        support_number="+919876543210",
        address="Mumbai, Maharashtra",
        logo_url="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=240&q=80",
        status=RecordStatus.ACTIVE,
    )
    db.add(brand)
    db.flush()
    return brand


def _get_or_create_outlets(db: Session, tenant: Tenant, brand: Brand) -> dict[str, Outlet]:
    """Ensure canonical outlet rows exist; seed keys stay stable by creation order."""
    existing = (
        db.query(Outlet)
        .filter(Outlet.tenant_id == tenant.id)
        .order_by(Outlet.id.asc())
        .all()
    )
    outlets: dict[str, Outlet] = {}
    for index, (name, location) in enumerate(OUTLET_SPECS):
        if index < len(existing):
            outlet = existing[index]
        else:
            outlet = Outlet(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_name=name,
                location=location,
                address=f"{location}, Mumbai",
                manager_name=f"{location} Manager",
                manager_mobile="+919876543211",
                opening_time="09:00",
                closing_time="23:00",
                status=RecordStatus.ACTIVE,
            )
            db.add(outlet)
            db.flush()
        outlets[name] = outlet

    sync_demo_outlet_locations(db, tenant.id, tenant.business_type)
    return outlets


def _seed_super_admin(db: Session, tenant: Tenant, brand: Brand, outlets: dict[str, Outlet], role) -> User:
    user = db.query(User).filter(User.email == SUPER_ADMIN_EMAIL).first()
    if user is None:
        user = User(
            tenant_id=tenant.id,
            brand_id=brand.id,
            email=SUPER_ADMIN_EMAIL,
            full_name="Super Admin",
            mobile="+919876543200",
            hashed_password=get_password_hash(SUPER_ADMIN_PASSWORD),
            role_id=role.id,
            is_super_admin=True,
        )
        db.add(user)
        db.flush()
    else:
        user.role_id = role.id
        user.is_super_admin = True
        user.tenant_id = tenant.id
        user.brand_id = brand.id
        user.hashed_password = get_password_hash(SUPER_ADMIN_PASSWORD)

    _ensure_user_outlets(db, user, list(outlets.values()))
    return user


def _seed_demo_users(
    db: Session,
    tenant: Tenant,
    brand: Brand,
    outlets: dict[str, Outlet],
    roles: dict,
) -> dict[str, User]:
    andheri = outlets["Andheri West"]
    bandra = outlets["Bandra"]
    users: dict[str, User] = {}

    outlet_map = {
        "cashier.andheri@restrochain.test": [andheri],
        "waiter.bandra@restrochain.test": [bandra],
        "housekeeper@restrochain.test": [andheri],
    }

    for email, full_name, role_name, is_super_admin, all_outlets in DEMO_USERS:
        user = db.query(User).filter(User.email == email).first()
        role = roles.get(role_name)
        if user is None:
            user = User(
                tenant_id=tenant.id,
                brand_id=brand.id,
                email=email,
                full_name=full_name,
                mobile="+919876543220",
                hashed_password=get_password_hash(DEMO_USER_PASSWORD),
                role_id=role.id if role else None,
                is_super_admin=is_super_admin,
            )
            db.add(user)
            db.flush()
        else:
            user.role_id = role.id if role else user.role_id
            user.tenant_id = tenant.id
            user.brand_id = brand.id
            user.hashed_password = get_password_hash(DEMO_USER_PASSWORD)

        assigned = list(outlets.values()) if all_outlets else outlet_map.get(email, [andheri])
        _ensure_user_outlets(db, user, assigned)
        users[email] = user

    return users


def _ensure_user_outlets(db: Session, user: User, outlets: list[Outlet]) -> None:
    existing = {uo.outlet_id for uo in user.user_outlets} if user.user_outlets else set()
    for outlet in outlets:
        if outlet.id not in existing:
            db.add(UserOutlet(user_id=user.id, outlet_id=outlet.id))
