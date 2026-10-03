from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.modules.brands.models import Brand
from app.modules.outlets.demo_locations import sync_demo_outlet_locations
from app.modules.outlets.models import Outlet
from app.modules.tenants.enums import BusinessType
from app.modules.settings.models import BrandSetting, OutletSetting
from app.modules.settings.schemas import (
    AI_GROUP,
    BANQUET_REMINDERS_GROUP,
    COMMUNICATION_GROUPS,
    AiSettingsRead,
    AiSettingsUpdate,
    BrandSettingsRead,
    CommunicationSettingsRead,
    CommunicationSettingsUpdate,
    GUEST_WIFI_GROUP,
    ModuleReminderSettings,
    OrganizationSettingsRead,
    OrganizationSettingsUpdate,
    OutletSettingsRead,
    PMS_INVENTORY_GROUP,
    PMS_REMINDERS_GROUP,
    PMS_TAX_GROUP,
    PmsTaxSettingsRead,
    PmsTaxSettingsUpdate,
    ReminderSettingsRead,
    ReminderSettingsUpdate,
    SETTING_GROUPS,
    SPA_REMINDERS_GROUP,
    SettingValueUpdate,
)
from app.modules.tenants.models import Tenant


DEFAULT_SETTINGS: dict[str, dict] = {
    "billing": {
        "currency": "INR",
        "tax_inclusive": False,
        "service_charge_percent": 0,
        "round_off_enabled": True,
        "print_bill_on_payment": True,
    },
    "pos": {
        "default_order_type": "dine_in",
        "allow_table_merge": True,
        "require_customer_on_bill": False,
        "auto_send_kot": True,
        "terminal_payment_enabled": True,
        "click_collect": {
            "enabled": True,
            "open": "08:00",
            "close": "22:00",
            "slot_minutes": 15,
            "prep_sla_minutes": 20,
            "min_lead_minutes": 20,
            "horizon_hours": 4,
        },
    },
    "kot": {
        "auto_print": False,
        "group_by_preparation_area": True,
        "notify_on_ready": True,
    },
    "notification": {
        "email_alerts_enabled": False,
        "sms_alerts_enabled": False,
        "push_alerts_enabled": False,
        "manager_escalation_minutes": 15,
    },
    "whatsapp": {
        "enabled": True,
        "provider": "mock",
        "sender_id": "",
        "default_template_id": None,
        "webhook_url": "",
    },
    "sms": {
        "enabled": True,
        "provider": "mock",
        "sender_id": "",
        "dlt_template_required": True,
    },
    "email": {
        "enabled": True,
        "provider": "mock",
        "from_name": "",
        "from_email": "",
        "reply_to": "",
    },
    "ai": {
        "enabled": False,
        "default_provider": "openai",
        "default_model": "gpt-4o-mini",
        "human_approval_required": True,
        "monthly_budget": 25000,
        "usage_alert_percent": 80,
    },
    "consent_compliance": {
        "require_whatsapp_consent": True,
        "require_sms_consent": True,
        "require_email_consent": True,
        "store_consent_proof": True,
        "privacy_policy_url": "",
        "terms_url": "",
    },
    "spa_reminders": {
        "enabled": True,
        "hours_before": 24,
        "window_minutes": 30,
        "send_sms": True,
        "send_email": True,
        "send_whatsapp": True,
    },
    "banquet_reminders": {
        "enabled": True,
        "hours_before": 24,
        "window_minutes": 30,
        "send_sms": True,
        "send_email": True,
        "send_whatsapp": True,
    },
    "pms_reminders": {
        "enabled": True,
        "hours_before": 24,
        "window_minutes": 30,
        "send_sms": True,
        "send_email": True,
        "send_whatsapp": True,
    },
    "pms_tax": {
        "tax_percent": 12.0,
        "tax_label": "GST",
        "require_zero_balance_checkout": False,
    },
    "pms_inventory": {
        "cells": {},
    },
    "guest_wifi": {
        "ssid": "",
        "password": "",
        "notes": "",
    },
    "loyalty": {
        "enabled": True,
        "points_per_100": 5,
        "stay_points_per_night": 50,
        "stay_points_per_100": 2,
        "min_redeem_points": 100,
        "point_value": 1,
        "earn_on_room_charge": False,
    },
}


def get_brand_settings(db: Session, tenant_id: int, brand_id: int) -> BrandSettingsRead:
    _get_brand(db, tenant_id, brand_id)
    stored = _load_brand_settings(db, tenant_id, brand_id)
    merged = _merge_with_defaults(stored)
    return BrandSettingsRead(brand_id=brand_id, settings=merged)


