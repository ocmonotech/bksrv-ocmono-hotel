from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.pos import service
from app.modules.pos.schemas import (
    BillRead,
    CancelBillPlaceholderResponse,
    CancelBillRequest,
    CancelOrderRequest,
    DiscountApprovalRequest,
    DiscountApprovalResponse,
    OrderCreate,
    OrderItemCreate,
    OrderItemUpdate,
    OrderRead,
    PaymentCreate,
    PaymentRead,
    PickupOrderRead,
    SendKotResponse,
)
from app.modules.users.models import User

router = APIRouter()


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    body: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> OrderRead:
    return service.create_order(db, current_user.tenant_id, current_user.id, body, current_user.brand_id)


@router.get("/orders/running", response_model=list[OrderRead])
def get_running_orders(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[OrderRead]:
    return service.get_running_orders(db, current_user.tenant_id, outlet_id)


@router.get("/orders/pickups", response_model=list[PickupOrderRead])
def get_pickup_orders(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[PickupOrderRead]:
    return service.list_pickup_orders(db, current_user.tenant_id, outlet_id)


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> OrderRead:
    return service.get_order(db, current_user.tenant_id, order_id)


@router.post("/orders/{order_id}/items", response_model=OrderRead)
def add_item(
    order_id: int,
    body: OrderItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> OrderRead:
    return service.add_item(db, current_user.tenant_id, order_id, body)


@router.patch("/orders/{order_id}/items/{item_id}", response_model=OrderRead)
def update_item_quantity(
    order_id: int,
    item_id: int,
    body: OrderItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> OrderRead:
    return service.update_item_quantity(
        db, current_user.tenant_id, order_id, item_id, body.quantity
    )


@router.delete("/orders/{order_id}/items/{item_id}", response_model=OrderRead)
def remove_item(
    order_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> OrderRead:
    return service.remove_item(db, current_user.tenant_id, order_id, item_id)


@router.post("/orders/{order_id}/send-kot", response_model=SendKotResponse)
def send_order_to_kot(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> SendKotResponse:
    return service.send_order_to_kot(db, current_user.tenant_id, order_id, current_user.id)


@router.post("/orders/{order_id}/bill", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def generate_bill(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> BillRead:
    return service.generate_bill(db, current_user.tenant_id, current_user.id, order_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_order(
    order_id: int,
    body: CancelOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> OrderRead:
    return service.cancel_order(db, current_user.tenant_id, current_user.id, order_id, body)


@router.get("/bills", response_model=list[BillRead])
def get_bills_by_outlet(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[BillRead]:
    return service.get_bills_by_outlet(db, current_user.tenant_id, outlet_id)


@router.post("/bills/{bill_id}/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def add_payment(
    bill_id: int,
    body: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> PaymentRead:
    return service.add_payment(db, current_user.tenant_id, bill_id, body, user_id=current_user.id)


@router.post("/bills/{bill_id}/cancel", response_model=CancelBillPlaceholderResponse)
def cancel_bill(
    bill_id: int,
    body: CancelBillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> CancelBillPlaceholderResponse:
    return service.cancel_bill(
        db,
        current_user.tenant_id,
        current_user,
        bill_id,
        body.reason_text,
    )


@router.post("/orders/{order_id}/approve-discount", response_model=DiscountApprovalResponse)
def approve_order_discount(
    order_id: int,
    body: DiscountApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> DiscountApprovalResponse:
    return service.approve_order_discount(
        db,
        current_user.tenant_id,
        current_user.id,
        order_id,
        body.notes,
    )
