from __future__ import annotations

from sqlalchemy.orm import Session

from app.common.base_model import RecordStatus, apply_record_status
from app.core.exceptions import NotFoundError
from app.modules.brands.models import Brand
from app.modules.brands.schemas import BrandCreate, BrandRead, BrandUpdate


def list_brands(db: Session, tenant_id: int) -> list[BrandRead]:
    brands = (
        db.query(Brand)
        .filter(Brand.tenant_id == tenant_id)
        .order_by(Brand.brand_name)
        .all()
    )
    return [BrandRead.model_validate(brand) for brand in brands]


def get_brand(db: Session, tenant_id: int, brand_id: int) -> BrandRead:
    brand = _get_brand_entity(db, tenant_id, brand_id)
    return BrandRead.model_validate(brand)


def create_brand(db: Session, tenant_id: int, data: BrandCreate) -> BrandRead:
    brand = Brand(tenant_id=tenant_id, **data.model_dump(), status=RecordStatus.ACTIVE)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return BrandRead.model_validate(brand)


def update_brand(db: Session, tenant_id: int, brand_id: int, data: BrandUpdate) -> BrandRead:
    brand = _get_brand_entity(db, tenant_id, brand_id)
    payload = data.model_dump(exclude_unset=True)
    status = payload.pop("status", None)
    for key, value in payload.items():
        setattr(brand, key, value)
    if status is not None:
        apply_record_status(brand, status)

    db.commit()
    db.refresh(brand)
    return BrandRead.model_validate(brand)


def _get_brand_entity(db: Session, tenant_id: int, brand_id: int) -> Brand:
    brand = (
        db.query(Brand)
        .filter(Brand.id == brand_id, Brand.tenant_id == tenant_id)
        .first()
    )
    if brand is None:
        raise NotFoundError("Brand not found")
    return brand
