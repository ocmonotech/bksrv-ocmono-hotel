from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    today_sales: float = 0
    total_orders: int = 0
    average_bill_value: float = 0
    active_outlets: int = 0
    total_discounts: float = 0
    cancelled_bills: int = 0
    currency: str = "INR"


class OutletComparisonRow(BaseModel):
    outlet_id: int
    outlet_name: str
    total_sales: float = 0
    total_orders: int = 0
    average_bill_value: float = 0
    total_discounts: float = 0


class OutletComparisonReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    outlet_id: int | None = None
    outlets: list[OutletComparisonRow] = Field(default_factory=list)
    totals: OutletComparisonRow | None = None


class ItemPerformanceRow(BaseModel):
    menu_item_id: int | None = None
    item_name: str
    quantity_sold: int = 0
    gross_sales: float = 0
    discount_amount: float = 0
    net_sales: float = 0


class ItemPerformanceReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    outlet_id: int | None = None
    items: list[ItemPerformanceRow] = Field(default_factory=list)


class FoodCostRow(BaseModel):
    menu_item_id: int | None = None
    item_name: str
    quantity_sold: int = 0
    net_sales: float = 0
    recipe_cost_per_unit: float = 0
    total_food_cost: float = 0  # theoretical COGS for the item
    gross_margin: float = 0
    actual_food_cost_percent: float = 0  # theoretical food cost / revenue (compat)
    menu_food_cost_percent: float = 0
    theoretical_food_cost_percent: float = 0


class FoodCostOutletSummary(BaseModel):
    outlet_id: int
    outlet_name: str
    total_revenue: float = 0
    theoretical_cogs: float = 0
    wastage_cost: float = 0
    actual_cogs: float = 0
    variance: float = 0
    variance_percent: float = 0
    overall_food_cost_percent: float = 0


class FoodCostReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    outlet_id: int | None = None
    items: list[FoodCostRow] = Field(default_factory=list)
    outlets: list[FoodCostOutletSummary] = Field(default_factory=list)
    total_revenue: float = 0
    total_food_cost: float = 0  # alias of theoretical_cogs
    theoretical_cogs: float = 0
    wastage_cost: float = 0
    sale_ledger_cogs: float = 0
    actual_cogs: float = 0
    variance: float = 0
    variance_percent: float = 0
    total_margin: float = 0  # revenue - actual_cogs
    theoretical_margin: float = 0  # revenue - theoretical_cogs
    overall_food_cost_percent: float = 0  # actual_cogs / revenue
    theoretical_food_cost_percent: float = 0


class PaymentSummaryRow(BaseModel):
    payment_mode: str
    transaction_count: int = 0
    total_amount: float = 0


class PaymentSummaryReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    outlet_id: int | None = None
    payments: list[PaymentSummaryRow] = Field(default_factory=list)
    total_amount: float = 0


class DiscountReportRow(BaseModel):
    outlet_id: int | None = None
    bill_number: str | None = None
    order_number: str | None = None
    discount_amount: float = 0
    bill_total: float = 0
    created_at: datetime | None = None


class DiscountReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    outlet_id: int | None = None
    total_discounts: float = 0
    discount_count: int = 0
    rows: list[DiscountReportRow] = Field(default_factory=list)


class CustomerRepeatRow(BaseModel):
    customer_id: int
    full_name: str
    mobile: str
    total_visits: int = 0
    total_spend: float = 0
    last_visit_at: datetime | None = None
    is_repeat_customer: bool = False


class CustomerRepeatReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    outlet_id: int | None = None
    total_customers: int = 0
    repeat_customers: int = 0
    repeat_rate_percent: float = 0
    customers: list[CustomerRepeatRow] = Field(default_factory=list)


class CampaignPerformanceRow(BaseModel):
    campaign_id: int
    campaign_name: str
    channel: str
    status: str
    sent_count: int = 0
    delivered_count: int = 0
    read_count: int = 0
    replied_count: int = 0
    converted_count: int = 0
    failed_count: int = 0
    actual_cost: float = 0
    delivery_rate_percent: float = 0
    conversion_rate_percent: float = 0


class CampaignPerformanceReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    campaigns: list[CampaignPerformanceRow] = Field(default_factory=list)
    totals: CampaignPerformanceRow | None = None


class AiUsageSummaryReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    total_requests: int = 0
    total_tokens: int = 0
    total_estimated_cost: float = 0
    by_module: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    by_provider: dict[str, dict[str, float | int]] = Field(default_factory=dict)


class CommunicationSummaryReport(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    outlet_id: int | None = None
    total_conversations: int = 0
    open_conversations: int = 0
    total_messages: int = 0
    inbound_messages: int = 0
    outbound_messages: int = 0
    by_channel: dict[str, dict[str, int]] = Field(default_factory=dict)


class EventsSummaryRow(BaseModel):
    event_id: int
    title: str
    event_type: str
    event_date: date
    status: str
    outlet_id: int
    expected_guests: int
    estimated_amount: float
    advance_paid: float


class EventsSummaryReport(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    outlet_id: int | None = None
    total_events: int = 0
    confirmed_events: int = 0
    completed_events: int = 0
    total_estimated_revenue: float = 0
    total_advance_collected: float = 0
    events: list[EventsSummaryRow] = Field(default_factory=list)
