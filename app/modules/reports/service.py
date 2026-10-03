from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.common.base_model import RecordStatus
from app.modules.ai.models import AiUsageLog
from app.modules.campaigns.models import Campaign
from app.modules.communications.models import Conversation, ConversationStatus, Message, MessageDirection
from app.modules.customers.models import Customer, CustomerVisit
from app.modules.events.models import EventStatus, RestaurantEvent
from app.modules.menu.models import MenuItem
from app.modules.inventory.models import RawMaterial, StockLedger, StockTransactionType
from app.modules.outlets.models import Outlet
from app.modules.pos.models import Bill, BillPaymentStatus, Order, OrderItem, OrderStatus, Payment, PaymentRecordStatus
from app.modules.reports.schemas import (
    AiUsageSummaryReport,
    CampaignPerformanceReport,
    CampaignPerformanceRow,
    CommunicationSummaryReport,
    CustomerRepeatReport,
    CustomerRepeatRow,
    DashboardSummary,
    DiscountReport,
    DiscountReportRow,
    EventsSummaryReport,
    EventsSummaryRow,
    FoodCostReport,
    FoodCostRow,
    FoodCostOutletSummary,
    ItemPerformanceReport,
    ItemPerformanceRow,
    OutletComparisonReport,
    OutletComparisonRow,
    PaymentSummaryReport,
    PaymentSummaryRow,
)


def dashboard_summary(db: Session, tenant_id: int, outlet_id: int | None = None) -> DashboardSummary:
    day_start, day_end = _today_range()

    bill_query = db.query(Bill).filter(Bill.tenant_id == tenant_id)
    order_query = db.query(Order).filter(Order.tenant_id == tenant_id)
    outlet_query = db.query(Outlet).filter(
        Outlet.tenant_id == tenant_id,
        Outlet.is_active.is_(True),
        Outlet.status == RecordStatus.ACTIVE,
    )

    if outlet_id is not None:
        bill_query = bill_query.filter(Bill.outlet_id == outlet_id)
        order_query = order_query.filter(Order.outlet_id == outlet_id)
        outlet_query = outlet_query.filter(Outlet.id == outlet_id)

    bill_query = _apply_date_filter(bill_query, Bill, day_start, day_end)
    order_query = _apply_date_filter(order_query, Order, day_start, day_end)

    paid_bills = bill_query.filter(Bill.payment_status == BillPaymentStatus.PAID).all()
    today_sales = sum(float(bill.grand_total or 0) for bill in paid_bills)
    total_discounts = sum(float(bill.discount_amount or 0) for bill in paid_bills)
    cancelled_bills = (
        bill_query.filter(Bill.payment_status == BillPaymentStatus.CANCELLED).count()
    )

    total_orders = order_query.filter(Order.order_status != OrderStatus.CANCELLED).count()
    active_outlets = outlet_query.count()
    average_bill_value = round(today_sales / len(paid_bills), 2) if paid_bills else 0

    return DashboardSummary(
        today_sales=round(today_sales, 2),
        total_orders=total_orders,
        average_bill_value=average_bill_value,
        active_outlets=active_outlets,
        total_discounts=round(total_discounts, 2),
        cancelled_bills=cancelled_bills,
    )


