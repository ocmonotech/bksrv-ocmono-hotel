from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.menu.models import FoodType, PreparationArea


class MenuCategoryCreate(BaseModel):
    brand_id: int | None = None
    name: str = Field(max_length=128)
    description: str | None = None
    sort_order: int = 0


class MenuCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class MenuCategoryRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    name: str
    description: str | None
    sort_order: int
    is_active: bool


class MenuItemCreate(BaseModel):
    brand_id: int | None = None
    category_id: int
    item_name: str = Field(max_length=255)
    description: str | None = None
    food_type: FoodType = FoodType.VEG
    base_price: float = Field(ge=0)
    gst_percent: float = Field(default=5, ge=0, le=100)
    preparation_area: PreparationArea = PreparationArea.KITCHEN
    image_url: str | None = None


class MenuItemUpdate(BaseModel):
    category_id: int | None = None
    item_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    food_type: FoodType | None = None
    base_price: float | None = Field(default=None, ge=0)
    gst_percent: float | None = Field(default=None, ge=0, le=100)
    preparation_area: PreparationArea | None = None
    image_url: str | None = None
    is_active: bool | None = None


class MenuItemRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    category_id: int
    item_name: str
    description: str | None
    food_type: FoodType
    base_price: float
    gst_percent: float
    recipe_cost: float = 0
    food_cost_percent: float = 0
    preparation_area: PreparationArea
    image_url: str | None
    is_active: bool


class MenuItemOutletPriceSet(BaseModel):
    outlet_id: int
    outlet_price: float = Field(ge=0)


class MenuItemOutletAvailabilitySet(BaseModel):
    outlet_id: int
    is_available: bool


class MenuItemOutletRead(BaseModel):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    menu_item_id: int
    outlet_price: float
    is_available: bool

    model_config = {"from_attributes": True}


class ItemAddonCreate(BaseModel):
    brand_id: int | None = None
    addon_name: str = Field(max_length=255)
    price: float = Field(ge=0)


class ItemAddonRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    menu_item_id: int
    addon_name: str
    price: float
    is_active: bool


class MenuItemIngredientCreate(BaseModel):
    brand_id: int | None = None
    raw_material_id: int
    quantity_per_serving: float = Field(default=1, gt=0)


class MenuItemIngredientUpdate(BaseModel):
    raw_material_id: int | None = None
    quantity_per_serving: float | None = Field(default=None, gt=0)
    is_active: bool | None = None


class MenuItemIngredientRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    menu_item_id: int
    raw_material_id: int
    quantity_per_serving: float
    is_active: bool
    raw_material_name: str | None = None
    unit: str | None = None
    unit_cost: float = 0
    line_cost: float = 0


class MenuRecipeCostRead(BaseModel):
    menu_item_id: int
    item_name: str
    base_price: float
    recipe_cost: float
    food_cost_percent: float
    gross_margin: float
    ingredient_count: int


class ComboItemInput(BaseModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1)


class ComboCreate(BaseModel):
    brand_id: int | None = None
    combo_name: str = Field(max_length=255)
    combo_price: float = Field(ge=0)
    items: list[ComboItemInput] = Field(min_length=1)


class ComboItemRead(BaseModel):
    id: int
    menu_item_id: int
    quantity: int
    item_name: str | None = None

    model_config = {"from_attributes": True}


class ComboRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    combo_name: str
    combo_price: float
    is_active: bool
    items: list[ComboItemRead] = Field(default_factory=list)


class ActiveMenuAddon(BaseModel):
    id: int
    addon_name: str
    price: float


class ActiveMenuItem(BaseModel):
    id: int
    item_name: str
    description: str | None
    food_type: FoodType
    base_price: float
    outlet_price: float
    gst_percent: float
    preparation_area: PreparationArea
    image_url: str | None
    is_available: bool
    addons: list[ActiveMenuAddon] = Field(default_factory=list)


class ActiveMenuCategory(BaseModel):
    id: int
    name: str
    description: str | None
    sort_order: int
    items: list[ActiveMenuItem] = Field(default_factory=list)


class ActiveMenuCombo(BaseModel):
    id: int
    combo_name: str
    combo_price: float
    items: list[ComboItemRead] = Field(default_factory=list)


