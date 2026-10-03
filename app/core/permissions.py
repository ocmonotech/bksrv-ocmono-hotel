from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    TENANTS_READ = "tenants:read"
    TENANTS_WRITE = "tenants:write"
    BRANDS_READ = "brands:read"
    BRANDS_WRITE = "brands:write"
    OUTLETS_READ = "outlets:read"
    OUTLETS_WRITE = "outlets:write"
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"
    POS_READ = "pos:read"
    POS_WRITE = "pos:write"
    KOT_READ = "kot:read"
    KOT_WRITE = "kot:write"
    MENU_READ = "menu:read"
    MENU_WRITE = "menu:write"
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    LEADS_READ = "leads:read"
    LEADS_WRITE = "leads:write"
    COMMS_READ = "comms:read"
    COMMS_WRITE = "comms:write"
    CAMPAIGNS_READ = "campaigns:read"
    CAMPAIGNS_WRITE = "campaigns:write"
    AI_READ = "ai:read"
    AI_WRITE = "ai:write"
    AI_APPROVE = "ai:approve"
    REPORTS_READ = "reports:read"
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    AUDIT_READ = "audit:read"
    DELIVERY_READ = "delivery:read"
    DELIVERY_WRITE = "delivery:write"
    PAYMENTS_READ = "payments:read"
    PAYMENTS_WRITE = "payments:write"
    BOOKING_READ = "booking:read"
    BOOKING_WRITE = "booking:write"
    EVENTS_READ = "events:read"
    EVENTS_WRITE = "events:write"
    HOUSEKEEPING_READ = "housekeeping:read"
    HOUSEKEEPING_WRITE = "housekeeping:write"
    PMS_READ = "pms:read"
    PMS_WRITE = "pms:write"
    OTA_READ = "ota:read"
    OTA_WRITE = "ota:write"
    SPA_READ = "spa:read"
    SPA_WRITE = "spa:write"
    BANQUET_READ = "banquet:read"
    BANQUET_WRITE = "banquet:write"


PERMISSION_LABELS: dict[Permission, tuple[str, str]] = {
    Permission.USERS_READ: ("View users", "users"),
    Permission.USERS_WRITE: ("Manage users", "users"),
    Permission.TENANTS_READ: ("View tenants", "tenants"),
    Permission.TENANTS_WRITE: ("Manage tenants", "tenants"),
    Permission.BRANDS_READ: ("View brands", "brands"),
    Permission.BRANDS_WRITE: ("Manage brands", "brands"),
    Permission.OUTLETS_READ: ("View outlets", "outlets"),
    Permission.OUTLETS_WRITE: ("Manage outlets", "outlets"),
    Permission.ROLES_READ: ("View roles", "roles"),
    Permission.ROLES_WRITE: ("Manage roles", "roles"),
    Permission.POS_READ: ("View POS", "pos"),
    Permission.POS_WRITE: ("Manage POS", "pos"),
    Permission.KOT_READ: ("View KOT", "kot"),
    Permission.KOT_WRITE: ("Manage KOT", "kot"),
    Permission.MENU_READ: ("View menu", "menu"),
    Permission.MENU_WRITE: ("Manage menu", "menu"),
    Permission.INVENTORY_READ: ("View inventory", "inventory"),
    Permission.INVENTORY_WRITE: ("Manage inventory", "inventory"),
    Permission.CUSTOMERS_READ: ("View customers", "customers"),
    Permission.CUSTOMERS_WRITE: ("Manage customers", "customers"),
    Permission.LEADS_READ: ("View leads", "leads"),
    Permission.LEADS_WRITE: ("Manage leads", "leads"),
    Permission.COMMS_READ: ("View communications", "communications"),
    Permission.COMMS_WRITE: ("Manage communications", "communications"),
    Permission.CAMPAIGNS_READ: ("View campaigns", "campaigns"),
    Permission.CAMPAIGNS_WRITE: ("Manage campaigns", "campaigns"),
    Permission.AI_READ: ("View AI settings", "ai"),
    Permission.AI_WRITE: ("Manage AI settings", "ai"),
    Permission.AI_APPROVE: ("Approve AI actions", "ai"),
    Permission.REPORTS_READ: ("View reports", "reports"),
    Permission.SETTINGS_READ: ("View settings", "settings"),
    Permission.SETTINGS_WRITE: ("Manage settings", "settings"),
    Permission.AUDIT_READ: ("View audit logs", "audit"),
    Permission.DELIVERY_READ: ("View delivery integrations", "delivery"),
    Permission.DELIVERY_WRITE: ("Manage delivery integrations", "delivery"),
    Permission.PAYMENTS_READ: ("View payment integrations", "payments"),
    Permission.PAYMENTS_WRITE: ("Manage payment integrations", "payments"),
    Permission.BOOKING_READ: ("View table bookings", "bookings"),
    Permission.BOOKING_WRITE: ("Manage table bookings", "bookings"),
    Permission.EVENTS_READ: ("View events", "events"),
    Permission.EVENTS_WRITE: ("Manage events", "events"),
    Permission.HOUSEKEEPING_READ: ("View housekeeping", "housekeeping"),
    Permission.HOUSEKEEPING_WRITE: ("Manage housekeeping", "housekeeping"),
    Permission.PMS_READ: ("View PMS & reservations", "pms"),
    Permission.PMS_WRITE: ("Manage PMS & front desk", "pms"),
    Permission.OTA_READ: ("View OTA channel manager", "ota"),
    Permission.OTA_WRITE: ("Manage OTA integrations", "ota"),
    Permission.SPA_READ: ("View spa & activities", "spa"),
    Permission.SPA_WRITE: ("Manage spa & activities", "spa"),
    Permission.BANQUET_READ: ("View banquet & MICE", "banquet"),
    Permission.BANQUET_WRITE: ("Manage banquet & MICE", "banquet"),
}


TENANT_WIDE_ROLE_NAMES = {
    "Super Admin",
    "Owner",
    "Operations Manager",
    "Marketing Manager",
    "Accountant",
}


def user_has_permission(db, user, permission: Permission) -> bool:
    if user.is_super_admin:
        return True

    if user.role_id is None:
        return False

    from app.modules.roles.models import Permission as PermissionModel
    from app.modules.roles.models import RolePermission

    exists = (
        db.query(RolePermission.id)
        .join(PermissionModel, PermissionModel.id == RolePermission.permission_id)
        .filter(
            RolePermission.role_id == user.role_id,
            PermissionModel.code == permission.value,
        )
        .first()
    )
    return exists is not None
