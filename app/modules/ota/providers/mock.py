from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import date, timedelta

from app.modules.ota.models import OtaPlatform
from app.modules.ota.providers.base import (
    AriPushPayload,
    AriPushResult,
    BaseOtaProvider,
    ProviderConnectionResult,
    ProviderReservation,
    ReservationPullResult,
)


class _MockOtaProvider(BaseOtaProvider):
    label: str

    async def test_connection(
        self,
        *,
        external_property_id: str | None,
        api_key: str | None,
        config: dict | None = None,
    ) -> ProviderConnectionResult:
        if not external_property_id:
            return ProviderConnectionResult(
                success=False,
                message=f"{self.label} property ID is required",
            )
        return ProviderConnectionResult(
            success=True,
            message=f"Mock {self.label} connection verified",
            property_name=f"{self.label} Property {external_property_id}",
        )

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

    async def push_availability_rates(
        self,
        *,
        external_property_id: str | None,
        api_key: str | None,
        payload: AriPushPayload,
        config: dict | None = None,
    ) -> AriPushResult:
        day_count = sum(len(room.days) for room in payload.room_types)
        restricted = sum(
            1
            for room in payload.room_types
            for day in room.days
            if day.stop_sell or day.cta or day.ctd or day.min_stay or day.max_stay
        )
        return AriPushResult(
            success=True,
            message=(
                f"Mock {self.label} ARI push accepted — "
                f"{len(payload.room_types)} room type(s), {day_count} day-rate(s)"
                + (f", {restricted} restriction day(s)" if restricted else "")
            ),
            external_reference=f"MOCK-ARI-{uuid.uuid4().hex[:10].upper()}",
        )

    async def pull_reservations(
        self,
        *,
        external_property_id: str | None,
        api_key: str | None,
        mapped_external_room_type_ids: list[str],
        config: dict | None = None,
    ) -> ReservationPullResult:
        if not external_property_id:
            return ReservationPullResult(
                success=False,
                message=f"{self.label} property ID is required",
            )
        room_id = (
            mapped_external_room_type_ids[0]
            if mapped_external_room_type_ids
            else "STD"
        )
        check_in = date.today() + timedelta(days=10)
        check_out = check_in + timedelta(days=2)
        pull_id = uuid.uuid4().hex[:8].upper()
        reservations = [
            ProviderReservation(
                external_reservation_id=f"{self.platform.value.upper()}-PULL-{pull_id}",
                guest_name=f"{self.label} Pull Guest",
                guest_mobile="+919700011122",
                guest_email="ota.pull@example.com",
                external_room_type_id=room_id,
                check_in_date=check_in,
                check_out_date=check_out,
                adults=2,
                children=0,
                notes=f"Pulled from mock {self.label} adapter",
                status="confirmed",
                action="create",
            )
        ]
        return ReservationPullResult(
            success=True,
            message=f"Mock {self.label} returned {len(reservations)} reservation(s)",
            reservations=reservations,
            external_reference=f"MOCK-PULL-{pull_id}",
        )


class MockBookingComProvider(_MockOtaProvider):
    platform = OtaPlatform.BOOKING_COM
    label = "Booking.com"


class MockMmtProvider(_MockOtaProvider):
    platform = OtaPlatform.MMT
    label = "MakeMyTrip"


class MockExpediaProvider(_MockOtaProvider):
    platform = OtaPlatform.EXPEDIA
    label = "Expedia"
