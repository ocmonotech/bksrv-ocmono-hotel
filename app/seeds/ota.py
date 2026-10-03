"""OTA channel integrations and room type mappings."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.modules.delivery.models import IntegrationStatus
from app.modules.housekeeping.models import RoomType
from app.modules.ota.models import OtaPlatform, OtaRoomTypeMapping, OutletOtaIntegration
from app.seeds.base import SeedContext


def seed_ota(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant

    room_types = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant.id, RoomType.is_active.is_(True))
        .order_by(RoomType.name)
        .all()
    )
    if not room_types:
        return

    type_by_name = {rt.name: rt for rt in room_types}

    andheri = ctx.outlets.get("Andheri West")
    bandra = ctx.outlets.get("Bandra")

    outlet_specs = []
    if andheri:
        outlet_specs += [
            {
                "outlet": andheri,
                "platform": OtaPlatform.BOOKING_COM,
                "external_property_id": "BCOM-ANDHERI-001",
                "is_enabled": True,
                "status": IntegrationStatus.ACTIVE,
                "mappings": [
                    ("STD", "Standard", "Standard"),
                    ("DLX", "Deluxe", "Deluxe"),
                    ("STE", "Suite", "Suite"),
                ],
            },
            {
                "outlet": andheri,
                "platform": OtaPlatform.MMT,
                "external_property_id": "MMT-ANDHERI-001",
                "is_enabled": True,
                "status": IntegrationStatus.ACTIVE,
                "mappings": [
                    ("standard", "Standard Room", "Standard"),
                    ("suite", "Suite Room", "Suite"),
                ],
            },
            {
                "outlet": andheri,
                "platform": OtaPlatform.EXPEDIA,
                "external_property_id": "EXP-ANDHERI-001",
                "is_enabled": True,
                "status": IntegrationStatus.ACTIVE,
                "mappings": [
                    ("STD", "Standard Room", "Standard"),
                    ("DLX", "Deluxe Room", "Deluxe"),
                    ("STE", "Suite", "Suite"),
                ],
            },
        ]
    if bandra:
        outlet_specs += [
            {
                "outlet": bandra,
                "platform": OtaPlatform.BOOKING_COM,
                "external_property_id": "BCOM-BANDRA-001",
                "is_enabled": True,
                "status": IntegrationStatus.ACTIVE,
                "mappings": [
                    ("STD", "Standard", "Standard"),
                    ("STE", "Suite", "Suite"),
                ],
            },
            {
                "outlet": bandra,
                "platform": OtaPlatform.MMT,
                "external_property_id": "MMT-BANDRA-001",
                "is_enabled": False,
                "status": IntegrationStatus.INACTIVE,
                "mappings": [
                    ("standard", "Standard Room", "Standard"),
                ],
            },
        ]

    for spec in outlet_specs:
        outlet = spec["outlet"]
        existing = (
            db.query(OutletOtaIntegration)
            .filter(
                OutletOtaIntegration.tenant_id == tenant.id,
                OutletOtaIntegration.outlet_id == outlet.id,
                OutletOtaIntegration.platform == spec["platform"],
            )
            .first()
        )
        if existing is not None:
            continue

        integration = OutletOtaIntegration(
            tenant_id=tenant.id,
            brand_id=ctx.brand.id,
            outlet_id=outlet.id,
            platform=spec["platform"],
            external_property_id=spec["external_property_id"],
            status=spec["status"],
            is_enabled=spec["is_enabled"],
            auto_confirm_reservations=True,
            auto_push_availability=True,
            webhook_token=uuid.uuid4().hex,
            config_json=json.dumps({"demo": True}),
        )
        db.add(integration)
        db.flush()

        for external_id, external_name, local_name in spec["mappings"]:
            room_type = type_by_name.get(local_name)
            if room_type is None:
                continue
            db.add(
                OtaRoomTypeMapping(
                    tenant_id=tenant.id,
                    brand_id=ctx.brand.id,
                    integration_id=integration.id,
                    external_room_type_id=external_id,
                    external_room_type_name=external_name,
                    room_type_id=room_type.id,
                )
            )

    db.flush()
