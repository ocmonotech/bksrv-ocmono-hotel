from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema

SETTING_GROUPS = (
    "billing",
    "pos",
    "kot",
    "notification",
    "whatsapp",
    "sms",
    "email",
    "ai",
    "consent_compliance",
    "spa_reminders",
    "banquet_reminders",
    "pms_reminders",
    "pms_tax",
    "pms_inventory",
    "guest_wifi",
    "loyalty",
)

COMMUNICATION_GROUPS = ("whatsapp", "sms", "email")
AI_GROUP = "ai"
SPA_REMINDERS_GROUP = "spa_reminders"
BANQUET_REMINDERS_GROUP = "banquet_reminders"
PMS_REMINDERS_GROUP = "pms_reminders"
PMS_TAX_GROUP = "pms_tax"
PMS_INVENTORY_GROUP = "pms_inventory"
GUEST_WIFI_GROUP = "guest_wifi"


class SettingValueUpdate(BaseModel):
    setting_key: str = Field(min_length=1, max_length=64)
    value: dict = Field(default_factory=dict)


class SettingEntryRead(ORMSchema, TimestampSchema):
    id: int | None = None
    setting_key: str
    value: dict = {}


class BrandSettingsRead(BaseModel):
    brand_id: int
    settings: dict[str, dict] = Field(default_factory=dict)


class OutletSettingsRead(BaseModel):
    outlet_id: int
    brand_id: int
    settings: dict[str, dict] = Field(default_factory=dict)


class CommunicationSettingsRead(BaseModel):
    brand_id: int | None = None
    outlet_id: int | None = None
    whatsapp: dict = Field(default_factory=dict)
    sms: dict = Field(default_factory=dict)
    email: dict = Field(default_factory=dict)


class CommunicationSettingsUpdate(BaseModel):
    brand_id: int | None = None
    outlet_id: int | None = None
    whatsapp: dict | None = None
    sms: dict | None = None
    email: dict | None = None


class AiSettingsRead(BaseModel):
    brand_id: int | None = None
    outlet_id: int | None = None
    ai: dict = Field(default_factory=dict)


class AiSettingsUpdate(BaseModel):
    brand_id: int | None = None
    outlet_id: int | None = None
    ai: dict = Field(default_factory=dict)


class ModuleReminderSettings(BaseModel):
    enabled: bool = True
    hours_before: int = Field(default=24, ge=1, le=168)
    window_minutes: int = Field(default=30, ge=5, le=240)
    send_sms: bool = True
    send_email: bool = True
    send_whatsapp: bool = True


class ReminderSettingsRead(BaseModel):
    outlet_id: int
    spa: ModuleReminderSettings
    banquet: ModuleReminderSettings
    pms: ModuleReminderSettings


class ReminderSettingsUpdate(BaseModel):
    outlet_id: int
    spa: ModuleReminderSettings | None = None
    banquet: ModuleReminderSettings | None = None
    pms: ModuleReminderSettings | None = None


class PmsTaxSettingsRead(BaseModel):
    outlet_id: int
    tax_percent: float
    tax_label: str
    require_zero_balance_checkout: bool


class PmsTaxSettingsUpdate(BaseModel):
    outlet_id: int
    tax_percent: float = Field(default=12.0, ge=0, le=100)
    tax_label: str = Field(default="GST", min_length=1, max_length=64)
    require_zero_balance_checkout: bool = False


class OrganizationSettingsRead(BaseModel):
    tenant_id: int
    company_name: str
    business_type: str


class OrganizationSettingsUpdate(BaseModel):
    business_type: str = Field(pattern="^(resort|multichain|cafe|restaurant)$")
