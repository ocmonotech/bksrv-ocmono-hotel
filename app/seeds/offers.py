"""Promotional offers."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.modules.offers.models import Offer, OfferStatus, OfferType
from app.seeds.base import SeedContext


def seed_offers(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    all_outlet_ids = [o.id for o in ctx.outlets.values()]

    offer_specs = [
        {
            "name": "Happy Hour 20% Off",
            "type": OfferType.HAPPY_HOUR,
            "discount": 20,
            "min_bill": 500,
            "start_time": "16:00",
            "end_time": "19:00",
            "days": ["mon", "tue", "wed", "thu", "fri"],
            "outlet_id": andheri.id,
        },
        {
            "name": "Weekend Family Feast",
            "type": OfferType.PERCENTAGE_DISCOUNT,
            "discount": 15,
            "min_bill": 1500,
            "start_time": None,
            "end_time": None,
            "days": ["sat", "sun"],
            "outlet_id": None,
        },
        {
            "name": "Birthday Special",
            "type": OfferType.BIRTHDAY,
            "discount": 25,
            "min_bill": 800,
            "start_time": None,
            "end_time": None,
            "days": None,
            "outlet_id": None,
        },
        {
            "name": "Flat ₹100 Off",
            "type": OfferType.FIXED_DISCOUNT,
            "discount": 100,
            "min_bill": 600,
            "start_time": None,
            "end_time": None,
            "days": None,
            "outlet_id": andheri.id,
        },
        {
            "name": "Loyalty Member 10% Off",
            "type": OfferType.PERCENTAGE_DISCOUNT,
            "discount": 10,
            "min_bill": 400,
            "start_time": None,
            "end_time": None,
            "days": None,
            "outlet_id": None,
        },
    ]

    offers: dict[str, Offer] = {}
    for spec in offer_specs:
        offer = (
            db.query(Offer)
            .filter(Offer.tenant_id == tenant.id, Offer.offer_name == spec["name"])
            .first()
        )
        if offer is None:
            offer = Offer(
                tenant_id=tenant.id,
                brand_id=brand.id,
                offer_name=spec["name"],
                offer_type=spec["type"],
                status=OfferStatus.ACTIVE,
                discount_value=spec["discount"],
                minimum_bill_amount=spec["min_bill"],
                applicable_outlets_json=json.dumps(all_outlet_ids if spec["outlet_id"] is None else [spec["outlet_id"]]),
                applicable_days_json=json.dumps(spec["days"]) if spec["days"] else None,
                start_time=spec["start_time"],
                end_time=spec["end_time"],
                description=f"Demo offer: {spec['name']}",
                outlet_id=spec["outlet_id"],
            )
            db.add(offer)
            db.flush()
        offers[spec["name"]] = offer

    ctx.offers = offers
