from __future__ import annotations

from app.core.config import settings
from app.modules.ota.models import OtaPlatform
from app.modules.ota.providers.base import BaseOtaProvider
from app.modules.ota.providers.booking_com import BookingComHttpProvider
from app.modules.ota.providers.expedia import ExpediaHttpProvider
from app.modules.ota.providers.mmt import MmtHttpProvider
from app.modules.ota.providers.mock import (
    MockBookingComProvider,
    MockExpediaProvider,
    MockMmtProvider,
)

_MOCK_ADAPTERS: dict[OtaPlatform, BaseOtaProvider] = {
    OtaPlatform.BOOKING_COM: MockBookingComProvider(),
    OtaPlatform.MMT: MockMmtProvider(),
    OtaPlatform.EXPEDIA: MockExpediaProvider(),
}

_HTTP_ADAPTERS: dict[OtaPlatform, BaseOtaProvider] = {
    OtaPlatform.BOOKING_COM: BookingComHttpProvider(),
    OtaPlatform.MMT: MmtHttpProvider(),
    OtaPlatform.EXPEDIA: ExpediaHttpProvider(),
}

PLATFORM_LABELS: dict[OtaPlatform, tuple[str, str]] = {
    OtaPlatform.BOOKING_COM: ("Booking.com", "Hotel reservations from Booking.com"),
    OtaPlatform.MMT: ("MakeMyTrip", "Hotel reservations from MakeMyTrip"),
    OtaPlatform.EXPEDIA: ("Expedia", "Hotel reservations from Expedia"),
}

PLATFORM_PMS_SOURCE = {
    OtaPlatform.BOOKING_COM: "ota_booking_com",
    OtaPlatform.MMT: "ota_mmt",
    OtaPlatform.EXPEDIA: "ota_expedia",
}

VALID_ADAPTER_MODES = {"mock", "http"}


def resolve_adapter_mode(config: dict | None = None) -> str:
    if config and config.get("adapter_mode"):
        mode = str(config["adapter_mode"]).lower()
        if mode in VALID_ADAPTER_MODES:
            return mode
    default = settings.ota_default_adapter_mode.lower()
    return default if default in VALID_ADAPTER_MODES else "mock"


def get_ota_provider(platform: OtaPlatform, config: dict | None = None) -> BaseOtaProvider:
    mode = resolve_adapter_mode(config)
    registry = _HTTP_ADAPTERS if mode == "http" else _MOCK_ADAPTERS
    adapter = registry.get(platform)
    if adapter is None:
        raise ValueError(f"No OTA provider registered for {platform.value}")
    return adapter


def build_webhook_url(webhook_token: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    return f"{base}/api/v1/ota/webhooks/{webhook_token}"