class ActiveOutletMenuRead(BaseModel):
    outlet_id: int
    brand_id: int
    categories: list[ActiveMenuCategory] = Field(default_factory=list)
    combos: list[ActiveMenuCombo] = Field(default_factory=list)


class PublicMenuTableOption(BaseModel):
    id: int
    table_number: str
    capacity: int = 2
    status: str = "available"


class PublicClickCollectInfo(BaseModel):
    enabled: bool = True
    open: str = "08:00"
    close: str = "22:00"
    slot_minutes: int = 15
    prep_sla_minutes: int = 20
    min_lead_minutes: int = 20
    horizon_hours: int = 4
    slots: list[str] = Field(default_factory=list)


class PublicOutletMenuRead(BaseModel):
    outlet_id: int
    outlet_name: str
    location: str
    address: str | None = None
    brand_id: int
    brand_name: str | None = None
    logo_url: str | None = None
    support_number: str | None = None
    categories: list[ActiveMenuCategory] = Field(default_factory=list)
    combos: list[ActiveMenuCombo] = Field(default_factory=list)
    tables: list[PublicMenuTableOption] = Field(default_factory=list)
    click_collect: PublicClickCollectInfo | None = None


class PublicMenuOrderLine(BaseModel):
    menu_item_id: int | None = None
    combo_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=50)
    note: str | None = Field(default=None, max_length=255)
    addon_ids: list[int] = Field(default_factory=list)


class PublicMenuOrderCreate(BaseModel):
    outlet_id: int
    table_id: int | None = None
    guest_name: str | None = Field(default=None, max_length=120)
    guest_mobile: str | None = Field(default=None, max_length=20)
    room_number: str | None = Field(default=None, max_length=32)
    order_type: str = Field(default="dine_in", max_length=32)
    pickup_at: datetime | None = None
    items: list[PublicMenuOrderLine] = Field(min_length=1)
    send_to_kot: bool = True


class PublicMenuOrderResponse(BaseModel):
    order_id: int
    order_number: str
    order_status: str
    grand_total: float
    table_number: str | None = None
    room_number: str | None = None
    queue_token: str | None = None
    pickup_at: datetime | None = None
    ready_at: datetime | None = None
    message: str
    kot_sent: bool = False
    notify_stub: str | None = None
    upi_vpa: str | None = None
    upi_payee_name: str | None = None
    upi_deeplink: str | None = None


class PublicQueueBoardItem(BaseModel):
    order_id: int
    order_number: str
    queue_token: str
    order_status: str
    guest_name: str | None = None
    pickup_at: datetime | None = None
    ready_at: datetime | None = None


class PublicQueueBoardResponse(BaseModel):
    outlet_id: int
    preparing: list[PublicQueueBoardItem] = Field(default_factory=list)
    ready: list[PublicQueueBoardItem] = Field(default_factory=list)
    upcoming_pickups: list[PublicQueueBoardItem] = Field(default_factory=list)


class PublicMenuPayRequest(BaseModel):
    order_id: int
    order_number: str = Field(max_length=32)
    payment_mode: str = Field(default="upi", max_length=32)
    reference_number: str | None = Field(default=None, max_length=64)


class PublicMenuPayResponse(BaseModel):
    order_id: int
    order_number: str
    bill_id: int
    bill_number: str
    payment_status: str
    grand_total: float
    message: str
    paid: bool = True


class PublicRoomVerifyRequest(BaseModel):
    outlet_id: int
    room_number: str = Field(min_length=1, max_length=32)
    guest_mobile: str = Field(min_length=4, max_length=20)


class PublicRoomVerifyResponse(BaseModel):
    reservation_id: int
    guest_name: str
    room_number: str
    confirmation_number: str


class PublicRoomChargeRequest(BaseModel):
    order_id: int
    order_number: str = Field(max_length=32)
    room_number: str = Field(min_length=1, max_length=32)
    guest_mobile: str = Field(min_length=4, max_length=20)


class PublicRoomChargeResponse(BaseModel):
    order_id: int
    order_number: str
    bill_id: int
    bill_number: str
    reservation_id: int
    room_number: str
    guest_name: str
    amount: float
    message: str
    paid: bool = True
