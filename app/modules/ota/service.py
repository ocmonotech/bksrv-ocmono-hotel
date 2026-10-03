from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.delivery.models import IntegrationStatus
from app.modules.housekeeping.models import RoomType
from app.modules.ota.models import (
    OtaPlatform,
    OtaRatePlanMapping,
    OtaReservationLink,
    OtaRoomTypeMapping,
    OtaSyncLog,
    OtaSyncStatus,
    OtaSyncType,
    OutletOtaIntegration,
)
from app.modules.ota.providers.base import AriDayRate, AriPushPayload, AriRoomTypePayload
from app.modules.ota.providers.registry import (
    PLATFORM_LABELS,
    PLATFORM_PMS_SOURCE,
    build_webhook_url,
    get_ota_provider,
)
from app.modules.ota.schemas import (
    AutoAriPushResponse,
    AutoAriPushResultItem,
    AriDayRead,
    AriPreviewRead,
    AriPushRequest,
    AriPushResponse,
    AriRoomTypeRead,
    InboundOtaReservationPayload,
    IntegrationCreate,
    IntegrationDeleteResponse,
    IntegrationRead,
    IntegrationUpdate,
    MockOtaReservationRequest,
    MockOtaReservationActionRequest,
    OtaReservationRead,
    OtaSyncLogRead,
    PlatformInfo,
    RatePlanMappingCreate,
    RatePlanMappingRead,
    ReservationPullItemResult,
    ReservationPullResponse,
    RoomTypeMappingCreate,
    RoomTypeMappingRead,
    WebhookAckResponse,
)
from app.modules.outlets.models import Outlet
from app.modules.pms import service as pms_service
from app.modules.pms.models import GuestReservation, ReservationSource, ReservationStatus
from app.modules.pms.schemas import RateInventoryCell, ReservationCreate
from app.modules.users.models import User
from app.utils.encryption import decrypt_secret, encrypt_secret


def list_platforms() -> list[PlatformInfo]:
    return [
        PlatformInfo(
            platform=platform,
            label=label,
            description=description,
            supported_adapter_modes=["mock", "http"],
            default_adapter_mode=settings.ota_default_adapter_mode,
        )
        for platform, (label, description) in PLATFORM_LABELS.items()
    ]


def list_integrations(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    platform: OtaPlatform | None = None,
) -> tuple[list[IntegrationRead], int]:
    query = db.query(OutletOtaIntegration).filter(
        OutletOtaIntegration.tenant_id == tenant_id,
        OutletOtaIntegration.is_active.is_(True),
    )
    if outlet_id is not None:
        query = query.filter(OutletOtaIntegration.outlet_id == outlet_id)
    if platform is not None:
        query = query.filter(OutletOtaIntegration.platform == platform)

    rows, total = paginate_query(query.order_by(OutletOtaIntegration.id.desc()), page, page_size)
    return [_to_integration_read(db, row) for row in rows], total


def get_integration(db: Session, tenant_id: int, integration_id: int) -> IntegrationRead:
    return _to_integration_read(db, _get_integration_entity(db, tenant_id, integration_id))