def outlet_comparison(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outlet_id: int | None = None,
) -> OutletComparisonReport:
    outlets = db.query(Outlet).filter(Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True))
    if outlet_id is not None:
        outlets = outlets.filter(Outlet.id == outlet_id)
    outlets = outlets.order_by(Outlet.outlet_name).all()

    rows: list[OutletComparisonRow] = []
    total_sales = 0.0
    total_orders = 0
    total_discounts = 0.0
    paid_bill_count = 0

    for outlet in outlets:
        bill_query = db.query(Bill).filter(
            Bill.tenant_id == tenant_id,
            Bill.outlet_id == outlet.id,
        )
        order_query = db.query(Order).filter(
            Order.tenant_id == tenant_id,
            Order.outlet_id == outlet.id,
            Order.order_status != OrderStatus.CANCELLED,
        )
        bill_query = _apply_date_filter(bill_query, Bill, date_from, date_to)
        order_query = _apply_date_filter(order_query, Order, date_from, date_to)

        paid_bills = bill_query.filter(Bill.payment_status == BillPaymentStatus.PAID).all()
        sales = sum(float(bill.grand_total or 0) for bill in paid_bills)
        discounts = sum(float(bill.discount_amount or 0) for bill in paid_bills)
        orders = order_query.count()
        avg_bill = round(sales / len(paid_bills), 2) if paid_bills else 0

        rows.append(
            OutletComparisonRow(
                outlet_id=outlet.id,
                outlet_name=outlet.outlet_name,
                total_sales=round(sales, 2),
                total_orders=orders,
                average_bill_value=avg_bill,
                total_discounts=round(discounts, 2),
            )
        )
        total_sales += sales
        total_orders += orders
        total_discounts += discounts
        paid_bill_count += len(paid_bills)

    totals = None
    if rows:
        totals = OutletComparisonRow(
            outlet_id=0,
            outlet_name="All Outlets",
            total_sales=round(total_sales, 2),
            total_orders=total_orders,
            average_bill_value=round(total_sales / paid_bill_count, 2) if paid_bill_count else 0,
            total_discounts=round(total_discounts, 2),
        )

    return OutletComparisonReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        outlets=rows,
        totals=totals,
    )


def item_performance(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outlet_id: int | None = None,
) -> ItemPerformanceReport:
    query = (
        db.query(
            OrderItem.menu_item_id,
            OrderItem.item_name,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity_sold"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.price), 0).label("gross_sales"),
            func.coalesce(func.sum(OrderItem.discount_amount), 0).label("discount_amount"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.tenant_id == tenant_id,
            Order.order_status != OrderStatus.CANCELLED,
        )
    )

    if outlet_id is not None:
        query = query.filter(Order.outlet_id == outlet_id)

    query = _apply_date_filter(query, Order, date_from, date_to)
    query = query.group_by(OrderItem.menu_item_id, OrderItem.item_name).order_by(
        func.sum(OrderItem.quantity * OrderItem.price).desc()
    )

    items: list[ItemPerformanceRow] = []
    for row in query.all():
        gross = float(row.gross_sales or 0)
        discount = float(row.discount_amount or 0)
        items.append(
            ItemPerformanceRow(
                menu_item_id=row.menu_item_id,
                item_name=row.item_name,
                quantity_sold=int(row.quantity_sold or 0),
                gross_sales=round(gross, 2),
                discount_amount=round(discount, 2),
                net_sales=round(gross - discount, 2),
            )
        )

    return ItemPerformanceReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        items=items,
    )


def food_cost_report(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outlet_id: int | None = None,
) -> FoodCostReport:
    performance = item_performance(db, tenant_id, date_from, date_to, outlet_id)
    menu_item_ids = [row.menu_item_id for row in performance.items if row.menu_item_id]
    cost_by_item: dict[int, MenuItem] = {}
    if menu_item_ids:
        cost_by_item = {
            item.id: item
            for item in db.query(MenuItem)
            .filter(MenuItem.tenant_id == tenant_id, MenuItem.id.in_(menu_item_ids))
            .all()
        }

    rows: list[FoodCostRow] = []
    total_revenue = 0.0
    theoretical_cogs = 0.0
    for row in performance.items:
        menu_item = cost_by_item.get(row.menu_item_id) if row.menu_item_id else None
        recipe_cost = float(menu_item.recipe_cost or 0) if menu_item else 0.0
        qty = int(row.quantity_sold or 0)
        line_food_cost = round(recipe_cost * qty, 2)
        net = float(row.net_sales or 0)
        margin = round(net - line_food_cost, 2)
        food_pct = round(line_food_cost / net * 100, 2) if net > 0 else 0.0
        rows.append(
            FoodCostRow(
                menu_item_id=row.menu_item_id,
                item_name=row.item_name,
                quantity_sold=qty,
                net_sales=net,
                recipe_cost_per_unit=recipe_cost,
                total_food_cost=line_food_cost,
                gross_margin=margin,
                actual_food_cost_percent=food_pct,
                menu_food_cost_percent=float(menu_item.food_cost_percent or 0) if menu_item else 0.0,
                theoretical_food_cost_percent=food_pct,
            )
        )
        total_revenue += net
        theoretical_cogs += line_food_cost

    wastage_cost = _sum_ledger_cogs(
        db,
        tenant_id,
        StockTransactionType.WASTAGE,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )
    sale_ledger_cogs = _sum_ledger_cogs(
        db,
        tenant_id,
        StockTransactionType.SALE,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )

    theoretical_cogs = round(theoretical_cogs, 2)
    wastage_cost = round(wastage_cost, 2)
    sale_ledger_cogs = round(sale_ledger_cogs, 2)
    actual_cogs = round(theoretical_cogs + wastage_cost, 2)
    variance = round(actual_cogs - theoretical_cogs, 2)
    variance_percent = (
        round(variance / theoretical_cogs * 100, 2) if theoretical_cogs > 0 else 0.0
    )
    total_revenue = round(total_revenue, 2)
    overall_pct = round(actual_cogs / total_revenue * 100, 2) if total_revenue > 0 else 0.0
    theoretical_pct = (
        round(theoretical_cogs / total_revenue * 100, 2) if total_revenue > 0 else 0.0
    )

    outlet_summaries = _food_cost_outlet_summaries(
        db,
        tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        fallback_revenue=total_revenue,
        fallback_theoretical=theoretical_cogs,
        fallback_wastage=wastage_cost,
    )

    return FoodCostReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        items=rows,
        outlets=outlet_summaries,
        total_revenue=total_revenue,
        total_food_cost=theoretical_cogs,
        theoretical_cogs=theoretical_cogs,
        wastage_cost=wastage_cost,
        sale_ledger_cogs=sale_ledger_cogs,
        actual_cogs=actual_cogs,
        variance=variance,
        variance_percent=variance_percent,
        total_margin=round(total_revenue - actual_cogs, 2),
        theoretical_margin=round(total_revenue - theoretical_cogs, 2),
        overall_food_cost_percent=overall_pct,
        theoretical_food_cost_percent=theoretical_pct,
    )


