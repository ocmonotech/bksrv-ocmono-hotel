"""Idempotent database seed for RestroChain OS demo data.

Run from backend/:
    python -m app.seed
"""

from __future__ import annotations

import sys

from app.core.database import SessionLocal
from app.seeds.base import SeedContext
from app.seeds.constants import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD
from app.seeds.orchestrator import run_seed

__all__ = ["SeedContext", "run_seed", "main"]


def main() -> int:
    db = SessionLocal()
    try:
        context = run_seed(db)
        print("Seed completed successfully.")
        print(f"  Tenant: {context.tenant.company_name} (id={context.tenant.id})")
        print(f"  Brand:  {context.brand.brand_name} (id={context.brand.id})")
        print(f"  Outlets: {len(context.outlets)}")
        print(f"  Menu items: {len(context.menu_items)}")
        print(f"  Customers: {len(context.customers)}")
        print(f"  Orders: {len(context.orders)}")
        print(f"  Campaigns: {len(context.campaigns)}")
        print(f"  Super Admin: {SUPER_ADMIN_EMAIL} / {SUPER_ADMIN_PASSWORD}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
