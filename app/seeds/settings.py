"""Brand and outlet configuration settings."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.modules.settings.models import BrandSetting, OutletSetting
from app.seeds.base import SeedContext


def seed_settings(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand

    brand_settings = [
        ("pos_config", {"service_charge_percent": 5, "round_off_enabled": True, "default_gst": 5}),
        ("loyalty", {
            "enabled": True,
            "points_per_100": 5,
            "stay_points_per_night": 50,
            "stay_points_per_100": 2,
            "min_redeem_points": 100,
            "point_value": 1,
            "earn_on_room_charge": False,
        }),
        ("loyalty_config", {"points_per_100": 5, "min_redeem_points": 100, "point_value": 1}),
        ("comms_config", {"default_channel": "whatsapp", "auto_reply_enabled": True}),
    ]
    for key, value in brand_settings:
        existing = (
            db.query(BrandSetting)
            .filter(
                BrandSetting.tenant_id == tenant.id,
                BrandSetting.brand_id == brand.id,
                BrandSetting.setting_key == key,
            )
            .first()
        )
        if existing is None:
            db.add(
                BrandSetting(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    setting_key=key,
                    setting_value_json=json.dumps(value),
                )
            )

    andheri = ctx.outlets["Andheri West"]
    outlet_settings = [
        ("kot_config", {"auto_print": True, "kitchen_printer_ip": "192.168.1.100"}),
        ("booking_config", {"max_party_size": 20, "slot_duration_minutes": 90}),
        ("inventory_config", {"low_stock_alert": True, "auto_deduct_on_sale": True}),
    ]
    for key, value in outlet_settings:
        existing = (
            db.query(OutletSetting)
            .filter(
                OutletSetting.tenant_id == tenant.id,
                OutletSetting.outlet_id == andheri.id,
                OutletSetting.setting_key == key,
            )
            .first()
        )
        if existing is None:
            db.add(
                OutletSetting(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    outlet_id=andheri.id,
                    setting_key=key,
                    setting_value_json=json.dumps(value),
                )
            )