def update_brand_setting(
    db: Session,
    tenant_id: int,
    brand_id: int,
    data: SettingValueUpdate,
) -> BrandSettingsRead:
    _get_brand(db, tenant_id, brand_id)
    _validate_setting_key(data.setting_key)
    _upsert_brand_setting(db, tenant_id, brand_id, data.setting_key, data.value)
    return get_brand_settings(db, tenant_id, brand_id)


def get_outlet_settings(db: Session, tenant_id: int, outlet_id: int) -> OutletSettingsRead:
    outlet = _get_outlet(db, tenant_id, outlet_id)
    stored = _load_outlet_settings(db, tenant_id, outlet_id)
    merged = _merge_with_defaults(stored)
    return OutletSettingsRead(outlet_id=outlet.id, brand_id=outlet.brand_id, settings=merged)


def update_outlet_setting(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    data: SettingValueUpdate,
) -> OutletSettingsRead:
    outlet = _get_outlet(db, tenant_id, outlet_id)
    _validate_setting_key(data.setting_key)
    _upsert_outlet_setting(
        db,
        tenant_id,
        outlet.brand_id,
        outlet_id,
        data.setting_key,
        data.value,
    )
    return get_outlet_settings(db, tenant_id, outlet_id)


def get_communication_settings(
    db: Session,
    tenant_id: int,
    brand_id: int | None = None,
    outlet_id: int | None = None,
    default_brand_id: int | None = None,
) -> CommunicationSettingsRead:
    resolved_brand_id = brand_id or default_brand_id
    if outlet_id is not None:
        outlet = _get_outlet(db, tenant_id, outlet_id)
        resolved_brand_id = outlet.brand_id

    if resolved_brand_id is None:
        raise NotFoundError("brand_id is required when outlet_id is not provided")

    brand_settings = _load_brand_settings(db, tenant_id, resolved_brand_id)
    outlet_settings = _load_outlet_settings(db, tenant_id, outlet_id) if outlet_id else {}

    result: dict[str, dict] = {}
    for key in COMMUNICATION_GROUPS:
        result[key] = _deep_merge(
            DEFAULT_SETTINGS.get(key, {}),
            brand_settings.get(key, {}),
            outlet_settings.get(key, {}),
        )

    return CommunicationSettingsRead(
        brand_id=resolved_brand_id,
        outlet_id=outlet_id,
        whatsapp=result["whatsapp"],
        sms=result["sms"],
        email=result["email"],
    )


def update_communication_settings(
    db: Session,
    tenant_id: int,
    data: CommunicationSettingsUpdate,
    default_brand_id: int | None = None,
) -> CommunicationSettingsRead:
    brand_id = data.brand_id or default_brand_id
    outlet_id = data.outlet_id

    if outlet_id is not None:
        outlet = _get_outlet(db, tenant_id, outlet_id)
        brand_id = outlet.brand_id
        if data.whatsapp is not None:
            _upsert_outlet_setting(db, tenant_id, brand_id, outlet_id, "whatsapp", data.whatsapp)
        if data.sms is not None:
            _upsert_outlet_setting(db, tenant_id, brand_id, outlet_id, "sms", data.sms)
        if data.email is not None:
            _upsert_outlet_setting(db, tenant_id, brand_id, outlet_id, "email", data.email)
    else:
        if brand_id is None:
            raise NotFoundError("brand_id is required")
        _get_brand(db, tenant_id, brand_id)
        if data.whatsapp is not None:
            _upsert_brand_setting(db, tenant_id, brand_id, "whatsapp", data.whatsapp)
        if data.sms is not None:
            _upsert_brand_setting(db, tenant_id, brand_id, "sms", data.sms)
        if data.email is not None:
            _upsert_brand_setting(db, tenant_id, brand_id, "email", data.email)

    return get_communication_settings(
        db,
        tenant_id,
        brand_id=brand_id,
        outlet_id=outlet_id,
    )


def get_ai_settings(
    db: Session,
    tenant_id: int,
    brand_id: int | None = None,
    outlet_id: int | None = None,
    default_brand_id: int | None = None,
) -> AiSettingsRead:
    resolved_brand_id = brand_id or default_brand_id
    if outlet_id is not None:
        outlet = _get_outlet(db, tenant_id, outlet_id)
        resolved_brand_id = outlet.brand_id

    if resolved_brand_id is None:
        raise NotFoundError("brand_id is required when outlet_id is not provided")

    brand_settings = _load_brand_settings(db, tenant_id, resolved_brand_id)
    outlet_settings = _load_outlet_settings(db, tenant_id, outlet_id) if outlet_id else {}

    ai_settings = _deep_merge(
        DEFAULT_SETTINGS.get(AI_GROUP, {}),
        brand_settings.get(AI_GROUP, {}),
        outlet_settings.get(AI_GROUP, {}),
    )

    return AiSettingsRead(
        brand_id=resolved_brand_id,
        outlet_id=outlet_id,
        ai=ai_settings,
    )


