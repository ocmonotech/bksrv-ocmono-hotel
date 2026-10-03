from __future__ import annotations

import hashlib
import hmac

from app.modules.bookings.models import BookingPlatform, BookingStatus
from app.modules.bookings.providers.base import (
    BaseBookingProvider,
    ProviderConnectionResult,
    ProviderStatusResult,
)


class MockZomatoBookingProvider(BaseBookingProvider):
    platform = BookingPlatform.ZOMATO

    async def test_connection(
        self,
        *,
        external_store_id: str | None,
        api_key: str | None,
        config: dict | None = None,
    ) -> ProviderConnectionResult:
        if not external_store_id:
            return ProviderConnectionResult(
                success=False,
                message="Zomato restaurant ID is required",
            )
        return ProviderConnectionResult(
            success=True,
            message="Mock Zomato Dine-in connection verified",
            store_name=f"Zomato Dine-in {external_store_id}",
        )

    async def update_booking_status(
        self,
        *,
        external_booking_id: str,
        external_store_id: str | None,
        api_key: str | None,
        status: BookingStatus,
        config: dict | None = None,
    ) -> ProviderStatusResult:
        return ProviderStatusResult(success=True, external_status=status)

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str | None,
        webhook_secret: str | None,
    ) -> bool:
        if not webhook_secret:
            return True
        if not signature:
            return False
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


class MockSwiggyDineoutProvider(MockZomatoBookingProvider):
    platform = BookingPlatform.SWIGGY_DINEOUT

    async def test_connection(
        self,
        *,
        external_store_id: str | None,
        api_key: str | None,
        config: dict | None = None,
    ) -> ProviderConnectionResult:
        if not external_store_id:
            return ProviderConnectionResult(
                success=False,
                message="Swiggy Dineout outlet ID is required",
            )
        return ProviderConnectionResult(
            success=True,
            message="Mock Swiggy Dineout connection verified",
            store_name=f"Swiggy Dineout {external_store_id}",
        )


class MockEazyDinerProvider(MockZomatoBookingProvider):
    platform = BookingPlatform.EAZYDINER


class MockDineoutProvider(MockZomatoBookingProvider):
    platform = BookingPlatform.DINEOUT


class MockGoogleBookingProvider(MockZomatoBookingProvider):
    platform = BookingPlatform.GOOGLE
