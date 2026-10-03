from __future__ import annotations

from sqlalchemy.orm import Session

from app.common.base_model import RecordStatus, apply_record_status
from app.common.pagination import paginate_query
from app.core.exceptions import NotFoundError
from app.modules.brands.models import Brand
from app.modules.outlets.models import Outlet
from app.modules.outlets.schemas import OutletCreate, OutletRead, OutletUpdate


def list_outlets(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    brand_id: int | None = None,
) -> tuple[list[OutletRead], int]:
    query = (
        db.query(Outlet)
        .filter(Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True))
        .order_by(Outlet.outlet_name)
    )
    if brand_id is not None:
        query = query.filter(Outlet.brand_id == brand_id)
    items, total = paginate_query(query, page, page_size)
    return [OutletRead.model_validate(item) for item in items], total


def list_outlets_by_brand(db: Session, tenant_id: int, brand_id: int) -> list[OutletRead]:
    _validate_brand(db, tenant_id, brand_id)
    outlets = (
        db.query(Outlet)
        .filter(
            Outlet.tenant_id == tenant_id,
            Outlet.brand_id == brand_id,
            Outlet.is_active.is_(True),
        )
        .order_by(Outlet.outlet_name)
        .all()
    )
    return [OutletRead.model_validate(outlet) for outlet in outlets]


def get_outlet(db: Session, tenant_id: int, outlet_id: int) -> OutletRead:
    outlet = _get_outlet_entity(db, tenant_id, outlet_id)
    return OutletRead.model_validate(outlet)


def create_outlet(db: Session, tenant_id: int, data: OutletCreate) -> OutletRead:
    _validate_brand(db, tenant_id, data.brand_id)
    outlet = Outlet(tenant_id=tenant_id, **data.model_dump(), status=RecordStatus.ACTIVE)
    db.add(outlet)
    db.commit()
    db.refresh(outlet)
    return OutletRead.model_validate(outlet)


def update_outlet(db: Session, tenant_id: int, outlet_id: int, data: OutletUpdate) -> OutletRead:
    outlet = _get_outlet_entity(db, tenant_id, outlet_id)
    payload = data.model_dump(exclude_unset=True)
    status = payload.pop("status", None)
    for key, value in payload.items():
        setattr(outlet, key, value)
    if status is not None:
        apply_record_status(outlet, status)

    db.commit()
    db.refresh(outlet)
    return OutletRead.model_validate(outlet)


def delete_outlet(db: Session, tenant_id: int, outlet_id: int) -> None:
    outlet = _get_outlet_entity(db, tenant_id, outlet_id)
    apply_record_status(outlet, RecordStatus.INACTIVE)
    db.commit()


def activate_outlet(db: Session, tenant_id: int, outlet_id: int) -> OutletRead:
    outlet = _get_outlet_entity(db, tenant_id, outlet_id)
    apply_record_status(outlet, RecordStatus.ACTIVE)
    db.commit()
    db.refresh(outlet)
    return OutletRead.model_validate(outlet)


def deactivate_outlet(db: Session, tenant_id: int, outlet_id: int) -> OutletRead:
    outlet = _get_outlet_entity(db, tenant_id, outlet_id)
    apply_record_status(outlet, RecordStatus.INACTIVE)
    db.commit()
    db.refresh(outlet)
    return OutletRead.model_validate(outlet)


def _get_outlet_entity(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id)
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _validate_brand(db: Session, tenant_id: int, brand_id: int) -> Brand:
    brand = (
        db.query(Brand)
        .filter(Brand.id == brand_id, Brand.tenant_id == tenant_id)
        .first()
    )
    if brand is None:
        raise NotFoundError("Brand not found")
    return brand
