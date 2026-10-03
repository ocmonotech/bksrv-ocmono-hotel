from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.modules.bookings.models import BookingPlatform, BookingStatus


@dataclass
class ProviderStatusResult:
    success: bool
    external_status: BookingStatus | None = None
    error_message: str | None = None


@dataclass
class ProviderConnectionResult:
    success: bool
    message: str
    store_name: str | None = None


class BaseBookingProvider(ABC):
    platform: BookingPlatform

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
    async def update_booking_status(
        self,
        *,
        external_booking_id: str,
        external_store_id: str | None,
        api_key: str | None,
        status: BookingStatus,
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
