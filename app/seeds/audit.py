"""Sample audit log entries."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditAction, AuditLog
from app.seeds.base import SeedContext
from app.seeds.constants import SUPER_ADMIN_EMAIL


def seed_audit(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    if admin is None:
        return

    log_specs = [
        (AuditAction.USER_LOGIN.value, "auth", "user", admin.id, None, {"email": admin.email}),
        (AuditAction.CAMPAIGN_LAUNCHED.value, "campaigns", "campaign", None, None, {"name": "Weekend Welcome Blast"}),
        (AuditAction.STOCK_SALE.value, "inventory", "stock_ledger", None, {"qty": 2.5}, {"qty": 2.5}),
        (AuditAction.OFFER_UPDATED.value, "offers", "offer", None, None, {"name": "Happy Hour 20% Off"}),
        (AuditAction.STOCK_ADJUSTED.value, "inventory", "stock_ledger", None, {"qty": 5.0}, {"qty": 10.0}),
        (AuditAction.BILL_CANCELLED.value, "pos", "bill", None, {"bill_number": "BILL-AND-X"}, {"reason": "Billing error"}),
        (AuditAction.USER_LOGOUT.value, "auth", "user", admin.id, None, {"email": admin.email}),
    ]

    for action, module, record_type, record_id, old_data, new_data in log_specs:
        existing = (
            db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == tenant.id,
                AuditLog.action == action,
                AuditLog.module_name == module,
                AuditLog.record_type == record_type,
            )
            .first()
        )
        if existing is not None:
            continue
        db.add(
            AuditLog(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                user_id=admin.id,
                action=action,
                module_name=module,
                record_type=record_type,
                record_id=record_id,
                old_data_json=json.dumps(old_data) if old_data else None,
                new_data_json=json.dumps(new_data) if new_data else None,
                ip_address="127.0.0.1",
                user_agent="RestroChain-Seed/1.0",
            )
        )
