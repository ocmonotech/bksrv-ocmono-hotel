from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.outlets.models import Outlet
from app.modules.spa import service
from app.modules.spa.models import SpaBookingStatus, SpaServiceCategory
from app.modules.spa.schemas import (
    SpaAvailabilityRead,
    SpaBookingAssignRequest,
    SpaBookingCompleteRequest,
    SpaBookingCreate,
    SpaBookingRead,
    SpaBookingUpdate,
    SpaDashboard,
    SpaCalendarRead,
    PublicSpaBookingCreate,
    PublicSpaBookingResponse,
    PublicSpaServiceRead,
    SpaBookingConfirmRequest,
    SpaNotificationKind,
    SpaNotificationRequest,
    SpaNotificationResponse,
    SpaServiceCreate,
    SpaServiceRead,
    SpaServiceUpdate,
    SpaTherapistCreate,
    SpaTherapistRead,
    SpaTherapistUpdate,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/public/services", response_model=list[PublicSpaServiceRead])
def list_public_services(
    outlet_id: int = Query(...),
    category: SpaServiceCategory | None = Query(None),
    db: Session = Depends(get_db),
) -> list[PublicSpaServiceRead]:
    return service.list_public_services(db, outlet_id, category=category)


@router.get("/public/services/{service_id}/availability", response_model=SpaAvailabilityRead)
def get_public_service_availability(
    service_id: int,
    outlet_id: int = Query(...),
    target_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
) -> SpaAvailabilityRead:
    return service.get_public_service_availability(db, outlet_id, service_id, target_date)


@router.post("/public/bookings", response_model=PublicSpaBookingResponse, status_code=status.HTTP_201_CREATED)
async def submit_public_booking(
    body: PublicSpaBookingCreate,
    db: Session = Depends(get_db),
) -> PublicSpaBookingResponse:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    result = await service.submit_public_booking(db, body)
    outlet = db.query(Outlet).filter(Outlet.id == body.outlet_id).first()
    if outlet is not None:
        await service.send_public_booking_acknowledgment(db, outlet.tenant_id, result.booking_id)
        booking = service.get_booking(db, outlet.tenant_id, result.booking_id)
        await automation_service.dispatch_trigger(
            db,
            outlet.tenant_id,
            AutomationTriggerType.SPA_BOOKING_CREATED,
            service.build_booking_automation_payload(booking),
        )
    return result


@router.get("/dashboard", response_model=SpaDashboard)
def get_dashboard(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_READ)),
) -> SpaDashboard:
    return service.get_dashboard(db, current_user.tenant_id, outlet_id=outlet_id)


@router.get("/services", response_model=PaginatedSuccessResponse[SpaServiceRead])
def list_services(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    outlet_id: int | None = Query(None),
    category: SpaServiceCategory | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_READ)),
) -> PaginatedSuccessResponse[SpaServiceRead]:
    items, total = service.list_services(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        category=category,
        include_inactive=include_inactive,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/services", response_model=SpaServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(
    body: SpaServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaServiceRead:
    return service.create_service(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/services/{service_id}", response_model=SpaServiceRead)
def update_service(
    service_id: int,
    body: SpaServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaServiceRead:
    return service.update_service(db, current_user.tenant_id, service_id, body)


@router.get("/services/{service_id}/availability", response_model=SpaAvailabilityRead)
def get_service_availability(
    service_id: int,
    target_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_READ)),
) -> SpaAvailabilityRead:
    return service.get_service_availability(db, current_user.tenant_id, service_id, target_date)


@router.get("/bookings", response_model=PaginatedSuccessResponse[SpaBookingRead])
def list_bookings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    service_id: int | None = Query(None),
    status: SpaBookingStatus | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    guest_reservation_id: int | None = Query(None),
    assigned_staff_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_READ)),
) -> PaginatedSuccessResponse[SpaBookingRead]:
    items, total = service.list_bookings(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        service_id=service_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        guest_reservation_id=guest_reservation_id,
        assigned_staff_id=assigned_staff_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/bookings", response_model=SpaBookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: SpaBookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
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
        AutomationTriggerType.SPA_BOOKING_CREATED,
        service.build_booking_automation_payload(result),
    )
    return result


