from __future__ import annotations

from app.core.config import settings
from app.modules.bookings.models import BookingPlatform
from app.modules.bookings.providers.base import BaseBookingProvider
from app.modules.bookings.providers.mock import (
    MockDineoutProvider,
    MockEazyDinerProvider,
    MockGoogleBookingProvider,
    MockSwiggyDineoutProvider,
    MockZomatoBookingProvider,
)

_ADAPTERS: dict[BookingPlatform, BaseBookingProvider] = {
    BookingPlatform.ZOMATO: MockZomatoBookingProvider(),
    BookingPlatform.SWIGGY_DINEOUT: MockSwiggyDineoutProvider(),
    BookingPlatform.EAZYDINER: MockEazyDinerProvider(),
    BookingPlatform.DINEOUT: MockDineoutProvider(),
    BookingPlatform.GOOGLE: MockGoogleBookingProvider(),
}

PLATFORM_LABELS: dict[BookingPlatform, tuple[str, str]] = {
    BookingPlatform.ZOMATO: ("Zomato Dine-in", "Table reservations from Zomato"),
    BookingPlatform.SWIGGY_DINEOUT: ("Swiggy Dineout", "Table reservations from Swiggy Dineout"),
    BookingPlatform.EAZYDINER: ("EazyDiner", "Table reservations from EazyDiner"),
    BookingPlatform.DINEOUT: ("Dineout", "Table reservations from Dineout"),
    BookingPlatform.GOOGLE: ("Google Reserve", "Reservations via Google Reserve with Maps"),
    BookingPlatform.DIRECT: ("Direct / Walk-in", "In-house or phone reservations"),
}


def get_booking_provider(platform: BookingPlatform) -> BaseBookingProvider:
    adapter = _ADAPTERS.get(platform)
    if adapter is None:
        raise ValueError(f"No booking provider registered for {platform.value}")
    return adapter


def build_webhook_url(webhook_token: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    return f"{base}/api/v1/bookings/webhooks/{webhook_token}"
