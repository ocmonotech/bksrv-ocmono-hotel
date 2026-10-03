from __future__ import annotations

import hashlib
import hmac

from app.modules.delivery.models import DeliveryPlatform, ExternalOrderStatus
from app.modules.delivery.providers.base import (
    BaseDeliveryProvider,
    ProviderConnectionResult,
    ProviderStatusResult,
)


class MockZomatoProvider(BaseDeliveryProvider):
    platform = DeliveryPlatform.ZOMATO

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
            message="Mock Zomato connection verified",
            store_name=f"Zomato Store {external_store_id}",
        )

    async def update_order_status(
        self,
        *,
        external_order_id: str,
        external_store_id: str | None,
        api_key: str | None,
        status: ExternalOrderStatus,
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


class MockSwiggyProvider(MockZomatoProvider):
    platform = DeliveryPlatform.SWIGGY

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
                message="Swiggy outlet ID is required",
            )
        return ProviderConnectionResult(
            success=True,
            message="Mock Swiggy connection verified",
            store_name=f"Swiggy Outlet {external_store_id}",
        )


class MockOndcProvider(MockZomatoProvider):
    platform = DeliveryPlatform.ONDC

    async def test_connection(
        self,
        *,
        external_store_id: str | None,
        api_key: str | None,
        config: dict | None = None,
    ) -> ProviderConnectionResult:
        return ProviderConnectionResult(
            success=True,
            message="Mock ONDC connection verified",
            store_name=external_store_id or "ONDC Seller",
        )


class MockDunzoProvider(MockZomatoProvider):
    platform = DeliveryPlatform.DUNZO


class MockMagicpinProvider(MockZomatoProvider):
    platform = DeliveryPlatform.MAGICPIN