@router.get("/bookings/{booking_id}", response_model=SpaBookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_READ)),
) -> SpaBookingRead:
    return service.get_booking(db, current_user.tenant_id, booking_id)


@router.patch("/bookings/{booking_id}", response_model=SpaBookingRead)
def update_booking(
    booking_id: int,
    body: SpaBookingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    return service.update_booking(db, current_user.tenant_id, booking_id, body)


@router.post("/bookings/{booking_id}/confirm", response_model=SpaBookingRead)
async def confirm_booking(
    booking_id: int,
    body: SpaBookingConfirmRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    from app.modules.automation import service as automation_service
    from app.modules.automation.models import AutomationTriggerType

    payload = body or SpaBookingConfirmRequest()
    result = service.confirm_booking(db, current_user.tenant_id, booking_id)
    if payload.send_sms or payload.send_email or payload.send_whatsapp:
        await service.send_booking_notifications(
            db,
            current_user.tenant_id,
            current_user.id,
            booking_id,
            kind=SpaNotificationKind.CONFIRMATION,
            send_sms=payload.send_sms,
            send_email=payload.send_email,
            send_whatsapp=payload.send_whatsapp,
        )
    await automation_service.dispatch_trigger(
        db,
        current_user.tenant_id,
        AutomationTriggerType.SPA_BOOKING_CONFIRMED,
        service.build_booking_automation_payload(result),
    )
    return result


@router.post("/bookings/{booking_id}/send-notification", response_model=SpaNotificationResponse)
async def send_booking_notification(
    booking_id: int,
    body: SpaNotificationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaNotificationResponse:
    payload = body or SpaNotificationRequest()
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


@router.post("/bookings/{booking_id}/start", response_model=SpaBookingRead)
def start_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    return service.start_booking(db, current_user.tenant_id, booking_id)


@router.post("/bookings/{booking_id}/complete", response_model=SpaBookingRead)
def complete_booking(
    booking_id: int,
    body: SpaBookingCompleteRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    payload = body or SpaBookingCompleteRequest()
    return service.complete_booking(
        db,
        current_user.tenant_id,
        booking_id,
        post_to_folio=payload.post_to_folio,
        posted_by=current_user.id,
    )


@router.post("/bookings/{booking_id}/post-to-folio", response_model=SpaBookingRead)
def post_booking_to_folio(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    return service.post_booking_to_folio(
        db,
        current_user.tenant_id,
        booking_id,
        posted_by=current_user.id,
    )


@router.post("/bookings/{booking_id}/cancel", response_model=SpaBookingRead)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    return service.cancel_booking(db, current_user.tenant_id, booking_id)


@router.post("/bookings/{booking_id}/no-show", response_model=SpaBookingRead)
def mark_no_show(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    return service.mark_no_show(db, current_user.tenant_id, booking_id)


@router.get("/therapists", response_model=list[SpaTherapistRead])
def list_therapists(
    outlet_id: int | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_READ)),
) -> list[SpaTherapistRead]:
    return service.list_therapists(
        db,
        current_user.tenant_id,
        outlet_id=outlet_id,
        include_inactive=include_inactive,
    )


@router.post("/therapists", response_model=SpaTherapistRead, status_code=status.HTTP_201_CREATED)
def create_therapist(
    body: SpaTherapistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaTherapistRead:
    return service.create_therapist(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/therapists/{therapist_id}", response_model=SpaTherapistRead)
def update_therapist(
    therapist_id: int,
    body: SpaTherapistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaTherapistRead:
    return service.update_therapist(db, current_user.tenant_id, therapist_id, body)


@router.get("/calendar", response_model=SpaCalendarRead)
def get_therapist_calendar(
    outlet_id: int = Query(...),
    target_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_READ)),
) -> SpaCalendarRead:
    return service.get_therapist_calendar(db, current_user.tenant_id, outlet_id, target_date)


@router.post("/bookings/{booking_id}/assign", response_model=SpaBookingRead)
def assign_booking_staff(
    booking_id: int,
    body: SpaBookingAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SPA_WRITE)),
) -> SpaBookingRead:
    return service.assign_booking_staff(
        db,
        current_user.tenant_id,
        booking_id,
        body.assigned_staff_id,
    )