def update_ai_settings(
    db: Session,
    tenant_id: int,
    data: AiSettingsUpdate,
    default_brand_id: int | None = None,
) -> AiSettingsRead:
    brand_id = data.brand_id or default_brand_id
    outlet_id = data.outlet_id

    if outlet_id is not None:
        outlet = _get_outlet(db, tenant_id, outlet_id)
        brand_id = outlet.brand_id
        _upsert_outlet_setting(db, tenant_id, brand_id, outlet_id, AI_GROUP, data.ai)
    else:
        if brand_id is None:
            raise NotFoundError("brand_id is required")
        _get_brand(db, tenant_id, brand_id)
        _upsert_brand_setting(db, tenant_id, brand_id, AI_GROUP, data.ai)

    return get_ai_settings(db, tenant_id, brand_id=brand_id, outlet_id=outlet_id)


def get_reminder_settings(db: Session, tenant_id: int, outlet_id: int) -> ReminderSettingsRead:
    outlet = _get_outlet(db, tenant_id, outlet_id)
    return ReminderSettingsRead(
        outlet_id=outlet.id,
        spa=_module_reminder_settings(db, tenant_id, outlet_id, SPA_REMINDERS_GROUP),
        banquet=_module_reminder_settings(db, tenant_id, outlet_id, BANQUET_REMINDERS_GROUP),
        pms=_module_reminder_settings(db, tenant_id, outlet_id, PMS_REMINDERS_GROUP),
    )


def update_reminder_settings(
    db: Session,
    tenant_id: int,
    data: ReminderSettingsUpdate,
) -> ReminderSettingsRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    if data.spa is not None:
        _upsert_outlet_setting(
            db,
            tenant_id,
            outlet.brand_id,
            outlet.id,
            SPA_REMINDERS_GROUP,
            data.spa.model_dump(),
        )
    if data.banquet is not None:
        _upsert_outlet_setting(
            db,
            tenant_id,
            outlet.brand_id,
            outlet.id,
            BANQUET_REMINDERS_GROUP,
            data.banquet.model_dump(),
        )
    if data.pms is not None:
        _upsert_outlet_setting(
            db,
            tenant_id,
            outlet.brand_id,
            outlet.id,
            PMS_REMINDERS_GROUP,
            data.pms.model_dump(),
        )
    return get_reminder_settings(db, tenant_id, outlet.id)


def get_spa_reminder_config(db: Session, tenant_id: int, outlet_id: int) -> dict:
    return _module_reminder_config(db, tenant_id, outlet_id, SPA_REMINDERS_GROUP, "spa")


def get_banquet_reminder_config(db: Session, tenant_id: int, outlet_id: int) -> dict:
    return _module_reminder_config(db, tenant_id, outlet_id, BANQUET_REMINDERS_GROUP, "banquet")


def get_pms_reminder_config(db: Session, tenant_id: int, outlet_id: int) -> dict:
    return _module_reminder_config(db, tenant_id, outlet_id, PMS_REMINDERS_GROUP, "pms")


def get_guest_wifi_config(db: Session, tenant_id: int, outlet_id: int) -> dict:
    stored = _load_outlet_settings(db, tenant_id, outlet_id)
    brand = _get_outlet(db, tenant_id, outlet_id)
    brand_stored = _load_brand_settings(db, tenant_id, brand.brand_id) if brand.brand_id else {}
    merged = _deep_merge(
        DEFAULT_SETTINGS.get(GUEST_WIFI_GROUP, {}),
        brand_stored.get(GUEST_WIFI_GROUP, {}),
    )
    merged = _deep_merge(merged, stored.get(GUEST_WIFI_GROUP, {}))
    return {
        "ssid": str(merged.get("ssid") or ""),
        "password": str(merged.get("password") or ""),
        "notes": str(merged.get("notes") or ""),
    }


def get_pms_inventory_overrides(db: Session, tenant_id: int, outlet_id: int) -> dict[str, dict]:
    stored = _load_outlet_settings(db, tenant_id, outlet_id)
    group = stored.get(PMS_INVENTORY_GROUP, {})
    cells = group.get("cells", {}) if isinstance(group, dict) else {}
    return cells if isinstance(cells, dict) else {}