def _sum_ledger_cogs(
    db: Session,
    tenant_id: int,
    transaction_type: StockTransactionType,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    outlet_id: int | None,
) -> float:
    cost_expr = func.coalesce(
        StockLedger.line_cost,
        StockLedger.quantity_out * func.coalesce(RawMaterial.average_unit_cost, 0),
        0,
    )
    query = (
        db.query(func.coalesce(func.sum(cost_expr), 0))
        .outerjoin(RawMaterial, RawMaterial.id == StockLedger.raw_material_id)
        .filter(
            StockLedger.tenant_id == tenant_id,
            StockLedger.transaction_type == transaction_type,
        )
    )
    if outlet_id is not None:
        query = query.filter(StockLedger.outlet_id == outlet_id)
    query = _apply_date_filter(query, StockLedger, date_from, date_to)
    return float(query.scalar() or 0)


def _food_cost_outlet_summaries(
    db: Session,
    tenant_id: int,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    outlet_id: int | None,
    fallback_revenue: float,
    fallback_theoretical: float,
    fallback_wastage: float,
) -> list[FoodCostOutletSummary]:
    """Build outlet KPIs; for single-outlet filters reuse report totals."""
    outlet_query = db.query(Outlet).filter(
        Outlet.tenant_id == tenant_id,
        Outlet.is_active.is_(True),
        Outlet.status == RecordStatus.ACTIVE,
    )
    if outlet_id is not None:
        outlet_query = outlet_query.filter(Outlet.id == outlet_id)
    outlets = outlet_query.order_by(Outlet.outlet_name.asc()).all()
    if not outlets:
        return []

    if outlet_id is not None and len(outlets) == 1:
        outlet = outlets[0]
        actual = round(fallback_theoretical + fallback_wastage, 2)
        variance = round(actual - fallback_theoretical, 2)
        return [
            FoodCostOutletSummary(
                outlet_id=outlet.id,
                outlet_name=outlet.outlet_name,
                total_revenue=round(fallback_revenue, 2),
                theoretical_cogs=round(fallback_theoretical, 2),
                wastage_cost=round(fallback_wastage, 2),
                actual_cogs=actual,
                variance=variance,
                variance_percent=(
                    round(variance / fallback_theoretical * 100, 2)
                    if fallback_theoretical > 0
                    else 0.0
                ),
                overall_food_cost_percent=(
                    round(actual / fallback_revenue * 100, 2) if fallback_revenue > 0 else 0.0
                ),
            )
        ]

    # Multi-outlet: revenue by order outlet from item performance aggregation
    revenue_rows = (
        db.query(
            Order.outlet_id,
            func.coalesce(
                func.sum(OrderItem.quantity * OrderItem.price - OrderItem.discount_amount),
                0,
            ).label("net_sales"),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            Order.tenant_id == tenant_id,
            Order.order_status != OrderStatus.CANCELLED,
        )
    )
    revenue_rows = _apply_date_filter(revenue_rows, Order, date_from, date_to)
    revenue_rows = revenue_rows.group_by(Order.outlet_id).all()
    revenue_by_outlet = {int(r.outlet_id): float(r.net_sales or 0) for r in revenue_rows}

    # Theoretical COGS by outlet ≈ weighted by order lines * recipe_cost
    theo_query = (
        db.query(
            Order.outlet_id,
            OrderItem.menu_item_id,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("qty"),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            Order.tenant_id == tenant_id,
            Order.order_status != OrderStatus.CANCELLED,
        )
    )
    theo_query = _apply_date_filter(theo_query, Order, date_from, date_to)
    theo_rows = theo_query.group_by(Order.outlet_id, OrderItem.menu_item_id).all()
    menu_ids = list({int(r.menu_item_id) for r in theo_rows if r.menu_item_id})
    recipe_map: dict[int, float] = {}
    if menu_ids:
        recipe_map = {
            item.id: float(item.recipe_cost or 0)
            for item in db.query(MenuItem)
            .filter(MenuItem.tenant_id == tenant_id, MenuItem.id.in_(menu_ids))
            .all()
        }
    theoretical_by_outlet: dict[int, float] = {}
    for r in theo_rows:
        oid = int(r.outlet_id)
        cost = recipe_map.get(int(r.menu_item_id), 0.0) * float(r.qty or 0)
        theoretical_by_outlet[oid] = theoretical_by_outlet.get(oid, 0.0) + cost

    cost_expr = func.coalesce(
        StockLedger.line_cost,
        StockLedger.quantity_out * func.coalesce(RawMaterial.average_unit_cost, 0),
        0,
    )
    wastage_query = (
        db.query(
            StockLedger.outlet_id,
            func.coalesce(func.sum(cost_expr), 0).label("wastage_cost"),
        )
        .outerjoin(RawMaterial, RawMaterial.id == StockLedger.raw_material_id)
        .filter(
            StockLedger.tenant_id == tenant_id,
            StockLedger.transaction_type == StockTransactionType.WASTAGE,
        )
    )
    wastage_query = _apply_date_filter(wastage_query, StockLedger, date_from, date_to)
    wastage_by_outlet = {
        int(r.outlet_id): float(r.wastage_cost or 0)
        for r in wastage_query.group_by(StockLedger.outlet_id).all()
    }

    summaries: list[FoodCostOutletSummary] = []
    for outlet in outlets:
        revenue = round(revenue_by_outlet.get(outlet.id, 0.0), 2)
        theoretical = round(theoretical_by_outlet.get(outlet.id, 0.0), 2)
        wastage = round(wastage_by_outlet.get(outlet.id, 0.0), 2)
        actual = round(theoretical + wastage, 2)
        variance = round(actual - theoretical, 2)
        summaries.append(
            FoodCostOutletSummary(
                outlet_id=outlet.id,
                outlet_name=outlet.outlet_name,
                total_revenue=revenue,
                theoretical_cogs=theoretical,
                wastage_cost=wastage,
                actual_cogs=actual,
                variance=variance,
                variance_percent=(
                    round(variance / theoretical * 100, 2) if theoretical > 0 else 0.0
                ),
                overall_food_cost_percent=(
                    round(actual / revenue * 100, 2) if revenue > 0 else 0.0
                ),
            )
        )
    return summaries


