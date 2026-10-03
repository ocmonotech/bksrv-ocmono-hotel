from __future__ import annotations

import hashlib
import hmac
from datetime import date
from typing import Any

import httpx

from app.modules.ota.providers.base import (
    AriPushPayload,
    AriPushResult,
    BaseOtaProvider,
    ProviderConnectionResult,
    ProviderReservation,
    ReservationPullResult,
)


class HttpOtaProvider(BaseOtaProvider):
    """REST channel-manager adapter — maps to configurable OTA partner endpoints."""

    label: str
    default_base_url: str

    def _resolve_base_url(self, config: dict | None) -> str:
        if config and config.get("api_base_url"):
            return str(config["api_base_url"]).rstrip("/")
        return self.default_base_url.rstrip("/")

    def _headers(self, api_key: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_ari_body(self, payload: AriPushPayload) -> dict[str, Any]:
        return {
            "property_id": payload.external_property_id,
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
            "room_types": [
                {
                    "room_type_id": room.external_room_type_id,
                    "room_type_name": room.external_room_type_name,
                    "rates": [
                        {
                            "date": day.date.isoformat(),
                            "available_rooms": day.available_rooms,
                            "rate": day.rate,
                            "stop_sell": day.stop_sell,
                            "cta": day.cta,
                            "ctd": day.ctd,
                            "min_stay": day.min_stay,
                            "max_stay": day.max_stay,
                        }
                        for day in room.days
                    ],
                }
                for room in payload.room_types
            ],
        }

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
        if not api_key:
            return ProviderConnectionResult(
                success=False,
                message=f"{self.label} API key is required for HTTP adapter",
            )

        base_url = self._resolve_base_url(config)
        url = f"{base_url}/properties/{external_property_id}"
        timeout = float((config or {}).get("http_timeout_seconds", 30))

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=self._headers(api_key))
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return ProviderConnectionResult(
                success=False,
                message=f"{self.label} HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.HTTPError as exc:
            return ProviderConnectionResult(
                success=False,
                message=f"{self.label} connection failed: {exc}",
            )

        property_name = data.get("property_name") or data.get("name")
        return ProviderConnectionResult(
            success=True,
            message=f"{self.label} HTTP connection verified",
            property_name=property_name or f"{self.label} {external_property_id}",
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
        if not external_property_id:
            return AriPushResult(success=False, message=f"{self.label} property ID is required")
        if not api_key:
            return AriPushResult(success=False, message=f"{self.label} API key is required for HTTP adapter")

        base_url = self._resolve_base_url(config)
        url = f"{base_url}/properties/{external_property_id}/ari"
        body = self._build_ari_body(payload)
        timeout = float((config or {}).get("http_timeout_seconds", 30))

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=self._headers(api_key), json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return AriPushResult(
                success=False,
                message=f"{self.label} ARI push HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.HTTPError as exc:
            return AriPushResult(success=False, message=f"{self.label} ARI push failed: {exc}")

        reference = data.get("reference") or data.get("external_reference")
        message = data.get("message") or f"{self.label} ARI push accepted"
        success = bool(data.get("success", True))
        return AriPushResult(success=success, message=message, external_reference=reference)

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
        if not api_key:
            return ReservationPullResult(
                success=False,
                message=f"{self.label} API key is required for HTTP adapter",
            )

        base_url = self._resolve_base_url(config)
        url = f"{base_url}/properties/{external_property_id}/reservations"
        timeout = float((config or {}).get("http_timeout_seconds", 30))

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=self._headers(api_key))
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return ReservationPullResult(
                success=False,
                message=(
                    f"{self.label} reservation pull HTTP {exc.response.status_code}: "
                    f"{exc.response.text[:200]}"
                ),
            )
        except httpx.HTTPError as exc:
            return ReservationPullResult(
                success=False,
                message=f"{self.label} reservation pull failed: {exc}",
            )

        raw_items = data.get("reservations") or data.get("items") or []
        if isinstance(data, list):
            raw_items = data

        reservations: list[ProviderReservation] = []
        allowed = set(mapped_external_room_type_ids) if mapped_external_room_type_ids else None
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            room_type_id = str(
                item.get("external_room_type_id")
                or item.get("room_type_id")
                or item.get("roomTypeId")
                or ""
            )
            if allowed is not None and room_type_id and room_type_id not in allowed:
                continue
            try:
                reservations.append(
                    ProviderReservation(
                        external_reservation_id=str(
                            item.get("external_reservation_id")
                            or item.get("reservation_id")
                            or item.get("id")
                        ),
                        guest_name=str(item.get("guest_name") or item.get("guestName") or "OTA Guest"),
                        guest_mobile=str(
                            item.get("guest_mobile") or item.get("guestMobile") or "+910000000000"
                        ),
                        guest_email=item.get("guest_email") or item.get("guestEmail"),
                        external_room_type_id=room_type_id or "STD",
                        check_in_date=date.fromisoformat(str(item["check_in_date"])),
                        check_out_date=date.fromisoformat(str(item["check_out_date"])),
                        adults=int(item.get("adults") or 1),
                        children=int(item.get("children") or 0),
                        notes=item.get("notes"),
                        external_rate_id=item.get("external_rate_id") or item.get("rate_id"),
                        status=str(item.get("status") or "confirmed"),
                        action=str(item.get("action") or "create"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue

        return ReservationPullResult(
            success=True,
            message=f"{self.label} pulled {len(reservations)} reservation(s)",
            reservations=reservations,
            external_reference=data.get("reference") if isinstance(data, dict) else None,
        )
