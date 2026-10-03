from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.bookings.models import (
    BookingPlatform,
    BookingStatus,
    OutletBookingIntegration,
    TableBooking,
)
from app.modules.bookings.providers.registry import (
    PLATFORM_LABELS,
    build_webhook_url,
    get_booking_provider,
)
from app.modules.bookings.schemas import (
    BookingCreate,
    BookingRead,
    InboundBookingPayload,
    IntegrationCreate,
    IntegrationDeleteResponse,
    IntegrationRead,
    IntegrationUpdate,
    MockBookingRequest,
    PlatformInfo,
    WebhookAckResponse,
)
from app.modules.delivery.models import IntegrationStatus
from app.modules.outlets.models import Outlet
from app.modules.tables.models import RestaurantTable, TableStatus
from app.utils.encryption import decrypt_secret, encrypt_secret


def list_platforms() -> list[PlatformInfo]:
    return [
        PlatformInfo(platform=platform, label=label, description=description)
        for platform, (label, description) in PLATFORM_LABELS.items()
        if platform != BookingPlatform.DIRECT
    ]


def list_integrations(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    platform: BookingPlatform | None = None,
) -> tuple[list[IntegrationRead], int]:
    query = db.query(OutletBookingIntegration).filter(
        OutletBookingIntegration.tenant_id == tenant_id,
        OutletBookingIntegration.is_active.is_(True),
    )
    if outlet_id is not None:
        query = query.filter(OutletBookingIntegration.outlet_id == outlet_id)
    if platform is not None:
        query = query.filter(OutletBookingIntegration.platform == platform)

    rows, total = paginate_query(
        query.order_by(OutletBookingIntegration.id.desc()), page, page_size
    )
    return [_to_integration_read(row) for row in rows], total


def get_integration(db: Session, tenant_id: int, integration_id: int) -> IntegrationRead:
    row = _get_integration_entity(db, tenant_id, integration_id)
    return _to_integration_read(row)


