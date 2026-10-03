from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.inventory import service
from app.modules.inventory.schemas import (
    LowStockItem,
    OutletInventoryItem,
    PrepBoardRead,
    PurchaseCreate,
    PurchaseRead,
    RawMaterialCreate,
    RawMaterialRead,
    StockLedgerRead,
    StockAdjustmentCreate,
    StockAdjustmentRead,
    StockTransferCreate,
    StockTransferRead,
    StockTransferStatusUpdate,
    VendorCreate,
    VendorRead,
    WastageCreate,
    WastageRead,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/raw-materials", response_model=PaginatedSuccessResponse[RawMaterialRead])
def list_raw_materials(
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=500),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_READ)),
) -> PaginatedSuccessResponse[RawMaterialRead]:
    items, total = service.list_raw_materials(
        db,
        current_user.tenant_id,
        brand_id=brand_id or current_user.brand_id,
        page=page,
        page_size=page_size,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/raw-materials", response_model=RawMaterialRead, status_code=status.HTTP_201_CREATED)
def create_raw_material(
    body: RawMaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> RawMaterialRead:
    return service.create_raw_material(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/outlets/{outlet_id}/inventory", response_model=PaginatedSuccessResponse[OutletInventoryItem])
def list_inventory_by_outlet(
    outlet_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_READ)),
) -> PaginatedSuccessResponse[OutletInventoryItem]:
    items, total = service.list_inventory_by_outlet(
        db, current_user.tenant_id, outlet_id, page, page_size
    )
    return success_paginated(items, total, page, page_size)


@router.post("/vendors", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(
    body: VendorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> VendorRead:
    return service.create_vendor(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/purchases", response_model=PurchaseRead, status_code=status.HTTP_201_CREATED)
def create_purchase(
    body: PurchaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> PurchaseRead:
    return service.create_purchase(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/purchases/{purchase_id}/approve", response_model=PurchaseRead)
def approve_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> PurchaseRead:
    return service.approve_purchase(db, current_user.tenant_id, current_user.id, purchase_id)


@router.get("/stock-ledger", response_model=PaginatedSuccessResponse[StockLedgerRead])
def list_stock_ledger(
    outlet_id: int | None = Query(None),
    raw_material_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_READ)),
) -> PaginatedSuccessResponse[StockLedgerRead]:
    items, total = service.list_stock_ledger(
        db,
        current_user.tenant_id,
        outlet_id,
        raw_material_id,
        page,
        page_size,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/stock-transfers", response_model=StockTransferRead, status_code=status.HTTP_201_CREATED)
def create_stock_transfer(
    body: StockTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> StockTransferRead:
    return service.create_stock_transfer(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/stock-transfers/{transfer_id}/status", response_model=StockTransferRead)
def update_transfer_status(
    transfer_id: int,
    body: StockTransferStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> StockTransferRead:
    return service.update_transfer_status(
        db,
        current_user.tenant_id,
        current_user.id,
        transfer_id,
        body,
    )


@router.post("/stock-adjustments", response_model=StockAdjustmentRead, status_code=status.HTTP_201_CREATED)
def adjust_stock(
    body: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> StockAdjustmentRead:
    return service.adjust_stock(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.post("/wastage", response_model=WastageRead, status_code=status.HTTP_201_CREATED)
def add_wastage(
    body: WastageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_WRITE)),
) -> WastageRead:
    return service.add_wastage(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/wastage", response_model=list[WastageRead])
def get_wastage_log(
    outlet_id: int = Query(...),
    business_date: date | None = Query(None),
    day_part: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_READ)),
) -> list[WastageRead]:
    return service.list_wastage(
        db,
        current_user.tenant_id,
        outlet_id,
        business_date=business_date,
        day_part=day_part,
    )


@router.get("/prep-board", response_model=PrepBoardRead)
def get_prep_board(
    outlet_id: int = Query(...),
    business_date: date | None = Query(None),
    day_part: str = Query("all_day"),
    lookback_days: int = Query(14, ge=3, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_READ)),
) -> PrepBoardRead:
    return service.get_prep_board(
        db,
        current_user.tenant_id,
        outlet_id,
        business_date=business_date,
        day_part=day_part,
        lookback_days=lookback_days,
    )


@router.get("/reports/low-stock", response_model=list[LowStockItem])
def low_stock_report(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.INVENTORY_READ)),
) -> list[LowStockItem]:
    return service.low_stock_report(db, current_user.tenant_id, outlet_id)