def _inventory_cell_is_empty(cell: dict) -> bool:
    if cell.get("stop_sell"):
        return False
    if "rate" in cell:
        return False
    if cell.get("cta") or cell.get("ctd"):
        return False
    if cell.get("min_stay") or cell.get("max_stay"):
        return False
    return True


def upsert_pms_inventory_override(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    room_type_id: int,
    on_date: str,
    *,
    stop_sell: bool | None = None,
    rate: float | None = None,
    clear_rate: bool = False,
    cta: bool | None = None,
    ctd: bool | None = None,
    min_stay: int | None = None,
    max_stay: int | None = None,
    clear_min_stay: bool = False,
    clear_max_stay: bool = False,
) -> dict[str, dict]:
    outlet = _get_outlet(db, tenant_id, outlet_id)
    cells = dict(get_pms_inventory_overrides(db, tenant_id, outlet_id))
    key = f"{room_type_id}:{on_date}"
    current = dict(cells.get(key) or {})
    if stop_sell is not None:
        current["stop_sell"] = bool(stop_sell)
    if clear_rate:
        current.pop("rate", None)
    elif rate is not None:
        current["rate"] = float(rate)
    if cta is not None:
        if cta:
            current["cta"] = True
        else:
            current.pop("cta", None)
    if ctd is not None:
        if ctd:
            current["ctd"] = True
        else:
            current.pop("ctd", None)
    if clear_min_stay:
        current.pop("min_stay", None)
    elif min_stay is not None:
        if int(min_stay) <= 0:
            current.pop("min_stay", None)
        else:
            current["min_stay"] = int(min_stay)
    if clear_max_stay:
        current.pop("max_stay", None)
    elif max_stay is not None:
        if int(max_stay) <= 0:
            current.pop("max_stay", None)
        else:
            current["max_stay"] = int(max_stay)
    if _inventory_cell_is_empty(current):
        cells.pop(key, None)
    else:
        cells[key] = current
    _upsert_outlet_setting(
        db,
        tenant_id,
        outlet.brand_id,
        outlet.id,
        PMS_INVENTORY_GROUP,
        {"cells": cells},
    )
    return cells


def get_pms_tax_config(db: Session, tenant_id: int, outlet_id: int) -> dict:
    stored = _load_outlet_settings(db, tenant_id, outlet_id)
    brand_id = None
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is not None:
        brand_id = outlet.brand_id
        brand_stored = _load_brand_settings(db, tenant_id, brand_id) if brand_id else {}
        brand_group = brand_stored.get(PMS_TAX_GROUP, {})
    else:
        brand_group = {}
    merged = _deep_merge(DEFAULT_SETTINGS.get(PMS_TAX_GROUP, {}), brand_group)
    merged = _deep_merge(merged, stored.get(PMS_TAX_GROUP, {}))
    return {
        "tax_percent": float(merged.get("tax_percent", 12.0)),
        "tax_label": str(merged.get("tax_label", "GST")),
        "require_zero_balance_checkout": bool(merged.get("require_zero_balance_checkout", False)),
    }


def get_pms_tax_settings(db: Session, tenant_id: int, outlet_id: int) -> PmsTaxSettingsRead:
    outlet = _get_outlet(db, tenant_id, outlet_id)
    config = get_pms_tax_config(db, tenant_id, outlet_id)
    return PmsTaxSettingsRead(outlet_id=outlet.id, **config)


def update_pms_tax_settings(
    db: Session,
    tenant_id: int,
    data: PmsTaxSettingsUpdate,
) -> PmsTaxSettingsRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    _upsert_outlet_setting(
        db,
        tenant_id,
        outlet.brand_id,
        outlet.id,
        PMS_TAX_GROUP,
        {
            "tax_percent": data.tax_percent,
            "tax_label": data.tax_label.strip(),
            "require_zero_balance_checkout": data.require_zero_balance_checkout,
        },
    )
    db.commit()
    return get_pms_tax_settings(db, tenant_id, outlet.id)


def _module_reminder_settings(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    group: str,
) -> ModuleReminderSettings:
    if group == SPA_REMINDERS_GROUP:
        kind = "spa"
    elif group == PMS_REMINDERS_GROUP:
        kind = "pms"
    else:
        kind = "banquet"
    return ModuleReminderSettings.model_validate(
        _module_reminder_config(db, tenant_id, outlet_id, group, kind)
    )


