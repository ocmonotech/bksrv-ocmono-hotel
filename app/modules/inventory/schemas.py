from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.inventory.models import (
    ApprovalStatus,
    MaterialUnit,
    PaymentStatus,
    StockReferenceType,
    StockTransactionType,
    StockTransferStatus,
)


class RawMaterialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(default="General", max_length=128)
    unit: MaterialUnit = MaterialUnit.KG
    reorder_level: float = Field(default=0, ge=0)
    brand_id: int | None = None


class RawMaterialRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    name: str
    category: str
    unit: MaterialUnit
    reorder_level: float
    average_unit_cost: float = 0
    last_purchase_rate: float | None = None
    is_active: bool


class OutletInventoryItem(BaseModel):
    raw_material_id: int
    name: str
    category: str
    unit: MaterialUnit
    reorder_level: float
    quantity_on_hand: float
    average_unit_cost: float = 0
    is_low_stock: bool = False


class LowStockItem(BaseModel):
    outlet_id: int
    raw_material_id: int
    name: str
    category: str
    unit: MaterialUnit
    reorder_level: float
    quantity_on_hand: float
    shortfall: float


class VendorCreate(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=255)
    mobile: str | None = None
    email: str | None = None
    gst_number: str | None = None
    address: str | None = None
    brand_id: int | None = None


class VendorRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    vendor_name: str
    mobile: str | None
    email: str | None
    gst_number: str | None
    address: str | None
    is_active: bool


class PurchaseItemCreate(BaseModel):
    raw_material_id: int
    quantity: float = Field(gt=0)
    unit: MaterialUnit
    rate: float = Field(ge=0)
    gst_percent: float = Field(default=0, ge=0)
    total: float = Field(ge=0)


class PurchaseCreate(BaseModel):
    outlet_id: int
    vendor_id: int
    invoice_number: str = Field(min_length=1, max_length=64)
    purchase_date: date
    payment_status: PaymentStatus = PaymentStatus.PENDING
    brand_id: int | None = None
    items: list[PurchaseItemCreate] = Field(min_length=1)


class PurchaseItemRead(ORMSchema, TimestampSchema):
    id: int
    purchase_id: int
    raw_material_id: int
    quantity: float
    unit: MaterialUnit
    rate: float
    gst_percent: float
    total: float


class PurchaseRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    vendor_id: int
    invoice_number: str
    purchase_date: date
    total_amount: float
    payment_status: PaymentStatus
    approval_status: ApprovalStatus
    created_by: int
    items: list[PurchaseItemRead] = []


class StockLedgerRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    raw_material_id: int
    transaction_type: StockTransactionType
    quantity_in: float
    quantity_out: float
    reference_type: StockReferenceType | None
    reference_id: int | None
    remarks: str | None
    created_by: int


class StockTransferItemCreate(BaseModel):
    raw_material_id: int
    quantity: float = Field(gt=0)
    unit: MaterialUnit


class StockTransferCreate(BaseModel):
    from_outlet_id: int
    to_outlet_id: int
    brand_id: int | None = None
    items: list[StockTransferItemCreate] = Field(min_length=1)
    remarks: str | None = None


class StockTransferItemRead(ORMSchema, TimestampSchema):
    id: int
    stock_transfer_id: int
    raw_material_id: int
    quantity: float
    unit: MaterialUnit


class StockTransferRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    from_outlet_id: int
    to_outlet_id: int
    status: StockTransferStatus
    requested_by: int
    approved_by: int | None
    dispatched_at: datetime | None
    received_at: datetime | None
    items: list[StockTransferItemRead] = []


class StockTransferStatusUpdate(BaseModel):
    status: StockTransferStatus


class StockAdjustmentCreate(BaseModel):
    outlet_id: int
    raw_material_id: int
    quantity: float
    remarks: str | None = None
    brand_id: int | None = None


class StockAdjustmentRead(BaseModel):
    ledger_id: int
    outlet_id: int
    raw_material_id: int
    quantity: float
    remarks: str | None = None
    quantity_on_hand: float


class WastageCreate(BaseModel):
    outlet_id: int
    raw_material_id: int
    quantity: float = Field(gt=0)
    reason: str | None = None
    day_part: str | None = Field(default=None, max_length=16)
    brand_id: int | None = None


class WastageRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    raw_material_id: int
    quantity: float
    reason: str | None
    day_part: str | None = None
    created_by: int
    material_name: str | None = None
    unit: MaterialUnit | None = None
    line_cost: float | None = None


class PrepBoardItem(BaseModel):
    menu_item_id: int
    item_name: str
    preparation_area: str
    avg_qty_sold: float
    forecast_qty: float
    recipe_cost: float = 0


class PrepBoardIngredient(BaseModel):
    raw_material_id: int
    name: str
    unit: MaterialUnit
    qty_needed: float
    qty_on_hand: float
    shortfall: float
    average_unit_cost: float
    estimated_cost: float


class PrepBoardTotals(BaseModel):
    ingredient_lines: int = 0
    shortfall_lines: int = 0
    estimated_prep_cost: float = 0
    wastage_cost_today: float = 0


class PrepBoardRead(BaseModel):
    outlet_id: int
    business_date: date
    day_part: str
    lookback_days: int
    expected_inclusion_covers: int = 0
    items: list[PrepBoardItem] = Field(default_factory=list)
    ingredients: list[PrepBoardIngredient] = Field(default_factory=list)
    wastage: list[WastageRead] = Field(default_factory=list)
    totals: PrepBoardTotals = Field(default_factory=PrepBoardTotals)