def create_integration(
    db: Session,
    tenant_id: int,
    data: IntegrationCreate,
    default_brand_id: int | None = None,
) -> IntegrationRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    existing = (
        db.query(OutletOtaIntegration)
        .filter(
            OutletOtaIntegration.outlet_id == data.outlet_id,
            OutletOtaIntegration.platform == data.platform,
            OutletOtaIntegration.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError(f"{data.platform.value} is already configured for this outlet")

    integration = OutletOtaIntegration(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        platform=data.platform,
        external_property_id=data.external_property_id,
        status=IntegrationStatus.PENDING,
        is_enabled=data.is_enabled,
        auto_confirm_reservations=data.auto_confirm_reservations,
        auto_push_availability=data.auto_push_availability,
        webhook_token=uuid.uuid4().hex,
        config_json=json.dumps(data.config or {}),
        encrypted_api_key=encrypt_secret(data.api_key),
        encrypted_webhook_secret=encrypt_secret(data.webhook_secret),
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return _to_integration_read(db, integration)


def update_integration(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: IntegrationUpdate,
) -> IntegrationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    payload = data.model_dump(exclude_unset=True)

    if "external_property_id" in payload:
        integration.external_property_id = payload["external_property_id"]
    if "status" in payload:
        integration.status = payload["status"]
    if "is_enabled" in payload:
        integration.is_enabled = payload["is_enabled"]
    if "auto_confirm_reservations" in payload:
        integration.auto_confirm_reservations = payload["auto_confirm_reservations"]
    if "auto_push_availability" in payload:
        integration.auto_push_availability = payload["auto_push_availability"]
    if "config" in payload and payload["config"] is not None:
        integration.config_json = json.dumps(payload["config"])
    if "api_key" in payload and payload["api_key"]:
        integration.encrypted_api_key = encrypt_secret(payload["api_key"])
    if "webhook_secret" in payload and payload["webhook_secret"]:
        integration.encrypted_webhook_secret = encrypt_secret(payload["webhook_secret"])

    db.commit()
    db.refresh(integration)
    return _to_integration_read(db, integration)


def delete_integration(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> IntegrationDeleteResponse:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    integration.is_active = False
    integration.is_enabled = False
    integration.status = IntegrationStatus.INACTIVE
    db.commit()
    return IntegrationDeleteResponse(message="OTA integration removed", integration_id=integration_id)


async def test_integration_connection(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> IntegrationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    config = _load_config(integration)
    provider = get_ota_provider(integration.platform, config)
    result = await provider.test_connection(
        external_property_id=integration.external_property_id,
        api_key=decrypt_secret(integration.encrypted_api_key),
        config=_load_config(integration),
    )
    integration.last_sync_at = datetime.utcnow()
    if result.success:
        integration.status = IntegrationStatus.ACTIVE
        integration.last_error = None
    else:
        integration.status = IntegrationStatus.ERROR
        integration.last_error = result.message
    db.commit()
    db.refresh(integration)
    return _to_integration_read(db, integration)


def list_room_mappings(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> list[RoomTypeMappingRead]:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    rows = (
        db.query(OtaRoomTypeMapping)
        .filter(
            OtaRoomTypeMapping.integration_id == integration.id,
            OtaRoomTypeMapping.is_active.is_(True),
        )
        .order_by(OtaRoomTypeMapping.external_room_type_id)
        .all()
    )
    return [_to_mapping_read(db, row) for row in rows]


def create_room_mapping(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: RoomTypeMappingCreate,
) -> RoomTypeMappingRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    room_type = (
        db.query(RoomType)
        .filter(
            RoomType.id == data.room_type_id,
            RoomType.tenant_id == tenant_id,
            RoomType.is_active.is_(True),
        )
        .first()
    )
    if room_type is None:
        raise NotFoundError("Room type not found")

    existing = (
        db.query(OtaRoomTypeMapping)
        .filter(
            OtaRoomTypeMapping.integration_id == integration.id,
            OtaRoomTypeMapping.external_room_type_id == data.external_room_type_id.strip(),
            OtaRoomTypeMapping.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError("External room type ID already mapped for this integration")

    mapping = OtaRoomTypeMapping(
        tenant_id=tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        external_room_type_id=data.external_room_type_id.strip(),
        external_room_type_name=data.external_room_type_name,
        room_type_id=data.room_type_id,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _to_mapping_read(db, mapping)


def delete_room_mapping(db: Session, tenant_id: int, integration_id: int, mapping_id: int) -> None:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    mapping = (
        db.query(OtaRoomTypeMapping)
        .filter(
            OtaRoomTypeMapping.id == mapping_id,
            OtaRoomTypeMapping.integration_id == integration.id,
            OtaRoomTypeMapping.tenant_id == tenant_id,
            OtaRoomTypeMapping.is_active.is_(True),
        )
        .first()
    )
    if mapping is None:
        raise NotFoundError("Room type mapping not found")
    mapping.is_active = False
    db.commit()


def list_rate_plan_mappings(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> list[RatePlanMappingRead]:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    rows = (
        db.query(OtaRatePlanMapping)
        .filter(
            OtaRatePlanMapping.integration_id == integration.id,
            OtaRatePlanMapping.is_active.is_(True),
        )
        .order_by(OtaRatePlanMapping.external_rate_id)
        .all()
    )
    return [_to_rate_plan_mapping_read(db, row) for row in rows]


def create_rate_plan_mapping(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: RatePlanMappingCreate,
) -> RatePlanMappingRead:
    from app.modules.pms.models import RatePlan

    integration = _get_integration_entity(db, tenant_id, integration_id)
    plan = (
        db.query(RatePlan)
        .filter(
            RatePlan.id == data.rate_plan_id,
            RatePlan.tenant_id == tenant_id,
            RatePlan.is_active.is_(True),
        )
        .first()
    )
    if plan is None:
        raise NotFoundError("Rate plan not found")

    existing = (
        db.query(OtaRatePlanMapping)
        .filter(
            OtaRatePlanMapping.integration_id == integration.id,
            OtaRatePlanMapping.external_rate_id == data.external_rate_id.strip(),
            OtaRatePlanMapping.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError("External rate ID already mapped for this integration")

    mapping = OtaRatePlanMapping(
        tenant_id=tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        rate_plan_id=data.rate_plan_id,
        external_rate_id=data.external_rate_id.strip(),
        external_rate_name=data.external_rate_name,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _to_rate_plan_mapping_read(db, mapping)


def delete_rate_plan_mapping(
    db: Session, tenant_id: int, integration_id: int, mapping_id: int
) -> None:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    mapping = (
        db.query(OtaRatePlanMapping)
        .filter(
            OtaRatePlanMapping.id == mapping_id,
            OtaRatePlanMapping.integration_id == integration.id,
            OtaRatePlanMapping.tenant_id == tenant_id,
            OtaRatePlanMapping.is_active.is_(True),
        )
        .first()
    )
    if mapping is None:
        raise NotFoundError("Rate plan mapping not found")
    mapping.is_active = False
    db.commit()


def list_ota_reservations(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    platform: OtaPlatform | None = None,
) -> tuple[list[OtaReservationRead], int]:
    query = (
        db.query(OtaReservationLink)
        .join(GuestReservation, GuestReservation.id == OtaReservationLink.guest_reservation_id)
        .filter(
            OtaReservationLink.tenant_id == tenant_id,
            OtaReservationLink.is_active.is_(True),
            GuestReservation.is_active.is_(True),
        )
    )
    if outlet_id is not None:
        query = query.filter(GuestReservation.outlet_id == outlet_id)
    if platform is not None:
        query = query.filter(OtaReservationLink.platform == platform)

    rows, total = paginate_query(query.order_by(OtaReservationLink.id.desc()), page, page_size)
    return [_to_ota_reservation_read(db, row) for row in rows], total


async def ingest_inbound_reservation(
    db: Session,
    webhook_token: str,
    payload: InboundOtaReservationPayload,
    raw_payload: dict | None = None,
) -> WebhookAckResponse:
    from app.modules.pms.schemas import CancelReservationRequest, ReservationUpdate

    integration = (
        db.query(OutletOtaIntegration)
        .filter(
            OutletOtaIntegration.webhook_token == webhook_token,
            OutletOtaIntegration.is_active.is_(True),
        )
        .first()
    )
    if integration is None:
        raise NotFoundError("OTA integration not found")
    if not integration.is_enabled:
        raise ConflictError("OTA integration is disabled")

    existing = (
        db.query(OtaReservationLink)
        .filter(
            OtaReservationLink.integration_id == integration.id,
            OtaReservationLink.external_reservation_id == payload.external_reservation_id,
            OtaReservationLink.is_active.is_(True),
        )
        .first()
    )

    status_lower = (payload.status or "").strip().lower()
    is_cancel = payload.action == "cancel" or status_lower in {"cancelled", "canceled", "cancel"}
    is_modify = payload.action == "modify"

    if existing and (is_cancel or is_modify):
        if is_cancel:
            pms_service.cancel_reservation(
                db,
                integration.tenant_id,
                existing.guest_reservation_id,
                CancelReservationRequest(reason="Cancelled via OTA"),
            )
            existing.external_status = "cancelled"
            existing.raw_payload_json = json.dumps(raw_payload or payload.model_dump(mode="json"))
            db.commit()
            return WebhookAckResponse(
                success=True,
                message="OTA reservation cancelled",
                reservation_link_id=existing.id,
                guest_reservation_id=existing.guest_reservation_id,
            )

        pms_service.update_reservation(
            db,
            integration.tenant_id,
            existing.guest_reservation_id,
            ReservationUpdate(
                check_in_date=payload.check_in_date,
                check_out_date=payload.check_out_date,
                guest_name=payload.guest_name.strip(),
                guest_mobile=payload.guest_mobile.strip(),
                guest_email=payload.guest_email,
                notes=payload.notes,
            ),
        )
        existing.external_status = "modified"
        existing.raw_payload_json = json.dumps(raw_payload or payload.model_dump(mode="json"))
        db.commit()
        return WebhookAckResponse(
            success=True,
            message="OTA reservation modified",
            reservation_link_id=existing.id,
            guest_reservation_id=existing.guest_reservation_id,
        )

    if existing:
        return WebhookAckResponse(
            success=True,
            message="Reservation already ingested",
            reservation_link_id=existing.id,
            guest_reservation_id=existing.guest_reservation_id,
        )

    if is_cancel:
        raise NotFoundError("Cannot cancel unknown OTA reservation")

    room_type_id = _resolve_room_type_id(db, integration, payload)
    rate_plan_id = _resolve_rate_plan_id(db, integration, payload)
    source = ReservationSource(PLATFORM_PMS_SOURCE[integration.platform])
    user_id = _system_user_id(db, integration.tenant_id)

    reservation = pms_service.create_reservation(
        db,
        integration.tenant_id,
        user_id,
        ReservationCreate(
            outlet_id=integration.outlet_id,
            guest_name=payload.guest_name.strip(),
            guest_mobile=payload.guest_mobile.strip(),
            guest_email=payload.guest_email,
            room_type_id=room_type_id,
            check_in_date=payload.check_in_date,
            check_out_date=payload.check_out_date,
            adults=payload.adults,
            children=payload.children,
            source=source,
            rate_plan_id=rate_plan_id,
            rate_per_night=0,
            notes=payload.notes,
            auto_confirm=integration.auto_confirm_reservations,
        ),
        default_brand_id=integration.brand_id,
    )

    link = OtaReservationLink(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        guest_reservation_id=reservation.id,
        platform=integration.platform,
        external_reservation_id=payload.external_reservation_id,
        external_status=reservation.status.value,
        raw_payload_json=json.dumps(raw_payload or payload.model_dump(mode="json")),
    )
    db.add(link)
    integration.last_sync_at = datetime.utcnow()
    integration.last_error = None
    db.commit()
    db.refresh(link)

    return WebhookAckResponse(
        success=True,
        message="OTA reservation ingested",
        reservation_link_id=link.id,
        guest_reservation_id=reservation.id,
    )


async def simulate_mock_reservation(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: MockOtaReservationRequest,
) -> OtaReservationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    if not integration.is_enabled:
        raise ConflictError("Enable the integration before simulating reservations")

    check_in = data.check_in_date or (date.today() + timedelta(days=7))
    check_out = data.check_out_date or (check_in + timedelta(days=2))

    payload = InboundOtaReservationPayload(
        external_reservation_id=f"OTA-{uuid.uuid4().hex[:10].upper()}",
        guest_name=data.guest_name,
        guest_mobile=data.guest_mobile,
        external_room_type_id=data.external_room_type_id,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=data.adults,
        children=data.children,
        notes=data.notes or "Simulated OTA reservation",
    )

    ack = await ingest_inbound_reservation(
        db,
        integration.webhook_token,
        payload,
        raw_payload=payload.model_dump(mode="json"),
    )
    link = db.get(OtaReservationLink, ack.reservation_link_id)
    if link is None:
        raise NotFoundError("Reservation link not found after simulation")
    return _to_ota_reservation_read(db, link)


def _get_reservation_link_by_external(
    db: Session,
    tenant_id: int,
    integration_id: int,
    external_reservation_id: str,
) -> OtaReservationLink:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    link = (
        db.query(OtaReservationLink)
        .filter(
            OtaReservationLink.integration_id == integration.id,
            OtaReservationLink.external_reservation_id == external_reservation_id,
            OtaReservationLink.is_active.is_(True),
        )
        .first()
    )
    if link is None:
        raise NotFoundError("OTA reservation not found")
    return link


async def simulate_modify_reservation(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: MockOtaReservationActionRequest,
) -> OtaReservationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    if not integration.is_enabled:
        raise ConflictError("Enable the integration before simulating modifications")

    link = _get_reservation_link_by_external(
        db, tenant_id, integration_id, data.external_reservation_id
    )
    reservation = pms_service._get_reservation(db, tenant_id, link.guest_reservation_id)
    check_in = data.check_in_date or reservation.check_in_date
    check_out = data.check_out_date or (check_in + timedelta(days=1))
    if check_out <= check_in:
        check_out = check_in + timedelta(days=1)

    payload = InboundOtaReservationPayload(
        external_reservation_id=link.external_reservation_id,
        guest_name=(data.guest_name or reservation.guest_name).strip(),
        guest_mobile=(data.guest_mobile or reservation.guest_mobile).strip(),
        guest_email=reservation.guest_email,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=reservation.adults,
        children=reservation.children,
        notes=data.notes or "Simulated OTA modification",
        action="modify",
        status="modified",
    )
    ack = await ingest_inbound_reservation(
        db,
        integration.webhook_token,
        payload,
        raw_payload=payload.model_dump(mode="json"),
    )
    refreshed = db.get(OtaReservationLink, ack.reservation_link_id)
    if refreshed is None:
        raise NotFoundError("Reservation link not found after modification")
    return _to_ota_reservation_read(db, refreshed)


async def simulate_cancel_reservation(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: MockOtaReservationActionRequest,
) -> OtaReservationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    if not integration.is_enabled:
        raise ConflictError("Enable the integration before simulating cancellations")

    link = _get_reservation_link_by_external(
        db, tenant_id, integration_id, data.external_reservation_id
    )
    reservation = pms_service._get_reservation(db, tenant_id, link.guest_reservation_id)

    payload = InboundOtaReservationPayload(
        external_reservation_id=link.external_reservation_id,
        guest_name=reservation.guest_name,
        guest_mobile=reservation.guest_mobile,
        guest_email=reservation.guest_email,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        adults=reservation.adults,
        children=reservation.children,
        notes=data.notes or "Simulated OTA cancellation",
        action="cancel",
        status="cancelled",
    )
    ack = await ingest_inbound_reservation(
        db,
        integration.webhook_token,
        payload,
        raw_payload=payload.model_dump(mode="json"),
    )
    refreshed = db.get(OtaReservationLink, ack.reservation_link_id)
    if refreshed is None:
        raise NotFoundError("Reservation link not found after cancellation")
    return _to_ota_reservation_read(db, refreshed)


def get_ari_preview(
    db: Session,
    tenant_id: int,
    integration_id: int,
    request: AriPushRequest,
) -> AriPreviewRead:
    payload = _build_ari_payload(db, tenant_id, integration_id, request)
    return _ari_payload_to_preview(payload)


async def push_ari(
    db: Session,
    tenant_id: int,
    integration_id: int,
    request: AriPushRequest,
) -> AriPushResponse:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    if not integration.is_enabled:
        raise ConflictError("Enable the integration before pushing availability and rates")

    payload = _build_ari_payload(db, tenant_id, integration_id, request)
    config = _load_config(integration)
    provider = get_ota_provider(integration.platform, config)
    config = _load_config(integration)

    try:
        result = await provider.push_availability_rates(
            external_property_id=integration.external_property_id,
            api_key=decrypt_secret(integration.encrypted_api_key),
            payload=payload,
            config=config,
        )
    except Exception as exc:  # noqa: BLE001 — persist provider failures on integration
        integration.last_error = str(exc)[:512]
        db.commit()
        raise

    days_count = sum(len(room.days) for room in payload.room_types)
    summary = {
        "platform": integration.platform.value,
        "room_types": [
            {
                "external_room_type_id": room.external_room_type_id,
                "days": len(room.days),
                "sample_rate": room.days[0].rate if room.days else None,
            }
            for room in payload.room_types
        ],
    }
    sync_log = OtaSyncLog(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        sync_type=OtaSyncType.ARI_PUSH,
        status=OtaSyncStatus.SUCCESS if result.success else OtaSyncStatus.FAILED,
        start_date=payload.start_date,
        end_date=payload.end_date,
        room_types_count=len(payload.room_types),
        days_count=days_count,
        external_reference=result.external_reference,
        message=result.message[:512],
        summary_json=json.dumps(summary),
    )
    db.add(sync_log)

    integration.last_sync_at = datetime.utcnow()
    if result.success:
        integration.last_error = None
    else:
        integration.last_error = result.message[:512]

    db.commit()
    db.refresh(sync_log)

    return AriPushResponse(
        success=result.success,
        message=result.message,
        external_reference=result.external_reference,
        sync_log_id=sync_log.id,
    )


async def pull_reservations(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> ReservationPullResponse:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    if not integration.is_enabled:
        raise ConflictError("Enable the integration before pulling reservations")

    mappings = (
        db.query(OtaRoomTypeMapping)
        .filter(
            OtaRoomTypeMapping.integration_id == integration.id,
            OtaRoomTypeMapping.is_active.is_(True),
        )
        .all()
    )
    mapped_external_ids = [m.external_room_type_id for m in mappings]
    config = _load_config(integration)
    provider = get_ota_provider(integration.platform, config)

    try:
        pull_result = await provider.pull_reservations(
            external_property_id=integration.external_property_id,
            api_key=decrypt_secret(integration.encrypted_api_key),
            mapped_external_room_type_ids=mapped_external_ids,
            config=config,
        )
    except Exception as exc:  # noqa: BLE001 — persist provider failures on integration
        integration.last_error = str(exc)[:512]
        db.commit()
        raise

    item_results: list[ReservationPullItemResult] = []
    created_count = 0
    skipped_count = 0
    failed_count = 0

    if pull_result.success:
        for reservation in pull_result.reservations:
            payload = InboundOtaReservationPayload(
                external_reservation_id=reservation.external_reservation_id,
                guest_name=reservation.guest_name,
                guest_mobile=reservation.guest_mobile,
                guest_email=reservation.guest_email,
                external_room_type_id=reservation.external_room_type_id,
                external_rate_id=reservation.external_rate_id,
                check_in_date=reservation.check_in_date,
                check_out_date=reservation.check_out_date,
                adults=reservation.adults,
                children=reservation.children,
                notes=reservation.notes,
                status=reservation.status,
                action=reservation.action,
            )
            try:
                ack = await ingest_inbound_reservation(
                    db,
                    integration.webhook_token,
                    payload,
                    raw_payload={
                        "source": "reservation_pull",
                        **payload.model_dump(mode="json"),
                    },
                )
                already = "already" in (ack.message or "").lower()
                if already:
                    skipped_count += 1
                else:
                    created_count += 1
                item_results.append(
                    ReservationPullItemResult(
                        external_reservation_id=reservation.external_reservation_id,
                        success=ack.success,
                        message=ack.message,
                        reservation_link_id=ack.reservation_link_id,
                        guest_reservation_id=ack.guest_reservation_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001 — continue remaining pulls
                failed_count += 1
                item_results.append(
                    ReservationPullItemResult(
                        external_reservation_id=reservation.external_reservation_id,
                        success=False,
                        message=str(exc)[:256],
                    )
                )

    today = date.today()
    summary = {
        "platform": integration.platform.value,
        "pulled": len(pull_result.reservations),
        "created": created_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "adapter_mode": config.get("adapter_mode", "mock"),
    }
    overall_success = pull_result.success and failed_count == 0
    message = pull_result.message
    if pull_result.success:
        message = (
            f"{pull_result.message} — created {created_count}, "
            f"skipped {skipped_count}, failed {failed_count}"
        )

    sync_log = OtaSyncLog(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        sync_type=OtaSyncType.RESERVATION_PULL,
        status=OtaSyncStatus.SUCCESS if overall_success else OtaSyncStatus.FAILED,
        start_date=today,
        end_date=today + timedelta(days=14),
        room_types_count=len(mapped_external_ids),
        days_count=len(pull_result.reservations),
        external_reference=pull_result.external_reference,
        message=message[:512],
        summary_json=json.dumps(summary),
    )
    db.add(sync_log)

    integration.last_sync_at = datetime.utcnow()
    if overall_success:
        integration.last_error = None
    else:
        integration.last_error = message[:512]

    db.commit()
    db.refresh(sync_log)

    return ReservationPullResponse(
        success=overall_success,
        message=message,
        external_reference=pull_result.external_reference,
        sync_log_id=sync_log.id,
        pulled_count=len(pull_result.reservations),
        created_count=created_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        results=item_results,
    )


def list_sync_logs(
    db: Session,
    tenant_id: int,
    integration_id: int,
    page: int,
    page_size: int,
) -> tuple[list[OtaSyncLogRead], int]:
    _get_integration_entity(db, tenant_id, integration_id)
    query = (
        db.query(OtaSyncLog)
        .filter(
            OtaSyncLog.integration_id == integration_id,
            OtaSyncLog.tenant_id == tenant_id,
            OtaSyncLog.is_active.is_(True),
        )
        .order_by(OtaSyncLog.id.desc())
    )
    rows, total = paginate_query(query, page, page_size)
    return [_to_sync_log_read(row) for row in rows], total


async def push_auto_ari_for_outlet(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    request: AriPushRequest | None = None,
) -> AutoAriPushResponse:
    _get_outlet(db, tenant_id, outlet_id)
    push_request = request or AriPushRequest()
    integrations = (
        db.query(OutletOtaIntegration)
        .filter(
            OutletOtaIntegration.tenant_id == tenant_id,
            OutletOtaIntegration.outlet_id == outlet_id,
            OutletOtaIntegration.is_active.is_(True),
            OutletOtaIntegration.is_enabled.is_(True),
            OutletOtaIntegration.auto_push_availability.is_(True),
        )
        .order_by(OutletOtaIntegration.id)
        .all()
    )

    results: list[AutoAriPushResultItem] = []
    for integration in integrations:
        try:
            push_result = await push_ari(db, tenant_id, integration.id, push_request)
            results.append(
                AutoAriPushResultItem(
                    integration_id=integration.id,
                    platform=integration.platform,
                    success=push_result.success,
                    message=push_result.message,
                    external_reference=push_result.external_reference,
                    sync_log_id=push_result.sync_log_id,
                )
            )
        except Exception as exc:  # noqa: BLE001 — continue pushing other channels
            results.append(
                AutoAriPushResultItem(
                    integration_id=integration.id,
                    platform=integration.platform,
                    success=False,
                    message=str(exc)[:512],
                )
            )

    successes = sum(1 for row in results if row.success)
    return AutoAriPushResponse(
        outlet_id=outlet_id,
        integrations_pushed=len(results),
        successes=successes,
        failures=len(results) - successes,
        results=results,
    )


async def push_auto_ari_for_tenant(
    db: Session,
    tenant_id: int,
    request: AriPushRequest | None = None,
) -> AutoAriPushResponse:
    push_request = request or AriPushRequest()
    outlet_ids = {
        row.outlet_id
        for row in db.query(OutletOtaIntegration)
        .filter(
            OutletOtaIntegration.tenant_id == tenant_id,
            OutletOtaIntegration.is_active.is_(True),
            OutletOtaIntegration.is_enabled.is_(True),
            OutletOtaIntegration.auto_push_availability.is_(True),
        )
        .all()
    }

    combined: list[AutoAriPushResultItem] = []
    for outlet_id in sorted(outlet_ids):
        summary = await push_auto_ari_for_outlet(db, tenant_id, outlet_id, push_request)
        combined.extend(summary.results)

    successes = sum(1 for row in combined if row.success)
    return AutoAriPushResponse(
        outlet_id=None,
        integrations_pushed=len(combined),
        successes=successes,
        failures=len(combined) - successes,
        results=combined,
    )


async def push_auto_ari_all_tenants(
    db: Session,
    request: AriPushRequest | None = None,
) -> AutoAriPushResponse:
    push_request = request or AriPushRequest()
    outlet_keys = {
        (row.tenant_id, row.outlet_id)
        for row in db.query(OutletOtaIntegration)
        .filter(
            OutletOtaIntegration.is_active.is_(True),
            OutletOtaIntegration.is_enabled.is_(True),
            OutletOtaIntegration.auto_push_availability.is_(True),
        )
        .all()
    }

    combined: list[AutoAriPushResultItem] = []
    for tenant_id, outlet_id in sorted(outlet_keys):
        summary = await push_auto_ari_for_outlet(db, tenant_id, outlet_id, push_request)
        combined.extend(summary.results)

    successes = sum(1 for row in combined if row.success)
    return AutoAriPushResponse(
        outlet_id=None,
        integrations_pushed=len(combined),
        successes=successes,
        failures=len(combined) - successes,
        results=combined,
    )


def _resolve_ari_date_range(
    start_date: date | None,
    end_date: date | None,
    max_days: int,
) -> tuple[date, date]:
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=max_days - 1))
    if end < start:
        raise ConflictError("end_date must be on or after start_date")
    if (end - start).days + 1 > 90:
        raise ConflictError("Date range cannot exceed 90 days")
    return start, end


def _pms_source_for_platform(platform: OtaPlatform) -> ReservationSource:
    return ReservationSource(PLATFORM_PMS_SOURCE[platform])


def _build_ari_payload(
    db: Session,
    tenant_id: int,
    integration_id: int,
    request: AriPushRequest,
) -> AriPushPayload:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    mappings = (
        db.query(OtaRoomTypeMapping)
        .filter(
            OtaRoomTypeMapping.integration_id == integration.id,
            OtaRoomTypeMapping.is_active.is_(True),
        )
        .order_by(OtaRoomTypeMapping.id)
        .all()
    )
    if not mappings:
        raise ConflictError("Configure at least one room type mapping before pushing ARI")

    start_date, end_date = _resolve_ari_date_range(
        request.start_date,
        request.end_date,
        request.max_days,
    )
    pms_source = _pms_source_for_platform(integration.platform)
    cells_by_key = _load_rate_inventory_cells(
        db,
        tenant_id,
        integration.outlet_id,
        start_date,
        end_date,
        pms_source,
    )
    room_types: list[AriRoomTypePayload] = []

    for mapping in mappings:
        room_type = db.get(RoomType, mapping.room_type_id)
        days: list[AriDayRate] = []
        current = start_date
        while current <= end_date:
            cell = cells_by_key.get((mapping.room_type_id, current))
            if cell is not None:
                physical_available = max(cell.total_rooms - cell.sold - cell.blocked, 0)
                days.append(
                    AriDayRate(
                        date=current,
                        available_rooms=physical_available,
                        rate=float(cell.rate),
                        stop_sell=bool(cell.stop_sell) or physical_available <= 0,
                        cta=bool(cell.cta),
                        ctd=bool(cell.ctd),
                        min_stay=cell.min_stay,
                        max_stay=cell.max_stay,
                    )
                )
            current += timedelta(days=1)

        room_types.append(
            AriRoomTypePayload(
                external_room_type_id=mapping.external_room_type_id,
                external_room_type_name=mapping.external_room_type_name,
                room_type_id=mapping.room_type_id,
                room_type_name=room_type.name if room_type else None,
                days=days,
            )
        )

    return AriPushPayload(
        integration_id=integration.id,
        outlet_id=integration.outlet_id,
        platform=integration.platform,
        external_property_id=integration.external_property_id,
        start_date=start_date,
        end_date=end_date,
        room_types=room_types,
    )


def _load_rate_inventory_cells(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    start_date: date,
    end_date: date,
    source: ReservationSource,
) -> dict[tuple[int, date], RateInventoryCell]:
    """Load rate/inventory calendar cells in ≤31-day chunks keyed by (room_type_id, date)."""
    cells: dict[tuple[int, date], RateInventoryCell] = {}
    chunk_start = start_date
    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=30), end_date)
        calendar = pms_service.get_rate_inventory_calendar(
            db,
            tenant_id,
            outlet_id,
            chunk_start,
            chunk_end,
            source,
        )
        for cell in calendar.cells:
            cells[(cell.room_type_id, cell.date)] = cell
        chunk_start = chunk_end + timedelta(days=1)
    return cells


def _ari_payload_to_preview(payload: AriPushPayload) -> AriPreviewRead:
    return AriPreviewRead(
        integration_id=payload.integration_id,
        outlet_id=payload.outlet_id,
        platform=payload.platform,
        external_property_id=payload.external_property_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        room_types=[
            AriRoomTypeRead(
                external_room_type_id=room.external_room_type_id,
                external_room_type_name=room.external_room_type_name,
                room_type_id=room.room_type_id,
                room_type_name=room.room_type_name,
                days=[
                    AriDayRead(
                        date=day.date,
                        available_rooms=day.available_rooms,
                        rate=day.rate,
                        stop_sell=day.stop_sell,
                        cta=day.cta,
                        ctd=day.ctd,
                        min_stay=day.min_stay,
                        max_stay=day.max_stay,
                    )
                    for day in room.days
                ],
            )
            for room in payload.room_types
        ],
    )


def _resolve_room_type_id(
    db: Session,
    integration: OutletOtaIntegration,
    payload: InboundOtaReservationPayload,
) -> int:
    if payload.external_room_type_id:
        mapping = (
            db.query(OtaRoomTypeMapping)
            .filter(
                OtaRoomTypeMapping.integration_id == integration.id,
                OtaRoomTypeMapping.external_room_type_id == payload.external_room_type_id.strip(),
                OtaRoomTypeMapping.is_active.is_(True),
            )
            .first()
        )
        if mapping:
            return mapping.room_type_id

    if payload.room_type_id:
        room_type = (
            db.query(RoomType)
            .filter(
                RoomType.id == payload.room_type_id,
                RoomType.tenant_id == integration.tenant_id,
                RoomType.is_active.is_(True),
            )
            .first()
        )
        if room_type:
            return room_type.id

    fallback = (
        db.query(OtaRoomTypeMapping)
        .filter(
            OtaRoomTypeMapping.integration_id == integration.id,
            OtaRoomTypeMapping.is_active.is_(True),
        )
        .order_by(OtaRoomTypeMapping.id)
        .first()
    )
    if fallback:
        return fallback.room_type_id

    room_type = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == integration.tenant_id, RoomType.is_active.is_(True))
        .order_by(RoomType.name)
        .first()
    )
    if room_type is None:
        raise ConflictError("No room types configured for this property")
    return room_type.id


def _system_user_id(db: Session, tenant_id: int) -> int:
    user = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.is_active.is_(True))
        .order_by(User.id)
        .first()
    )
    if user is None:
        raise NotFoundError("No active user found for tenant")
    return user.id


def _load_config(integration: OutletOtaIntegration) -> dict:
    try:
        return json.loads(integration.config_json or "{}")
    except json.JSONDecodeError:
        return {}


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_integration_entity(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> OutletOtaIntegration:
    row = (
        db.query(OutletOtaIntegration)
        .filter(
            OutletOtaIntegration.id == integration_id,
            OutletOtaIntegration.tenant_id == tenant_id,
            OutletOtaIntegration.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("OTA integration not found")
    return row


def _to_integration_read(db: Session, integration: OutletOtaIntegration) -> IntegrationRead:
    mapping_count = (
        db.query(OtaRoomTypeMapping)
        .filter(
            OtaRoomTypeMapping.integration_id == integration.id,
            OtaRoomTypeMapping.is_active.is_(True),
        )
        .count()
    )
    return IntegrationRead(
        id=integration.id,
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        outlet_id=integration.outlet_id,
        platform=integration.platform,
        external_property_id=integration.external_property_id,
        status=integration.status,
        is_enabled=integration.is_enabled,
        auto_confirm_reservations=integration.auto_confirm_reservations,
        auto_push_availability=integration.auto_push_availability,
        webhook_token=integration.webhook_token,
        config=_load_config(integration),
        has_api_key=bool(integration.encrypted_api_key),
        has_webhook_secret=bool(integration.encrypted_webhook_secret),
        last_sync_at=integration.last_sync_at,
        last_error=integration.last_error,
        webhook_url=build_webhook_url(integration.webhook_token),
        mapping_count=mapping_count,
        is_active=integration.is_active,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


def _to_mapping_read(db: Session, mapping: OtaRoomTypeMapping) -> RoomTypeMappingRead:
    room_type = db.get(RoomType, mapping.room_type_id)
    return RoomTypeMappingRead(
        id=mapping.id,
        integration_id=mapping.integration_id,
        external_room_type_id=mapping.external_room_type_id,
        external_room_type_name=mapping.external_room_type_name,
        room_type_id=mapping.room_type_id,
        room_type_name=room_type.name if room_type else None,
        is_active=mapping.is_active,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


def _to_rate_plan_mapping_read(db: Session, mapping: OtaRatePlanMapping) -> RatePlanMappingRead:
    from app.modules.pms.models import RatePlan

    plan = db.get(RatePlan, mapping.rate_plan_id)
    return RatePlanMappingRead(
        id=mapping.id,
        integration_id=mapping.integration_id,
        external_rate_id=mapping.external_rate_id,
        external_rate_name=mapping.external_rate_name,
        rate_plan_id=mapping.rate_plan_id,
        rate_plan_name=plan.name if plan else None,
        is_active=mapping.is_active,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


def _resolve_rate_plan_id(
    db: Session,
    integration: OutletOtaIntegration,
    payload: InboundOtaReservationPayload,
) -> int | None:
    if not payload.external_rate_id:
        return None
    mapping = (
        db.query(OtaRatePlanMapping)
        .filter(
            OtaRatePlanMapping.integration_id == integration.id,
            OtaRatePlanMapping.external_rate_id == payload.external_rate_id.strip(),
            OtaRatePlanMapping.is_active.is_(True),
        )
        .first()
    )
    return mapping.rate_plan_id if mapping else None


def _to_ota_reservation_read(db: Session, link: OtaReservationLink) -> OtaReservationRead:
    reservation = (
        db.query(GuestReservation)
        .filter(GuestReservation.id == link.guest_reservation_id)
        .first()
    )
    if reservation is None:
        raise NotFoundError("Linked guest reservation not found")

    room_type_name = None
    room_type = db.get(RoomType, reservation.room_type_id)
    if room_type:
        room_type_name = room_type.name

    return OtaReservationRead(
        id=link.id,
        integration_id=link.integration_id,
        guest_reservation_id=link.guest_reservation_id,
        platform=link.platform,
        external_reservation_id=link.external_reservation_id,
        external_status=link.external_status,
        confirmation_number=reservation.confirmation_number,
        guest_name=reservation.guest_name,
        guest_mobile=reservation.guest_mobile,
        reservation_status=reservation.status,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        room_type_name=room_type_name,
        total_amount=float(reservation.total_amount),
        is_active=link.is_active,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _to_sync_log_read(row: OtaSyncLog) -> OtaSyncLogRead:
    return OtaSyncLogRead(
        id=row.id,
        integration_id=row.integration_id,
        sync_type=row.sync_type.value,
        status=row.status.value,
        start_date=row.start_date,
        end_date=row.end_date,
        room_types_count=row.room_types_count,
        days_count=row.days_count,
        external_reference=row.external_reference,
        message=row.message,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
