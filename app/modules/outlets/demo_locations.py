"""Rewrite demo-tenant outlet names/locations when business type changes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.common.base_model import RecordStatus, apply_record_status
from app.modules.brands.models import Brand
from app.modules.outlets.models import Outlet
from app.modules.tenants.enums import BusinessType
from app.modules.tenants.models import Tenant

# Keep in sync with app.seeds.constants.DEMO_TENANT_COMPANY (avoid importing seeds here).
DEMO_TENANT_COMPANY = "Bombay Bite Collective"

# Location dummy data shown in the Topbar / Outlets UI per business profile.
OUTLET_SPECS_BY_BUSINESS_TYPE: dict[str, list[tuple[str, str]]] = {
    "resort": [
        ("Goa Beach Resort", "Goa"),
        ("Lonavala Hills Resort", "Lonavala"),
        ("Alibaug Waterfront", "Alibaug"),
        ("Mahabaleshwar Estate", "Mahabaleshwar"),
    ],
    "multichain": [
        ("Andheri West", "Andheri"),
        ("Bandra", "Bandra West"),
        ("Powai", "Powai"),
        ("BKC", "Bandra Kurla Complex"),
        ("Malad", "Malad West"),
    ],
    "restaurant": [
        ("Colaba Flagship", "Colaba"),
        ("Worli Sea Face", "Worli"),
        ("Juhu Dining Hall", "Juhu"),
        ("Lower Parel Kitchen", "Lower Parel"),
    ],
    "cafe": [
        ("Bandra Cafe Hub", "Bandra West"),
        ("Powai Express Counter", "Powai"),
        ("Andheri QSR Kiosk", "Andheri"),
        ("BKC Grab & Go", "Bandra Kurla Complex"),
    ],
}

# Canonical seed pack (stable keys for seed FK lookups).
OUTLET_SPECS = OUTLET_SPECS_BY_BUSINESS_TYPE["multichain"]


def sync_demo_outlet_locations(
    db: Session,
    tenant_id: int,
    business_type: BusinessType | str,
) -> None:
    """Align active demo outlets with the selected business profile pack.

    Existing outlet rows are reused (renamed in place) so seed FK references stay valid.
    Extra outlets beyond the pack size are deactivated; missing ones are created.
    """
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.company_name != DEMO_TENANT_COMPANY:
        return

    bt = business_type.value if isinstance(business_type, BusinessType) else str(business_type)
    specs = OUTLET_SPECS_BY_BUSINESS_TYPE.get(bt) or OUTLET_SPECS

    outlets = (
        db.query(Outlet)
        .filter(Outlet.tenant_id == tenant_id)
        .order_by(Outlet.id.asc())
        .all()
    )

    brand_id = _resolve_brand_id(db, tenant_id, outlets)
    if brand_id is None:
        return

    for index, (name, location) in enumerate(specs):
        if index < len(outlets):
            outlet = outlets[index]
        else:
            outlet = Outlet(
                tenant_id=tenant_id,
                brand_id=brand_id,
                outlet_name=name,
                location=location,
                address=f"{name}, {location}",
                manager_name=f"{location} Manager",
                manager_mobile="+919876543211",
                opening_time="09:00",
                closing_time="23:00",
                status=RecordStatus.ACTIVE,
            )
            db.add(outlet)
            outlets.append(outlet)
            db.flush()

        outlet.outlet_name = name
        outlet.location = location
        outlet.address = f"{name}, {location}"
        outlet.manager_name = f"{location} Manager"
        apply_record_status(outlet, RecordStatus.ACTIVE)

    for outlet in outlets[len(specs) :]:
        apply_record_status(outlet, RecordStatus.INACTIVE)

    db.flush()


def _resolve_brand_id(db: Session, tenant_id: int, outlets: list[Outlet]) -> int | None:
    if outlets:
        return outlets[0].brand_id
    brand = db.query(Brand).filter(Brand.tenant_id == tenant_id).order_by(Brand.id.asc()).first()
    return brand.id if brand is not None else None