def create_integration(
    db: Session,
    tenant_id: int,
    data: IntegrationCreate,
    default_brand_id: int | None = None,
) -> IntegrationRead:
    if data.platform == BookingPlatform.DIRECT:
        raise ConflictError("Direct bookings do not require an integration")

    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    existing = (
        db.query(OutletBookingIntegration)
        .filter(
            OutletBookingIntegration.outlet_id == data.outlet_id,
            OutletBookingIntegration.platform == data.platform,
            OutletBookingIntegration.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError(
            f"{data.platform.value} is already configured for this outlet"
        )

    integration = OutletBookingIntegration(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        platform=data.platform,
        external_store_id=data.external_store_id,
        status=IntegrationStatus.PENDING,
        is_enabled=data.is_enabled,
        auto_confirm_bookings=data.auto_confirm_bookings,
        auto_reserve_table=data.auto_reserve_table,
        webhook_token=uuid.uuid4().hex,
        config_json=json.dumps(data.config or {}),
        encrypted_api_key=encrypt_secret(data.api_key),
        encrypted_webhook_secret=encrypt_secret(data.webhook_secret),
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return _to_integration_read(integration)


def update_integration(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: IntegrationUpdate,
) -> IntegrationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    payload = data.model_dump(exclude_unset=True)

    if "external_store_id" in payload:
        integration.external_store_id = payload["external_store_id"]
    if "status" in payload:
        integration.status = payload["status"]
    if "is_enabled" in payload:
        integration.is_enabled = payload["is_enabled"]
    if "auto_confirm_bookings" in payload:
        integration.auto_confirm_bookings = payload["auto_confirm_bookings"]
    if "auto_reserve_table" in payload:
        integration.auto_reserve_table = payload["auto_reserve_table"]
    if "config" in payload and payload["config"] is not None:
        integration.config_json = json.dumps(payload["config"])
    if "api_key" in payload and payload["api_key"]:
        integration.encrypted_api_key = encrypt_secret(payload["api_key"])
    if "webhook_secret" in payload and payload["webhook_secret"]:
        integration.encrypted_webhook_secret = encrypt_secret(payload["webhook_secret"])

    db.commit()
    db.refresh(integration)
    return _to_integration_read(integration)


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
    return IntegrationDeleteResponse(
        message="Booking integration removed",
        integration_id=integration_id,
    )


async def test_integration_connection(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> IntegrationRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    provider = get_booking_provider(integration.platform)
    config = _load_config(integration)
    result = await provider.test_connection(
        external_store_id=integration.external_store_id,
        api_key=decrypt_secret(integration.encrypted_api_key),
        config=config,
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
    return _to_integration_read(integration)


def list_bookings(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    platform: BookingPlatform | None = None,
    status: BookingStatus | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> tuple[list[BookingRead], int]:
    query = db.query(TableBooking).filter(
        TableBooking.tenant_id == tenant_id,
        TableBooking.is_active.is_(True),
    )
    if outlet_id is not None:
        query = query.filter(TableBooking.outlet_id == outlet_id)
    if platform is not None:
        query = query.filter(TableBooking.platform == platform)
    if status is not None:
        query = query.filter(TableBooking.status == status)
    if from_date is not None:
        query = query.filter(TableBooking.booked_for >= from_date)
    if to_date is not None:
        query = query.filter(TableBooking.booked_for <= to_date)

    rows, total = paginate_query(query.order_by(TableBooking.booked_for.asc()), page, page_size)
    return [_to_booking_read(db, row) for row in rows], total


def get_booking(db: Session, tenant_id: int, booking_id: int) -> BookingRead:
    row = _get_booking_entity(db, tenant_id, booking_id)
    return _to_booking_read(db, row)


def create_direct_booking(
    db: Session,
    tenant_id: int,
    data: BookingCreate,
    default_brand_id: int | None = None,
) -> BookingRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    table = None
    if data.table_id is not None:
        table = _get_table(db, tenant_id, data.table_id)
        if table.outlet_id != data.outlet_id:
            raise ConflictError("Table does not belong to this outlet")

    booking = TableBooking(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        platform=BookingPlatform.DIRECT,
        external_booking_id=f"DIRECT-{uuid.uuid4().hex[:10].upper()}",
        status=BookingStatus.CONFIRMED,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_email=data.customer_email,
        guest_count=data.guest_count,
        booked_for=data.booked_for,
        duration_minutes=data.duration_minutes,
        table_id=data.table_id,
        special_requests=data.special_requests,
        notes=data.notes,
        raw_payload_json=json.dumps(data.model_dump(mode="json")),
    )
    db.add(booking)

    if table is not None:
        _reserve_table(table)

    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def confirm_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    notes: str | None = None,
    table_id: int | None = None,
) -> BookingRead:
    booking = _get_booking_entity(db, tenant_id, booking_id)
    if booking.status not in {BookingStatus.PENDING}:
        raise ConflictError("Only pending bookings can be confirmed")

    booking.status = BookingStatus.CONFIRMED
    if notes:
        booking.notes = notes

    integration = booking.integration
    if table_id is not None:
        table = _get_table(db, tenant_id, table_id)
        if table.outlet_id != booking.outlet_id:
            raise ConflictError("Table does not belong to this outlet")
        booking.table_id = table_id
        _reserve_table(table)
    elif integration and integration.auto_reserve_table:
        table = _find_suitable_table(db, booking)
        if table:
            booking.table_id = table.id
            _reserve_table(table)

    if integration:
        await _sync_external_status(integration, booking, BookingStatus.CONFIRMED)
        integration.last_sync_at = datetime.utcnow()

    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def reject_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    notes: str | None = None,
) -> BookingRead:
    booking = _get_booking_entity(db, tenant_id, booking_id)
    if booking.status not in {BookingStatus.PENDING}:
        raise ConflictError("Only pending bookings can be rejected")

    booking.status = BookingStatus.REJECTED
    if notes:
        booking.notes = notes
    _release_table(db, booking)

    integration = booking.integration
    if integration:
        await _sync_external_status(integration, booking, BookingStatus.REJECTED)

    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def cancel_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    notes: str | None = None,
) -> BookingRead:
    booking = _get_booking_entity(db, tenant_id, booking_id)
    if booking.status in {BookingStatus.COMPLETED, BookingStatus.CANCELLED, BookingStatus.REJECTED}:
        raise ConflictError("Booking cannot be cancelled in its current status")

    booking.status = BookingStatus.CANCELLED
    if notes:
        booking.notes = notes
    _release_table(db, booking)

    integration = booking.integration
    if integration and booking.external_booking_id:
        await _sync_external_status(integration, booking, BookingStatus.CANCELLED)

    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def seat_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    table_id: int,
    notes: str | None = None,
) -> BookingRead:
    booking = _get_booking_entity(db, tenant_id, booking_id)
    if booking.status not in {BookingStatus.CONFIRMED, BookingStatus.PENDING}:
        raise ConflictError("Only confirmed or pending bookings can be seated")

    table = _get_table(db, tenant_id, table_id)
    if table.outlet_id != booking.outlet_id:
        raise ConflictError("Table does not belong to this outlet")
    if table.status not in {TableStatus.AVAILABLE, TableStatus.RESERVED, TableStatus.CLEANING}:
        raise ConflictError("Table is not available for seating")

    if booking.table_id and booking.table_id != table_id:
        old_table = db.get(RestaurantTable, booking.table_id)
        if old_table:
            _apply_table_status(old_table, TableStatus.AVAILABLE)

    booking.table_id = table_id
    booking.status = BookingStatus.SEATED
    if notes:
        booking.notes = notes
    _apply_table_status(table, TableStatus.OCCUPIED)
    table.occupied_since = datetime.utcnow()

    integration = booking.integration
    if integration and booking.external_booking_id:
        await _sync_external_status(integration, booking, BookingStatus.SEATED)

    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def mark_booking_no_show(
    db: Session,
    tenant_id: int,
    booking_id: int,
    notes: str | None = None,
) -> BookingRead:
    booking = _get_booking_entity(db, tenant_id, booking_id)
    if booking.status not in {BookingStatus.CONFIRMED, BookingStatus.PENDING}:
        raise ConflictError("Booking cannot be marked as no-show in its current status")

    booking.status = BookingStatus.NO_SHOW
    if notes:
        booking.notes = notes
    _release_table(db, booking)

    integration = booking.integration
    if integration and booking.external_booking_id:
        await _sync_external_status(integration, booking, BookingStatus.NO_SHOW)

    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def complete_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    notes: str | None = None,
) -> BookingRead:
    booking = _get_booking_entity(db, tenant_id, booking_id)
    if booking.status not in {BookingStatus.SEATED, BookingStatus.CONFIRMED}:
        raise ConflictError("Booking cannot be completed in its current status")

    booking.status = BookingStatus.COMPLETED
    if notes:
        booking.notes = notes
    _release_table(db, booking)

    integration = booking.integration
    if integration and booking.external_booking_id:
        await _sync_external_status(integration, booking, BookingStatus.COMPLETED)

    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def ingest_inbound_booking(
    db: Session,
    webhook_token: str,
    payload: InboundBookingPayload,
    raw_payload: dict | None = None,
) -> WebhookAckResponse:
    integration = (
        db.query(OutletBookingIntegration)
        .filter(
            OutletBookingIntegration.webhook_token == webhook_token,
            OutletBookingIntegration.is_active.is_(True),
        )
        .first()
    )
    if integration is None:
        raise NotFoundError("Booking integration not found")
    if not integration.is_enabled:
        raise ConflictError("Booking integration is disabled")

    existing = (
        db.query(TableBooking)
        .filter(
            TableBooking.integration_id == integration.id,
            TableBooking.external_booking_id == payload.external_booking_id,
            TableBooking.is_active.is_(True),
        )
        .first()
    )
    if existing:
        return WebhookAckResponse(
            success=True,
            message="Booking already ingested",
            booking_id=existing.id,
        )

    initial_status = (
        BookingStatus.CONFIRMED
        if integration.auto_confirm_bookings
        else BookingStatus.PENDING
    )

    booking = TableBooking(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        outlet_id=integration.outlet_id,
        platform=integration.platform,
        external_booking_id=payload.external_booking_id,
        status=initial_status,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        guest_count=payload.guest_count,
        booked_for=payload.booked_for,
        duration_minutes=payload.duration_minutes,
        special_requests=payload.special_requests,
        notes=payload.notes,
        raw_payload_json=json.dumps(raw_payload or payload.model_dump(mode="json")),
    )
    db.add(booking)
    db.flush()

    if initial_status == BookingStatus.CONFIRMED and integration.auto_reserve_table:
        table = _find_suitable_table(db, booking)
        if table:
            booking.table_id = table.id
            _reserve_table(table)

    integration.last_sync_at = datetime.utcnow()
    integration.last_error = None
    db.commit()
    return WebhookAckResponse(
        success=True,
        message="Booking ingested",
        booking_id=booking.id,
    )


async def simulate_mock_booking(
    db: Session,
    tenant_id: int,
    integration_id: int,
    data: MockBookingRequest,
) -> BookingRead:
    integration = _get_integration_entity(db, tenant_id, integration_id)
    if not integration.is_enabled:
        raise ConflictError("Enable the integration before simulating bookings")

    booked_for = data.booked_for or (datetime.utcnow() + timedelta(hours=2))
    payload = InboundBookingPayload(
        external_booking_id=f"MOCK-{uuid.uuid4().hex[:10].upper()}",
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        guest_count=data.guest_count,
        booked_for=booked_for,
        duration_minutes=data.duration_minutes,
        special_requests=data.special_requests,
        notes="Simulated aggregator booking",
    )

    initial_status = (
        BookingStatus.CONFIRMED
        if integration.auto_confirm_bookings
        else BookingStatus.PENDING
    )

    booking = TableBooking(
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        integration_id=integration.id,
        outlet_id=integration.outlet_id,
        platform=integration.platform,
        external_booking_id=payload.external_booking_id,
        status=initial_status,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        guest_count=payload.guest_count,
        booked_for=payload.booked_for,
        duration_minutes=payload.duration_minutes,
        special_requests=payload.special_requests,
        notes=payload.notes,
        raw_payload_json=json.dumps(payload.model_dump(mode="json")),
    )
    db.add(booking)
    db.flush()

    if initial_status == BookingStatus.CONFIRMED and integration.auto_reserve_table:
        table = _find_suitable_table(db, booking)
        if table:
            booking.table_id = table.id
            _reserve_table(table)

    integration.last_sync_at = datetime.utcnow()
    integration.last_error = None
    db.commit()
    db.refresh(booking)
    return _to_booking_read(db, booking)


async def _sync_external_status(
    integration: OutletBookingIntegration,
    booking: TableBooking,
    status: BookingStatus,
) -> None:
    if not booking.external_booking_id:
        return
    provider = get_booking_provider(integration.platform)
    config = _load_config(integration)
    result = await provider.update_booking_status(
        external_booking_id=booking.external_booking_id,
        external_store_id=integration.external_store_id,
        api_key=decrypt_secret(integration.encrypted_api_key),
        status=status,
        config=config,
    )
    if not result.success:
        integration.last_error = result.error_message or "Failed to sync status to platform"
    else:
        integration.last_error = None


def _find_suitable_table(db: Session, booking: TableBooking) -> RestaurantTable | None:
    return (
        db.query(RestaurantTable)
        .filter(
            RestaurantTable.outlet_id == booking.outlet_id,
            RestaurantTable.tenant_id == booking.tenant_id,
            RestaurantTable.is_active.is_(True),
            RestaurantTable.status.in_([TableStatus.AVAILABLE, TableStatus.CLEANING]),
            RestaurantTable.capacity >= booking.guest_count,
        )
        .order_by(RestaurantTable.capacity.asc())
        .first()
    )


def _reserve_table(table: RestaurantTable) -> None:
    if table.status in {TableStatus.AVAILABLE, TableStatus.CLEANING}:
        _apply_table_status(table, TableStatus.RESERVED)


def _release_table(db: Session, booking: TableBooking) -> None:
    if not booking.table_id:
        return
    table = db.get(RestaurantTable, booking.table_id)
    if table and table.status == TableStatus.RESERVED:
        _apply_table_status(table, TableStatus.AVAILABLE)


def _apply_table_status(table: RestaurantTable, status: TableStatus) -> None:
    table.status = status


def _load_config(integration: OutletBookingIntegration) -> dict:
    try:
        return json.loads(integration.config_json or "{}")
    except json.JSONDecodeError:
        return {}


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_table(db: Session, tenant_id: int, table_id: int) -> RestaurantTable:
    table = (
        db.query(RestaurantTable)
        .filter(
            RestaurantTable.id == table_id,
            RestaurantTable.tenant_id == tenant_id,
            RestaurantTable.is_active.is_(True),
        )
        .first()
    )
    if table is None:
        raise NotFoundError("Table not found")
    return table


def _get_integration_entity(
    db: Session,
    tenant_id: int,
    integration_id: int,
) -> OutletBookingIntegration:
    row = (
        db.query(OutletBookingIntegration)
        .filter(
            OutletBookingIntegration.id == integration_id,
            OutletBookingIntegration.tenant_id == tenant_id,
            OutletBookingIntegration.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Booking integration not found")
    return row


def _get_booking_entity(db: Session, tenant_id: int, booking_id: int) -> TableBooking:
    row = (
        db.query(TableBooking)
        .options(joinedload(TableBooking.integration))
        .filter(
            TableBooking.id == booking_id,
            TableBooking.tenant_id == tenant_id,
            TableBooking.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Booking not found")
    return row


def _to_integration_read(integration: OutletBookingIntegration) -> IntegrationRead:
    return IntegrationRead(
        id=integration.id,
        tenant_id=integration.tenant_id,
        brand_id=integration.brand_id,
        outlet_id=integration.outlet_id,
        platform=integration.platform,
        external_store_id=integration.external_store_id,
        status=integration.status,
        is_enabled=integration.is_enabled,
        auto_confirm_bookings=integration.auto_confirm_bookings,
        auto_reserve_table=integration.auto_reserve_table,
        webhook_token=integration.webhook_token,
        config=_load_config(integration),
        has_api_key=bool(integration.encrypted_api_key),
        has_webhook_secret=bool(integration.encrypted_webhook_secret),
        last_sync_at=integration.last_sync_at,
        last_error=integration.last_error,
        webhook_url=build_webhook_url(integration.webhook_token),
        is_active=integration.is_active,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


def _to_booking_read(db: Session, booking: TableBooking) -> BookingRead:
    table_number = None
    if booking.table_id:
        table = db.get(RestaurantTable, booking.table_id)
        table_number = table.table_number if table else None

    return BookingRead(
        id=booking.id,
        integration_id=booking.integration_id,
        outlet_id=booking.outlet_id,
        platform=booking.platform,
        external_booking_id=booking.external_booking_id,
        status=booking.status,
        customer_name=booking.customer_name,
        customer_phone=booking.customer_phone,
        customer_email=booking.customer_email,
        guest_count=booking.guest_count,
        booked_for=booking.booked_for,
        duration_minutes=booking.duration_minutes,
        table_id=booking.table_id,
        table_number=table_number,
        special_requests=booking.special_requests,
        notes=booking.notes,
        is_active=booking.is_active,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
    )
