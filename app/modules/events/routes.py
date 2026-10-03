from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.events import service
from app.modules.events.models import EventStatus, EventType
from app.modules.events.schemas import (
    BirthdayOpportunityRead,
    EventActivityCreate,
    EventActivityRead,
    EventCancelRequest,
    EventConfirmRequest,
    EventCreate,
    EventDeleteResponse,
    EventDetailRead,
    EventFromLeadCreate,
    EventPackageRead,
    EventPosOrderResponse,
    EventPreOrderRead,
    EventPreOrdersReplace,
    EventRead,
    EventUpdate,
    EventWhatsAppRequest,
    EventWhatsAppResponse,
    PublicEventInquiryCreate,
    PublicEventInquiryResponse,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("", response_model=PaginatedSuccessResponse[EventRead])
def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    status: EventStatus | None = Query(None),
    event_type: EventType | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    assigned_to: int | None = Query(None),
    customer_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_READ)),
) -> PaginatedSuccessResponse[EventRead]:
    items, total = service.list_events(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        status=status,
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        assigned_to=assigned_to,
        customer_id=customer_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    body: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventRead:
    return service.create_event(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/from-lead", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event_from_lead(
    body: EventFromLeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventRead:
    return service.create_event_from_lead(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/packages", response_model=list[EventPackageRead])
def list_event_packages(
    current_user: User = Depends(require_permission(Permission.EVENTS_READ)),
) -> list[EventPackageRead]:
    return service.list_event_packages()


@router.get("/birthday-opportunities", response_model=list[BirthdayOpportunityRead])
def list_birthday_opportunities(
    days_ahead: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_READ)),
) -> list[BirthdayOpportunityRead]:
    return service.list_birthday_opportunities(db, current_user.tenant_id, days_ahead=days_ahead)


@router.get("/public/packages", response_model=list[EventPackageRead])
def list_public_event_packages() -> list[EventPackageRead]:
    return service.list_event_packages()


@router.post("/public/inquiry", response_model=PublicEventInquiryResponse, status_code=status.HTTP_201_CREATED)
def submit_public_event_inquiry(
    body: PublicEventInquiryCreate,
    db: Session = Depends(get_db),
) -> PublicEventInquiryResponse:
    return service.submit_public_inquiry(db, body)


@router.get("/{event_id}", response_model=EventDetailRead)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_READ)),
) -> EventDetailRead:
    return service.get_event(db, current_user.tenant_id, event_id)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(
    event_id: int,
    body: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventRead:
    return service.update_event(db, current_user.tenant_id, event_id, body)


@router.delete("/{event_id}", response_model=EventDeleteResponse)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventDeleteResponse:
    return service.delete_event(db, current_user.tenant_id, event_id)


@router.post("/{event_id}/confirm", response_model=EventRead)
async def confirm_event(
    event_id: int,
    body: EventConfirmRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventRead:
    from app.modules.automation.models import AutomationTriggerType
    from app.modules.automation import service as automation_service

    payload = body or EventConfirmRequest()
    result = service.confirm_event(
        db,
        current_user.tenant_id,
        current_user.id,
        event_id,
        table_ids=payload.table_ids or None,
        notes=payload.notes,
    )
    if payload.send_whatsapp:
        await service.send_event_whatsapp(
            db,
            current_user.tenant_id,
            current_user.id,
            event_id,
        )
    await automation_service.dispatch_trigger(
        db,
        current_user.tenant_id,
        AutomationTriggerType.EVENT_CONFIRMED,
        {
            "event_id": result.id,
            "title": result.title,
            "event_type": result.event_type.value,
            "customer_name": result.customer_name,
            "customer_phone": result.customer_phone,
            "event_date": str(result.event_date),
            "outlet_id": result.outlet_id,
        },
    )
    return result


@router.post("/{event_id}/cancel", response_model=EventRead)
def cancel_event(
    event_id: int,
    body: EventCancelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventRead:
    notes = body.notes if body else None
    return service.cancel_event(db, current_user.tenant_id, current_user.id, event_id, notes=notes)


@router.post("/{event_id}/complete", response_model=EventRead)
def complete_event(
    event_id: int,
    body: EventCancelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventRead:
    notes = body.notes if body else None
    return service.complete_event(db, current_user.tenant_id, current_user.id, event_id, notes=notes)


@router.post("/{event_id}/send-whatsapp", response_model=EventWhatsAppResponse)
async def send_event_whatsapp(
    event_id: int,
    body: EventWhatsAppRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventWhatsAppResponse:
    payload = body or EventWhatsAppRequest()
    return await service.send_event_whatsapp(
        db,
        current_user.tenant_id,
        current_user.id,
        event_id,
        kind=payload.kind,
    )


@router.post("/{event_id}/activities", response_model=EventActivityRead, status_code=status.HTTP_201_CREATED)
def add_event_activity(
    event_id: int,
    body: EventActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventActivityRead:
    return service.add_activity(db, current_user.tenant_id, current_user.id, event_id, body)


@router.get("/{event_id}/preorders", response_model=list[EventPreOrderRead])
def list_event_preorders(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_READ)),
) -> list[EventPreOrderRead]:
    return service.list_preorders(db, current_user.tenant_id, event_id)


@router.put("/{event_id}/preorders", response_model=list[EventPreOrderRead])
def replace_event_preorders(
    event_id: int,
    body: EventPreOrdersReplace,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> list[EventPreOrderRead]:
    return service.replace_preorders(
        db,
        current_user.tenant_id,
        current_user.id,
        event_id,
        body.items,
    )


@router.post("/{event_id}/create-pos-order", response_model=EventPosOrderResponse)
def create_event_pos_order(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EVENTS_WRITE)),
) -> EventPosOrderResponse:
    return service.create_pos_order_from_event(
        db,
        current_user.tenant_id,
        current_user.id,
        event_id,
    )
