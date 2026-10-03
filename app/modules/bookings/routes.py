from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.bookings import service
from app.modules.bookings.models import BookingPlatform, BookingStatus
from app.modules.bookings.providers.registry import get_booking_provider
from app.modules.bookings.schemas import (
    BookingAction,
    BookingCreate,
    BookingRead,
    InboundBookingPayload,
    IntegrationCreate,
    IntegrationDeleteResponse,
    IntegrationRead,
    IntegrationUpdate,
    MockBookingRequest,
    PlatformInfo,
    SeatBookingRequest,
    WebhookAckResponse,
)
from app.modules.users.models import User
from app.utils.encryption import decrypt_secret

router = APIRouter()


@router.get("/platforms", response_model=list[PlatformInfo])
def list_platforms(
    current_user: User = Depends(require_permission(Permission.BOOKING_READ)),
) -> list[PlatformInfo]:
    return service.list_platforms()


@router.get("/integrations", response_model=PaginatedSuccessResponse[IntegrationRead])
def list_integrations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    platform: BookingPlatform | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_READ)),
) -> PaginatedSuccessResponse[IntegrationRead]:
    items, total = service.list_integrations(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        platform=platform,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/integrations", response_model=IntegrationRead, status_code=status.HTTP_201_CREATED)
def create_integration(
    body: IntegrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> IntegrationRead:
    return service.create_integration(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/integrations/{integration_id}", response_model=IntegrationRead)
def get_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_READ)),
) -> IntegrationRead:
    return service.get_integration(db, current_user.tenant_id, integration_id)


@router.patch("/integrations/{integration_id}", response_model=IntegrationRead)
def update_integration(
    integration_id: int,
    body: IntegrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> IntegrationRead:
    return service.update_integration(db, current_user.tenant_id, integration_id, body)


@router.delete("/integrations/{integration_id}", response_model=IntegrationDeleteResponse)
def delete_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> IntegrationDeleteResponse:
    return service.delete_integration(db, current_user.tenant_id, integration_id)


@router.post("/integrations/{integration_id}/test", response_model=IntegrationRead)
async def test_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> IntegrationRead:
    return await service.test_integration_connection(db, current_user.tenant_id, integration_id)


@router.get("/reservations", response_model=PaginatedSuccessResponse[BookingRead])
def list_bookings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    platform: BookingPlatform | None = Query(None),
    status: BookingStatus | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_READ)),
) -> PaginatedSuccessResponse[BookingRead]:
    items, total = service.list_bookings(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        platform=platform,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/reservations", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    body: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    return service.create_direct_booking(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/reservations/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_READ)),
) -> BookingRead:
    return service.get_booking(db, current_user.tenant_id, booking_id)


@router.post("/reservations/{booking_id}/confirm", response_model=BookingRead)
async def confirm_booking(
    booking_id: int,
    body: BookingAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    notes = body.notes if body else None
    return await service.confirm_booking(db, current_user.tenant_id, booking_id, notes=notes)


@router.post("/reservations/{booking_id}/reject", response_model=BookingRead)
async def reject_booking(
    booking_id: int,
    body: BookingAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    notes = body.notes if body else None
    return await service.reject_booking(db, current_user.tenant_id, booking_id, notes=notes)


@router.post("/reservations/{booking_id}/cancel", response_model=BookingRead)
async def cancel_booking(
    booking_id: int,
    body: BookingAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    notes = body.notes if body else None
    return await service.cancel_booking(db, current_user.tenant_id, booking_id, notes=notes)


@router.post("/reservations/{booking_id}/seat", response_model=BookingRead)
async def seat_booking(
    booking_id: int,
    body: SeatBookingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    return await service.seat_booking(
        db,
        current_user.tenant_id,
        booking_id,
        body.table_id,
        notes=body.notes,
    )


@router.post("/reservations/{booking_id}/no-show", response_model=BookingRead)
async def mark_no_show(
    booking_id: int,
    body: BookingAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    notes = body.notes if body else None
    return await service.mark_booking_no_show(db, current_user.tenant_id, booking_id, notes=notes)


@router.post("/reservations/{booking_id}/complete", response_model=BookingRead)
async def complete_booking(
    booking_id: int,
    body: BookingAction | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    notes = body.notes if body else None
    return await service.complete_booking(db, current_user.tenant_id, booking_id, notes=notes)


@router.post(
    "/integrations/{integration_id}/simulate-booking",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
)
async def simulate_mock_booking(
    integration_id: int,
    body: MockBookingRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BOOKING_WRITE)),
) -> BookingRead:
    return await service.simulate_mock_booking(
        db,
        current_user.tenant_id,
        integration_id,
        body or MockBookingRequest(),
    )


@router.post("/webhooks/{webhook_token}", response_model=WebhookAckResponse)
async def receive_booking_webhook(
    webhook_token: str,
    body: InboundBookingPayload,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
) -> WebhookAckResponse:
    from app.modules.bookings.models import OutletBookingIntegration

    integration = (
        db.query(OutletBookingIntegration)
        .filter(
            OutletBookingIntegration.webhook_token == webhook_token,
            OutletBookingIntegration.is_active.is_(True),
        )
        .first()
    )
    if integration is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Booking integration not found")

    provider = get_booking_provider(integration.platform)
    payload_bytes = body.model_dump_json().encode("utf-8")
    if not provider.verify_webhook_signature(
        payload=payload_bytes,
        signature=x_signature,
        webhook_secret=decrypt_secret(integration.encrypted_webhook_secret),
    ):
        from app.core.exceptions import ForbiddenError

        raise ForbiddenError("Invalid webhook signature")

    return await service.ingest_inbound_booking(
        db,
        webhook_token,
        body,
        raw_payload=body.model_dump(mode="json"),
    )
