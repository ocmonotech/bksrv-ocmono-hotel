from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.banquet import service
from app.modules.banquet.models import BanquetBookingStatus, BanquetVenueType
from app.modules.banquet.schemas import (
    BanquetAvailabilityRead,
    BanquetBookingCompleteRequest,
    BanquetBookingConfirmRequest,
    BanquetBookingCreate,
    BanquetBookingRead,
    BanquetBookingUpdate,
    BanquetCalendarRead,
    BanquetDashboard,
    BanquetNotificationKind,
    BanquetNotificationRequest,
    BanquetNotificationResponse,
    BanquetVenueCreate,
    BanquetVenueRead,
    BanquetVenueUpdate,
    PublicBanquetInquiryCreate,
    PublicBanquetInquiryResponse,
    PublicBanquetVenueRead,
)
from app.modules.outlets.models import Outlet
from app.modules.users.models import User

router = APIRouter()


@router.get("/public/venues", response_model=list[PublicBanquetVenueRead])
def list_public_venues(
    outlet_id: int = Query(...),
    venue_type: BanquetVenueType | None = Query(None),
    db: Session = Depends(get_db),
) -> list[PublicBanquetVenueRead]:
    return service.list_public_venues(db, outlet_id, venue_type=venue_type)


@router.get("/public/venues/{venue_id}/availability", response_model=BanquetAvailabilityRead)
def get_public_venue_availability(
    venue_id: int,
    outlet_id: int = Query(...),
    target_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
) -> BanquetAvailabilityRead:
    return service.get_public_venue_availability(db, outlet_id, venue_id, target_date)


@router.post("/public/inquiries", response_model=PublicBanquetInquiryResponse, status_code=status.HTTP_201_CREATED)
async def submit_public_inquiry(
    body: PublicBanquetInquiryCreate,
    db: Session = Depends(get_db),
) -> PublicBanquetInquiryResponse:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    result = service.submit_public_inquiry(db, body)
    outlet = db.query(Outlet).filter(Outlet.id == body.outlet_id).first()
    if outlet is not None:
        await service.send_public_inquiry_acknowledgment(db, outlet.tenant_id, result.booking_id)
        booking = service.get_booking(db, outlet.tenant_id, result.booking_id)
        await automation_service.dispatch_trigger(
            db,
            outlet.tenant_id,
            AutomationTriggerType.BANQUET_BOOKING_CREATED,
            service.build_booking_automation_payload(booking),
        )
    return result


@router.get("/dashboard", response_model=BanquetDashboard)
def get_dashboard(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_READ)),
) -> BanquetDashboard:
    return service.get_dashboard(db, current_user.tenant_id, outlet_id=outlet_id)


@router.get("/calendar", response_model=BanquetCalendarRead)
def get_venue_calendar(
    outlet_id: int = Query(...),
    target_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_READ)),
) -> BanquetCalendarRead:
    return service.get_venue_calendar(db, current_user.tenant_id, outlet_id, target_date)


@router.get("/venues", response_model=PaginatedSuccessResponse[BanquetVenueRead])
def list_venues(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    outlet_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_READ)),
) -> PaginatedSuccessResponse[BanquetVenueRead]:
    items, total = service.list_venues(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        include_inactive=include_inactive,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/venues", response_model=BanquetVenueRead, status_code=status.HTTP_201_CREATED)
def create_venue(
    body: BanquetVenueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetVenueRead:
    return service.create_venue(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/venues/{venue_id}", response_model=BanquetVenueRead)
def update_venue(
    venue_id: int,
    body: BanquetVenueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetVenueRead:
    return service.update_venue(db, current_user.tenant_id, venue_id, body)


@router.get("/bookings", response_model=PaginatedSuccessResponse[BanquetBookingRead])
def list_bookings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    venue_id: int | None = Query(None),
    status: BanquetBookingStatus | None = Query(None),
    guest_reservation_id: int | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_READ)),
) -> PaginatedSuccessResponse[BanquetBookingRead]:
    items, total = service.list_bookings(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        venue_id=venue_id,
        status=status,
        guest_reservation_id=guest_reservation_id,
        from_date=from_date,
        to_date=to_date,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/bookings", response_model=BanquetBookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BanquetBookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetBookingRead:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    result = service.create_booking(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )
    await automation_service.dispatch_trigger(
        db,
        current_user.tenant_id,
        AutomationTriggerType.BANQUET_BOOKING_CREATED,
        service.build_booking_automation_payload(result),
    )
    return result


@router.get("/bookings/{booking_id}", response_model=BanquetBookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_READ)),
) -> BanquetBookingRead:
    return service.get_booking(db, current_user.tenant_id, booking_id)


@router.patch("/bookings/{booking_id}", response_model=BanquetBookingRead)
def update_booking(
    booking_id: int,
    body: BanquetBookingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetBookingRead:
    return service.update_booking(db, current_user.tenant_id, booking_id, body)


@router.post("/bookings/{booking_id}/confirm", response_model=BanquetBookingRead)
async def confirm_booking(
    booking_id: int,
    body: BanquetBookingConfirmRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetBookingRead:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    payload = body or BanquetBookingConfirmRequest()
    result = service.confirm_booking(db, current_user.tenant_id, booking_id)
    if payload.send_sms or payload.send_email or payload.send_whatsapp:
        await service.send_booking_notifications(
            db,
            current_user.tenant_id,
            current_user.id,
            booking_id,
            kind=BanquetNotificationKind.CONFIRMATION,
            send_sms=payload.send_sms,
            send_email=payload.send_email,
            send_whatsapp=payload.send_whatsapp,
        )
    await automation_service.dispatch_trigger(
        db,
        current_user.tenant_id,
        AutomationTriggerType.BANQUET_BOOKING_CONFIRMED,
        service.build_booking_automation_payload(result),
    )
    return result


@router.post("/bookings/{booking_id}/send-notification", response_model=BanquetNotificationResponse)
async def send_booking_notification(
    booking_id: int,
    body: BanquetNotificationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetNotificationResponse:
    payload = body or BanquetNotificationRequest()
    return await service.send_booking_notifications(
        db,
        current_user.tenant_id,
        current_user.id,
        booking_id,
        kind=payload.kind,
        send_sms=payload.send_sms,
        send_email=payload.send_email,
        send_whatsapp=payload.send_whatsapp,
    )


@router.post("/bookings/{booking_id}/complete", response_model=BanquetBookingRead)
def complete_booking(
    booking_id: int,
    body: BanquetBookingCompleteRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetBookingRead:
    payload = body or BanquetBookingCompleteRequest()
    return service.complete_booking(
        db,
        current_user.tenant_id,
        booking_id,
        post_to_folio=payload.post_to_folio,
        posted_by=current_user.id,
    )


@router.post("/bookings/{booking_id}/post-deposit-to-folio", response_model=BanquetBookingRead)
def post_deposit_to_folio(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetBookingRead:
    return service.post_deposit_to_folio(
        db,
        current_user.tenant_id,
        booking_id,
        posted_by=current_user.id,
    )


@router.post("/bookings/{booking_id}/post-to-folio", response_model=BanquetBookingRead)
def post_booking_to_folio(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetBookingRead:
    return service.post_booking_to_folio(
        db,
        current_user.tenant_id,
        booking_id,
        posted_by=current_user.id,
    )


@router.post("/bookings/{booking_id}/cancel", response_model=BanquetBookingRead)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BANQUET_WRITE)),
) -> BanquetBookingRead:
    return service.cancel_booking(db, current_user.tenant_id, booking_id)
