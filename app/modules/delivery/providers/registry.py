from __future__ import annotations

from app.core.config import settings
from app.modules.delivery.models import DeliveryPlatform
from app.modules.delivery.providers.base import BaseDeliveryProvider
from app.modules.delivery.providers.mock import (
    MockDunzoProvider,
    MockMagicpinProvider,
    MockOndcProvider,
    MockSwiggyProvider,
    MockZomatoProvider,
)

_ADAPTERS: dict[DeliveryPlatform, BaseDeliveryProvider] = {
    DeliveryPlatform.ZOMATO: MockZomatoProvider(),
    DeliveryPlatform.SWIGGY: MockSwiggyProvider(),
    DeliveryPlatform.ONDC: MockOndcProvider(),
    DeliveryPlatform.DUNZO: MockDunzoProvider(),
    DeliveryPlatform.MAGICPIN: MockMagicpinProvider(),
}

PLATFORM_LABELS: dict[DeliveryPlatform, tuple[str, str]] = {
    DeliveryPlatform.ZOMATO: ("Zomato", "Receive and manage Zomato delivery orders"),
    DeliveryPlatform.SWIGGY: ("Swiggy", "Receive and manage Swiggy delivery orders"),
    DeliveryPlatform.ONDC: ("ONDC", "Open Network for Digital Commerce orders"),
    DeliveryPlatform.DUNZO: ("Dunzo", "Hyperlocal delivery orders via Dunzo"),
    DeliveryPlatform.MAGICPIN: ("Magicpin", "Magicpin delivery and dine-in orders"),
}


def get_delivery_provider(platform: DeliveryPlatform) -> BaseDeliveryProvider:
    adapter = _ADAPTERS.get(platform)
    if adapter is None:
        raise ValueError(f"No delivery provider registered for {platform.value}")
    return adapter


def build_webhook_url(webhook_token: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    return f"{base}/api/v1/delivery/webhooks/{webhook_token}"
