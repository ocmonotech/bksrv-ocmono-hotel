from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from app.modules.ota.models import OtaPlatform


@dataclass
class ProviderConnectionResult:
    success: bool
    message: str
    property_name: str | None = None


@dataclass
class AriDayRate:
    date: date
    available_rooms: int
    rate: float
    stop_sell: bool = False
    cta: bool = False
    ctd: bool = False
    min_stay: int | None = None
    max_stay: int | None = None


@dataclass
class AriRoomTypePayload:
    external_room_type_id: str
    external_room_type_name: str | None
    room_type_id: int
    room_type_name: str | None
    days: list[AriDayRate] = field(default_factory=list)


@dataclass
class AriPushPayload:
    integration_id: int
    outlet_id: int
    platform: OtaPlatform
    external_property_id: str | None
    start_date: date
    end_date: date
    room_types: list[AriRoomTypePayload] = field(default_factory=list)


@dataclass
class AriPushResult:
    success: bool
    message: str
    external_reference: str | None = None


@dataclass
class ProviderReservation:
    external_reservation_id: str
    guest_name: str
    guest_mobile: str
    external_room_type_id: str
    check_in_date: date
    check_out_date: date
    guest_email: str | None = None
    adults: int = 2
    children: int = 0
    notes: str | None = None
    external_rate_id: str | None = None
    status: str = "confirmed"
    action: str = "create"


@dataclass
class ReservationPullResult:
    success: bool
    message: str
    reservations: list[ProviderReservation] = field(default_factory=list)
    external_reference: str | None = None


class BaseOtaProvider(ABC):
    platform: OtaPlatform

    @abstractmethod
    async def test_connection(
        self,
        *,
        external_property_id: str | None,
        api_key: str | None,
        config: dict | None = None,
    ) -> ProviderConnectionResult:
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

    @abstractmethod
    async def push_availability_rates(
        self,
        *,
        external_property_id: str | None,
        api_key: str | None,
        payload: AriPushPayload,
        config: dict | None = None,
    ) -> AriPushResult:
        raise NotImplementedError

    @abstractmethod
    async def pull_reservations(
        self,
        *,
        external_property_id: str | None,
        api_key: str | None,
        mapped_external_room_type_ids: list[str],
        config: dict | None = None,
    ) -> ReservationPullResult:
        raise NotImplementedError
