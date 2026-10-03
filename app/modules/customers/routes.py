from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.customers import service
from app.modules.customers.models import CustomerStatus
from app.modules.customers.schemas import (
    CustomerCreate,
    CustomerProfileRead,
    CustomerRead,
    CustomerTagAssign,
    CustomerUpdate,
    CustomerVisitRead,
    FeedbackCreate,
    FeedbackRead,
    Guest360Read,
    InactiveCustomerRead,
    VipCustomerRead,
)
from app.modules.users.models import User

router = APIRouter()


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> CustomerRead:
    return service.create_customer(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("", response_model=PaginatedSuccessResponse[CustomerRead])
def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    brand_id: int | None = Query(None),
    status: CustomerStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> PaginatedSuccessResponse[CustomerRead]:
    items, total = service.list_customers(
        db,
        current_user.tenant_id,
        page,
        page_size,
        search=search,
        brand_id=brand_id,
        status=status,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/vip", response_model=PaginatedSuccessResponse[VipCustomerRead])
def get_vip_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_spend: float = Query(service.DEFAULT_VIP_MIN_SPEND, ge=0),
    min_loyalty_points: int = Query(service.DEFAULT_VIP_MIN_LOYALTY_POINTS, ge=0),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> PaginatedSuccessResponse[VipCustomerRead]:
    items, total = service.get_vip_customers(
        db,
        current_user.tenant_id,
        page,
        page_size,
        min_spend=min_spend,
        min_loyalty_points=min_loyalty_points,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/inactive", response_model=PaginatedSuccessResponse[InactiveCustomerRead])
def get_inactive_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    inactive_days: int = Query(service.DEFAULT_INACTIVE_DAYS, ge=1),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> PaginatedSuccessResponse[InactiveCustomerRead]:
    items, total = service.get_inactive_customers(
        db,
        current_user.tenant_id,
        page,
        page_size,
        inactive_days=inactive_days,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def add_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> FeedbackRead:
    return service.add_feedback(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/{customer_id}", response_model=CustomerProfileRead)
def get_customer_profile(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> CustomerProfileRead:
    return service.get_customer_profile(db, current_user.tenant_id, customer_id)


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> CustomerRead:
    return service.update_customer(db, current_user.tenant_id, customer_id, body)


@router.post("/{customer_id}/tags", response_model=CustomerProfileRead)
def add_customer_tag(
    customer_id: int,
    body: CustomerTagAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> CustomerProfileRead:
    return service.add_customer_tag(
        db,
        current_user.tenant_id,
        customer_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.delete("/{customer_id}/tags/{tag_id}", response_model=CustomerProfileRead)
def remove_customer_tag(
    customer_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> CustomerProfileRead:
    return service.remove_customer_tag(db, current_user.tenant_id, customer_id, tag_id)


@router.get("/{customer_id}/visits", response_model=PaginatedSuccessResponse[CustomerVisitRead])
def get_customer_visits(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> PaginatedSuccessResponse[CustomerVisitRead]:
    items, total = service.get_customer_visits(
        db, current_user.tenant_id, customer_id, page, page_size
    )
    return success_paginated(items, total, page, page_size)


@router.get("/{customer_id}/guest-360", response_model=Guest360Read)
def get_guest_360(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> Guest360Read:
    return service.get_guest_360(db, current_user.tenant_id, customer_id)
