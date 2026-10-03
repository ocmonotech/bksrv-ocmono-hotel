from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.modules.delivery.models import DeliveryPlatform, ExternalOrderStatus


@dataclass
class ProviderStatusResult:
    success: bool
    external_status: ExternalOrderStatus | None = None
    error_message: str | None = None


@dataclass
class ProviderConnectionResult:
    success: bool
    message: str
    store_name: str | None = None


class BaseDeliveryProvider(ABC):
    platform: DeliveryPlatform

    @abstractmethod
    async def test_connection(
        self,
        *,
        external_store_id: str | None,
        api_key: str | None,
        config: dict | None = None,
    ) -> ProviderConnectionResult:
        raise NotImplementedError

    @abstractmethod
    async def update_order_status(
        self,
        *,
        external_order_id: str,
        external_store_id: str | None,
        api_key: str | None,
        status: ExternalOrderStatus,
        config: dict | None = None,
    ) -> ProviderStatusResult:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str | None,
        webhook_secret: str | None,
    ) -> bool:
        raise NotImplementedError