def payment_summary(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outlet_id: int | None = None,
) -> PaymentSummaryReport:
    query = (
        db.query(
            Payment.payment_mode,
            func.count(Payment.id).label("transaction_count"),
            func.coalesce(func.sum(Payment.amount), 0).label("total_amount"),
        )
        .join(Bill, Bill.id == Payment.bill_id)
        .filter(
            Bill.tenant_id == tenant_id,
            Payment.status == PaymentRecordStatus.SUCCESS,
        )
    )

    if outlet_id is not None:
        query = query.filter(Bill.outlet_id == outlet_id)

    query = _apply_date_filter(query, Bill, date_from, date_to)
    query = query.group_by(Payment.payment_mode).order_by(func.sum(Payment.amount).desc())

    payments: list[PaymentSummaryRow] = []
    total_amount = 0.0
    for row in query.all():
        amount = float(row.total_amount or 0)
        payments.append(
            PaymentSummaryRow(
                payment_mode=row.payment_mode.value,
                transaction_count=int(row.transaction_count or 0),
                total_amount=round(amount, 2),
            )
        )
        total_amount += amount

    return PaymentSummaryReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        payments=payments,
        total_amount=round(total_amount, 2),
    )


def discount_report(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outlet_id: int | None = None,
) -> DiscountReport:
    query = (
        db.query(Bill, Order.order_number)
        .join(Order, Order.id == Bill.order_id)
        .filter(
            Bill.tenant_id == tenant_id,
            Bill.discount_amount > 0,
        )
    )

    if outlet_id is not None:
        query = query.filter(Bill.outlet_id == outlet_id)

    query = _apply_date_filter(query, Bill, date_from, date_to)
    query = query.order_by(Bill.created_at.desc())

    rows: list[DiscountReportRow] = []
    total_discounts = 0.0
    for bill, order_number in query.all():
        discount = float(bill.discount_amount or 0)
        total_discounts += discount
        rows.append(
            DiscountReportRow(
                outlet_id=bill.outlet_id,
                bill_number=bill.bill_number,
                order_number=order_number,
                discount_amount=round(discount, 2),
                bill_total=round(float(bill.grand_total or 0), 2),
                created_at=bill.created_at,
            )
        )

    return DiscountReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        total_discounts=round(total_discounts, 2),
        discount_count=len(rows),
        rows=rows,
    )


