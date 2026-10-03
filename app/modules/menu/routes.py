from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.common.response import MessageResponse
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.menu import service
from app.modules.menu.schemas import (
    ActiveOutletMenuRead,
    ComboCreate,
    ComboRead,
    ItemAddonCreate,
    ItemAddonRead,
    MenuCategoryCreate,
    MenuCategoryRead,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemIngredientCreate,
    MenuItemIngredientRead,
    MenuItemIngredientUpdate,
    MenuRecipeCostRead,
    MenuItemOutletAvailabilitySet,
    MenuItemOutletPriceSet,
    MenuItemOutletRead,
    MenuItemRead,
    MenuItemUpdate,
    PublicMenuOrderCreate,
    PublicMenuOrderResponse,
    PublicMenuPayRequest,
    PublicMenuPayResponse,
    PublicOutletMenuRead,
    PublicQueueBoardResponse,
    PublicRoomChargeRequest,
    PublicRoomChargeResponse,
    PublicRoomVerifyRequest,
    PublicRoomVerifyResponse,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/categories", response_model=list[MenuCategoryRead])
def list_categories(
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> list[MenuCategoryRead]:
    return service.list_categories(db, current_user.tenant_id, brand_id=brand_id)


@router.post("/categories", response_model=MenuCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    body: MenuCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuCategoryRead:
    return service.create_category(db, current_user.tenant_id, body, current_user.brand_id)


@router.get("/categories/{category_id}", response_model=MenuCategoryRead)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> MenuCategoryRead:
    return service.get_category(db, current_user.tenant_id, category_id)


@router.patch("/categories/{category_id}", response_model=MenuCategoryRead)
def update_category(
    category_id: int,
    body: MenuCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuCategoryRead:
    return service.update_category(db, current_user.tenant_id, category_id, body)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MessageResponse:
    service.delete_category(db, current_user.tenant_id, category_id)
    return MessageResponse(message="Category deactivated")


@router.get("/items", response_model=PaginatedSuccessResponse[MenuItemRead])
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand_id: int | None = Query(None),
    category_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> PaginatedSuccessResponse[MenuItemRead]:
    items, total = service.list_items(
        db,
        current_user.tenant_id,
        page,
        page_size,
        brand_id=brand_id,
        category_id=category_id,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/items", response_model=MenuItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    body: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuItemRead:
    return service.create_item(db, current_user.tenant_id, body, current_user.brand_id)


@router.get("/items/{item_id}", response_model=MenuItemRead)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> MenuItemRead:
    return service.get_item(db, current_user.tenant_id, item_id)


@router.patch("/items/{item_id}", response_model=MenuItemRead)
def update_item(
    item_id: int,
    body: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuItemRead:
    return service.update_item(db, current_user.tenant_id, item_id, body)


@router.delete("/items/{item_id}", response_model=MessageResponse)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MessageResponse:
    service.delete_item(db, current_user.tenant_id, item_id)
    return MessageResponse(message="Menu item deactivated")


@router.put("/items/{item_id}/outlet-price", response_model=MenuItemOutletRead)
def set_outlet_price(
    item_id: int,
    body: MenuItemOutletPriceSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuItemOutletRead:
    return service.set_outlet_price(db, current_user.tenant_id, item_id, body)


@router.put("/items/{item_id}/outlet-availability", response_model=MenuItemOutletRead)
def set_outlet_availability(
    item_id: int,
    body: MenuItemOutletAvailabilitySet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuItemOutletRead:
    return service.set_outlet_availability(db, current_user.tenant_id, item_id, body)


@router.post("/items/{item_id}/addons", response_model=ItemAddonRead, status_code=status.HTTP_201_CREATED)
def create_addon(
    item_id: int,
    body: ItemAddonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> ItemAddonRead:
    return service.create_addon(db, current_user.tenant_id, item_id, body, current_user.brand_id)


@router.get("/items/{item_id}/addons", response_model=list[ItemAddonRead])
def list_item_addons(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> list[ItemAddonRead]:
    return service.list_addons_for_item(db, current_user.tenant_id, item_id)


@router.get("/costing/recipes", response_model=list[MenuRecipeCostRead])
def list_recipe_costs(
    high_food_cost_only: bool = Query(default=False),
    threshold: float = Query(default=35.0, ge=0, le=100),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> list[MenuRecipeCostRead]:
    return service.list_recipe_costs(
        db,
        current_user.tenant_id,
        brand_id=brand_id or current_user.brand_id,
        high_food_cost_only=high_food_cost_only,
        threshold=threshold,
    )


@router.post("/items/{item_id}/costing/refresh", response_model=MenuRecipeCostRead)
def refresh_item_recipe_cost(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuRecipeCostRead:
    return service.refresh_menu_item_cost(db, current_user.tenant_id, item_id)


@router.get("/items/{item_id}/ingredients", response_model=list[MenuItemIngredientRead])
def list_item_ingredients(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> list[MenuItemIngredientRead]:
    return service.list_ingredients_by_item(db, current_user.tenant_id, item_id)


@router.post(
    "/items/{item_id}/ingredients",
    response_model=MenuItemIngredientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_item_ingredient(
    item_id: int,
    body: MenuItemIngredientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuItemIngredientRead:
    return service.create_ingredient(
        db, current_user.tenant_id, item_id, body, current_user.brand_id
    )


@router.patch("/items/{item_id}/ingredients/{ingredient_id}", response_model=MenuItemIngredientRead)
def update_item_ingredient(
    item_id: int,
    ingredient_id: int,
    body: MenuItemIngredientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MenuItemIngredientRead:
    return service.update_ingredient(
        db, current_user.tenant_id, item_id, ingredient_id, body
    )


@router.delete("/items/{item_id}/ingredients/{ingredient_id}", response_model=MessageResponse)
def delete_item_ingredient(
    item_id: int,
    ingredient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> MessageResponse:
    service.delete_ingredient(db, current_user.tenant_id, item_id, ingredient_id)
    return MessageResponse(message="Menu item ingredient deactivated")


@router.get("/combos", response_model=list[ComboRead])
def list_combos(
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> list[ComboRead]:
    return service.list_combos(db, current_user.tenant_id, brand_id=brand_id)


@router.post("/combos", response_model=ComboRead, status_code=status.HTTP_201_CREATED)
def create_combo(
    body: ComboCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> ComboRead:
    return service.create_combo(db, current_user.tenant_id, body, current_user.brand_id)


@router.get("/combos/{combo_id}", response_model=ComboRead)
def get_combo(
    combo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> ComboRead:
    return service.get_combo(db, current_user.tenant_id, combo_id)


@router.get("/outlets/{outlet_id}/active-menu", response_model=ActiveOutletMenuRead)
def get_active_menu_for_outlet(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> ActiveOutletMenuRead:
    return service.get_active_menu_for_outlet(db, current_user.tenant_id, outlet_id)


@router.get("/public/outlets/{outlet_id}", response_model=PublicOutletMenuRead)
def get_public_outlet_menu(
    outlet_id: int,
    db: Session = Depends(get_db),
) -> PublicOutletMenuRead:
    return service.get_public_outlet_menu(db, outlet_id)


@router.get("/public/queue", response_model=PublicQueueBoardResponse)
def get_public_queue_board(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
) -> PublicQueueBoardResponse:
    from app.modules.pos import service as pos_service

    return pos_service.get_public_queue_board(db, outlet_id)


@router.post("/public/orders", response_model=PublicMenuOrderResponse, status_code=status.HTTP_201_CREATED)
def submit_public_menu_order(
    body: PublicMenuOrderCreate,
    db: Session = Depends(get_db),
) -> PublicMenuOrderResponse:
    from app.modules.pos import service as pos_service

    return pos_service.submit_guest_menu_order(db, body)


@router.post("/public/orders/pay", response_model=PublicMenuPayResponse)
def pay_public_menu_order(
    body: PublicMenuPayRequest,
    db: Session = Depends(get_db),
) -> PublicMenuPayResponse:
    from app.modules.pos import service as pos_service

    return pos_service.pay_guest_menu_order(db, body)


@router.post("/public/room-verify", response_model=PublicRoomVerifyResponse)
def verify_public_room_guest(
    body: PublicRoomVerifyRequest,
    db: Session = Depends(get_db),
) -> PublicRoomVerifyResponse:
    from app.modules.pms import service as pms_service

    return pms_service.verify_public_room_guest(db, body)


@router.post("/public/orders/charge-to-room", response_model=PublicRoomChargeResponse)
def charge_public_menu_order_to_room(
    body: PublicRoomChargeRequest,
    db: Session = Depends(get_db),
) -> PublicRoomChargeResponse:
    from app.modules.pos import service as pos_service

    return pos_service.charge_guest_menu_order_to_room(db, body)
