from __future__ import annotations

import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.pagination import paginate_query
from app.core.exceptions import NotFoundError
from app.modules.brands.models import Brand
from app.modules.offers.models import Offer, OfferStatus
from app.modules.offers.schemas import OfferCreate, OfferDeleteResponse, OfferRead, OfferUpdate
from app.modules.outlets.models import Outlet


def list_offers(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    brand_id: int | None = None,
    outlet_id: int | None = None,
    status: OfferStatus | None = None,
) -> tuple[list[OfferRead], int]:
    query = db.query(Offer).filter(Offer.tenant_id == tenant_id, Offer.is_active.is_(True))

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Offer.brand_id.is_(None), Offer.brand_id == brand_id))

    if outlet_id is not None:
        _validate_outlet(db, tenant_id, outlet_id)
        query = query.filter(or_(Offer.outlet_id.is_(None), Offer.outlet_id == outlet_id))

    if status is not None:
        query = query.filter(Offer.status == status)

    query = query.order_by(Offer.offer_name)
    offers, total = paginate_query(query, page, page_size)
    return [_to_read(offer) for offer in offers], total


def get_offer(db: Session, tenant_id: int, offer_id: int) -> OfferRead:
    offer = _get_entity(db, tenant_id, offer_id)
    return _to_read(offer)


def create_offer(
    db: Session,
    tenant_id: int,
    data: OfferCreate,
    default_brand_id: int | None = None,
) -> OfferRead:
    brand_id = data.brand_id or default_brand_id
    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
    if data.outlet_id is not None:
        _validate_outlet(db, tenant_id, data.outlet_id)

    offer = Offer(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        offer_name=data.offer_name,
        offer_type=data.offer_type,
        status=data.status,
        discount_value=data.discount_value,
        minimum_bill_amount=data.minimum_bill_amount,
        applicable_outlets_json=_serialize_list(data.applicable_outlets),
        applicable_days_json=_serialize_list(data.applicable_days),
        start_time=data.start_time,
        end_time=data.end_time,
        applicable_targets=data.applicable_targets,
        description=data.description,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return _to_read(offer)


def update_offer(
    db: Session,
    tenant_id: int,
    offer_id: int,
    data: OfferUpdate,
) -> OfferRead:
    offer = _get_entity(db, tenant_id, offer_id)
    payload = data.model_dump(exclude_unset=True)

    if "applicable_outlets" in payload:
        offer.applicable_outlets_json = _serialize_list(payload.pop("applicable_outlets"))
    if "applicable_days" in payload:
        offer.applicable_days_json = _serialize_list(payload.pop("applicable_days"))

    for key, value in payload.items():
        setattr(offer, key, value)

    db.commit()
    db.refresh(offer)
    return _to_read(offer)


def delete_offer(db: Session, tenant_id: int, offer_id: int) -> OfferDeleteResponse:
    offer = _get_entity(db, tenant_id, offer_id)
    offer.is_active = False
    db.commit()
    return OfferDeleteResponse(message="Offer deleted", offer_id=offer.id)


def _get_entity(db: Session, tenant_id: int, offer_id: int) -> Offer:
    offer = (
        db.query(Offer)
        .filter(Offer.id == offer_id, Offer.tenant_id == tenant_id, Offer.is_active.is_(True))
        .first()
    )
    if offer is None:
        raise NotFoundError("Offer not found")
    return offer


def _validate_brand(db: Session, tenant_id: int, brand_id: int) -> None:
    exists = (
        db.query(Brand.id)
        .filter(Brand.id == brand_id, Brand.tenant_id == tenant_id)
        .first()
    )
    if exists is None:
        raise NotFoundError("Brand not found")


def _validate_outlet(db: Session, tenant_id: int, outlet_id: int) -> None:
    exists = (
        db.query(Outlet.id)
        .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id)
        .first()
    )
    if exists is None:
        raise NotFoundError("Outlet not found")


def _serialize_list(values: list) -> str:
    return json.dumps(values)


def _deserialize_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _to_read(offer: Offer) -> OfferRead:
    payload = OfferRead.model_validate(offer)
    payload.applicable_outlets = _deserialize_list(offer.applicable_outlets_json)
    payload.applicable_days = _deserialize_list(offer.applicable_days_json)
    return payload