def customer_repeat_report(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outlet_id: int | None = None,
) -> CustomerRepeatReport:
    visit_query = db.query(CustomerVisit).filter(CustomerVisit.tenant_id == tenant_id)
    if outlet_id is not None:
        visit_query = visit_query.filter(CustomerVisit.outlet_id == outlet_id)
    visit_query = _apply_date_filter(visit_query, CustomerVisit, date_from, date_to)

    visit_counts = (
        visit_query.with_entities(
            CustomerVisit.customer_id,
            func.count(CustomerVisit.id).label("visit_count"),
        )
        .group_by(CustomerVisit.customer_id)
        .all()
    )

    if not visit_counts:
        customers = db.query(Customer).filter(
            Customer.tenant_id == tenant_id,
            Customer.is_active.is_(True),
            Customer.total_visits > 1,
        )
        if outlet_id is not None:
            customers = customers.filter(Customer.favourite_outlet_id == outlet_id)
        customer_rows: list[CustomerRepeatRow] = []
        repeat_count = 0
        for customer in customers.limit(100).all():
            is_repeat = customer.total_visits > 1
            if is_repeat:
                repeat_count += 1
            customer_rows.append(
                CustomerRepeatRow(
                    customer_id=customer.id,
                    full_name=customer.full_name,
                    mobile=customer.mobile,
                    total_visits=customer.total_visits,
                    total_spend=float(customer.total_spend or 0),
                    last_visit_at=customer.last_visit_at,
                    is_repeat_customer=is_repeat,
                )
            )
        total = len(customer_rows)
        repeat_rate = round(repeat_count / total * 100, 2) if total else 0
        return CustomerRepeatReport(
            date_from=date_from,
            date_to=date_to,
            outlet_id=outlet_id,
            total_customers=total,
            repeat_customers=repeat_count,
            repeat_rate_percent=repeat_rate,
            customers=customer_rows,
        )

    customer_ids = [row.customer_id for row in visit_counts]
    customers_map = {
        customer.id: customer
        for customer in db.query(Customer)
        .filter(Customer.tenant_id == tenant_id, Customer.id.in_(customer_ids))
        .all()
    }

    rows: list[CustomerRepeatRow] = []
    repeat_count = 0
    for visit_row in visit_counts:
        customer = customers_map.get(visit_row.customer_id)
        if customer is None:
            continue
        period_visits = int(visit_row.visit_count or 0)
        is_repeat = period_visits > 1 or customer.total_visits > 1
        if is_repeat:
            repeat_count += 1
        rows.append(
            CustomerRepeatRow(
                customer_id=customer.id,
                full_name=customer.full_name,
                mobile=customer.mobile,
                total_visits=period_visits,
                total_spend=float(customer.total_spend or 0),
                last_visit_at=customer.last_visit_at,
                is_repeat_customer=is_repeat,
            )
        )

    total = len(rows)
    repeat_rate = round(repeat_count / total * 100, 2) if total else 0
    return CustomerRepeatReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        total_customers=total,
        repeat_customers=repeat_count,
        repeat_rate_percent=repeat_rate,
        customers=rows,
    )