def _module_reminder_config(db: Session, tenant_id: int, outlet_id: int, group: str, kind: str) -> dict:
    from app.core.config import settings as app_settings

    stored = _load_outlet_settings(db, tenant_id, outlet_id)
    merged = _deep_merge(DEFAULT_SETTINGS.get(group, {}), stored.get(group, {}))
    if kind == "spa":
        merged.setdefault("hours_before", app_settings.spa_reminder_hours_before)
        merged.setdefault("window_minutes", app_settings.spa_reminder_window_minutes)
    elif kind == "pms":
        merged.setdefault("hours_before", app_settings.pms_reminder_hours_before)
        merged.setdefault("window_minutes", app_settings.pms_reminder_window_minutes)
    else:
        merged.setdefault("hours_before", app_settings.banquet_reminder_hours_before)
        merged.setdefault("window_minutes", app_settings.banquet_reminder_window_minutes)
    return merged


def _load_brand_settings(db: Session, tenant_id: int, brand_id: int) -> dict[str, dict]:
    rows = (
        db.query(BrandSetting)
        .filter(
            BrandSetting.tenant_id == tenant_id,
            BrandSetting.brand_id == brand_id,
            BrandSetting.is_active.is_(True),
        )
        .all()
    )
    return {row.setting_key: _parse_json(row.setting_value_json) for row in rows}


def _load_outlet_settings(db: Session, tenant_id: int, outlet_id: int) -> dict[str, dict]:
    rows = (
        db.query(OutletSetting)
        .filter(
            OutletSetting.tenant_id == tenant_id,
            OutletSetting.outlet_id == outlet_id,
            OutletSetting.is_active.is_(True),
        )
        .all()
    )
    return {row.setting_key: _parse_json(row.setting_value_json) for row in rows}


def _upsert_brand_setting(
    db: Session,
    tenant_id: int,
    brand_id: int,
    setting_key: str,
    value: dict,
) -> BrandSetting:
    row = (
        db.query(BrandSetting)
        .filter(
            BrandSetting.tenant_id == tenant_id,
            BrandSetting.brand_id == brand_id,
            BrandSetting.setting_key == setting_key,
        )
        .first()
    )
    if row is None:
        row = BrandSetting(
            tenant_id=tenant_id,
            brand_id=brand_id,
            setting_key=setting_key,
            setting_value_json=json.dumps(value),
        )
        db.add(row)
    else:
        row.setting_value_json = json.dumps(value)

    db.commit()
    db.refresh(row)
    return row


def _upsert_outlet_setting(
    db: Session,
    tenant_id: int,
    brand_id: int,
    outlet_id: int,
    setting_key: str,
    value: dict,
) -> OutletSetting:
    row = (
        db.query(OutletSetting)
        .filter(
            OutletSetting.tenant_id == tenant_id,
            OutletSetting.outlet_id == outlet_id,
            OutletSetting.setting_key == setting_key,
        )
        .first()
    )
    if row is None:
        row = OutletSetting(
            tenant_id=tenant_id,
            brand_id=brand_id,
            outlet_id=outlet_id,
            setting_key=setting_key,
            setting_value_json=json.dumps(value),
        )
        db.add(row)
    else:
        row.setting_value_json = json.dumps(value)

    db.commit()
    db.refresh(row)
    return row


def _merge_with_defaults(stored: dict[str, dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for key in SETTING_GROUPS:
        merged[key] = _deep_merge(DEFAULT_SETTINGS.get(key, {}), stored.get(key, {}))
    return merged


def _deep_merge(*dicts: dict) -> dict:
    result: dict = {}
    for current in dicts:
        for key, value in current.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
    return result


def _validate_setting_key(setting_key: str) -> None:
    if setting_key not in SETTING_GROUPS:
        raise AppError(f"Unknown setting group: {setting_key}", code="invalid_setting_key")


def _parse_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _get_brand(db: Session, tenant_id: int, brand_id: int) -> Brand:
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if brand is None:
        raise NotFoundError("Brand not found")
    return brand


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def get_organization_settings(db: Session, tenant_id: int) -> OrganizationSettingsRead:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    return OrganizationSettingsRead(
        tenant_id=tenant.id,
        company_name=tenant.company_name,
        business_type=tenant.business_type.value,
    )


def update_organization_settings(
    db: Session,
    tenant_id: int,
    data: OrganizationSettingsUpdate,
) -> OrganizationSettingsRead:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    tenant.business_type = BusinessType(data.business_type)
    sync_demo_outlet_locations(db, tenant_id, tenant.business_type)
    db.commit()
    db.refresh(tenant)
    return OrganizationSettingsRead(
        tenant_id=tenant.id,
        company_name=tenant.company_name,
        business_type=tenant.business_type.value,
    )