def campaign_performance(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> CampaignPerformanceReport:
    query = db.query(Campaign).filter(Campaign.tenant_id == tenant_id, Campaign.is_active.is_(True))
    query = _apply_date_filter(query, Campaign, date_from, date_to)
    campaigns = query.order_by(Campaign.created_at.desc()).all()

    rows: list[CampaignPerformanceRow] = []
    totals_sent = totals_delivered = totals_read = totals_replied = 0
    totals_converted = totals_failed = 0
    totals_cost = 0.0

    for campaign in campaigns:
        sent = campaign.sent_count or 0
        delivered = campaign.delivered_count or 0
        read = campaign.read_count or 0
        replied = campaign.replied_count or 0
        converted = campaign.converted_count or 0
        failed = campaign.failed_count or 0
        cost = float(campaign.actual_cost or 0)

        rows.append(
            CampaignPerformanceRow(
                campaign_id=campaign.id,
                campaign_name=campaign.campaign_name,
                channel=campaign.channel.value,
                status=campaign.status.value,
                sent_count=sent,
                delivered_count=delivered,
                read_count=read,
                replied_count=replied,
                converted_count=converted,
                failed_count=failed,
                actual_cost=round(cost, 2),
                delivery_rate_percent=_rate(delivered, sent),
                conversion_rate_percent=_rate(converted, sent),
            )
        )
        totals_sent += sent
        totals_delivered += delivered
        totals_read += read
        totals_replied += replied
        totals_converted += converted
        totals_failed += failed
        totals_cost += cost

    totals = None
    if rows:
        totals = CampaignPerformanceRow(
            campaign_id=0,
            campaign_name="All Campaigns",
            channel="all",
            status="all",
            sent_count=totals_sent,
            delivered_count=totals_delivered,
            read_count=totals_read,
            replied_count=totals_replied,
            converted_count=totals_converted,
            failed_count=totals_failed,
            actual_cost=round(totals_cost, 2),
            delivery_rate_percent=_rate(totals_delivered, totals_sent),
            conversion_rate_percent=_rate(totals_converted, totals_sent),
        )

    return CampaignPerformanceReport(
        date_from=date_from,
        date_to=date_to,
        campaigns=rows,
        totals=totals,
    )


def ai_usage_summary(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AiUsageSummaryReport:
    query = db.query(AiUsageLog).filter(AiUsageLog.tenant_id == tenant_id)
    query = _apply_date_filter(query, AiUsageLog, date_from, date_to)
    logs = query.all()

    by_module: dict[str, dict[str, float | int]] = {}
    by_provider: dict[str, dict[str, float | int]] = {}
    total_tokens = 0
    total_cost = 0.0

    for log in logs:
        total_tokens += log.total_tokens or 0
        total_cost += float(log.estimated_cost or 0)

        module_bucket = by_module.setdefault(
            log.module_name,
            {"requests": 0, "tokens": 0, "estimated_cost": 0.0},
        )
        module_bucket["requests"] = int(module_bucket["requests"]) + 1
        module_bucket["tokens"] = int(module_bucket["tokens"]) + (log.total_tokens or 0)
        module_bucket["estimated_cost"] = float(module_bucket["estimated_cost"]) + float(
            log.estimated_cost or 0
        )

        provider_key = str(log.provider_id or "unknown")
        provider_bucket = by_provider.setdefault(
            provider_key,
            {"requests": 0, "tokens": 0, "estimated_cost": 0.0},
        )
        provider_bucket["requests"] = int(provider_bucket["requests"]) + 1
        provider_bucket["tokens"] = int(provider_bucket["tokens"]) + (log.total_tokens or 0)
        provider_bucket["estimated_cost"] = float(provider_bucket["estimated_cost"]) + float(
            log.estimated_cost or 0
        )

    return AiUsageSummaryReport(
        date_from=date_from,
        date_to=date_to,
        total_requests=len(logs),
        total_tokens=total_tokens,
        total_estimated_cost=round(total_cost, 4),
        by_module=by_module,
        by_provider=by_provider,
    )


def communication_summary(
    db: Session,
    tenant_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outlet_id: int | None = None,
) -> CommunicationSummaryReport:
    conv_query = db.query(Conversation).filter(Conversation.tenant_id == tenant_id)
    msg_query = db.query(Message).filter(Message.tenant_id == tenant_id)

    if outlet_id is not None:
        conv_query = conv_query.filter(Conversation.outlet_id == outlet_id)
        msg_query = msg_query.filter(Message.outlet_id == outlet_id)

    conv_query = _apply_date_filter(conv_query, Conversation, date_from, date_to)
    msg_query = _apply_date_filter(msg_query, Message, date_from, date_to)

    conversations = conv_query.all()
    messages = msg_query.all()

    by_channel: dict[str, dict[str, int]] = {}
    inbound = outbound = 0

    for conversation in conversations:
        channel = conversation.channel.value
        bucket = by_channel.setdefault(
            channel,
            {"conversations": 0, "messages": 0, "inbound": 0, "outbound": 0},
        )
        bucket["conversations"] = int(bucket["conversations"]) + 1

    for message in messages:
        channel = message.channel.value
        bucket = by_channel.setdefault(
            channel,
            {"conversations": 0, "messages": 0, "inbound": 0, "outbound": 0},
        )
        bucket["messages"] = int(bucket["messages"]) + 1
        if message.direction == MessageDirection.INBOUND:
            bucket["inbound"] = int(bucket["inbound"]) + 1
            inbound += 1
        else:
            bucket["outbound"] = int(bucket["outbound"]) + 1
            outbound += 1

    open_conversations = sum(
        1 for conversation in conversations if conversation.status == ConversationStatus.OPEN
    )

    return CommunicationSummaryReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        total_conversations=len(conversations),
        open_conversations=open_conversations,
        total_messages=len(messages),
        inbound_messages=inbound,
        outbound_messages=outbound,
        by_channel=by_channel,
    )


def events_summary(
    db: Session,
    tenant_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    outlet_id: int | None = None,
) -> EventsSummaryReport:
    query = db.query(RestaurantEvent).filter(
        RestaurantEvent.tenant_id == tenant_id,
        RestaurantEvent.is_active.is_(True),
    )
    if outlet_id is not None:
        query = query.filter(RestaurantEvent.outlet_id == outlet_id)
    if date_from is not None:
        query = query.filter(RestaurantEvent.event_date >= date_from)
    if date_to is not None:
        query = query.filter(RestaurantEvent.event_date <= date_to)

    events = query.order_by(RestaurantEvent.event_date.asc()).all()
    rows = [
        EventsSummaryRow(
            event_id=event.id,
            title=event.title,
            event_type=event.event_type.value,
            event_date=event.event_date,
            status=event.status.value,
            outlet_id=event.outlet_id,
            expected_guests=event.expected_guests,
            estimated_amount=float(event.estimated_amount or 0),
            advance_paid=float(event.advance_paid or 0),
        )
        for event in events
    ]

    confirmed = sum(1 for event in events if event.status == EventStatus.CONFIRMED)
    completed = sum(1 for event in events if event.status == EventStatus.COMPLETED)
    total_estimated = sum(float(event.estimated_amount or 0) for event in events)
    total_advance = sum(float(event.advance_paid or 0) for event in events)

    return EventsSummaryReport(
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
        total_events=len(events),
        confirmed_events=confirmed,
        completed_events=completed,
        total_estimated_revenue=total_estimated,
        total_advance_collected=total_advance,
        events=rows,
    )


def _today_range() -> tuple[datetime, datetime]:
    today = datetime.utcnow().date()
    return datetime.combine(today, time.min), datetime.combine(today, time.max)


def _apply_date_filter(query, model, date_from: datetime | None, date_to: datetime | None):
    if date_from is not None:
        query = query.filter(model.created_at >= date_from)
    if date_to is not None:
        query = query.filter(model.created_at <= date_to)
    return query


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 2)
