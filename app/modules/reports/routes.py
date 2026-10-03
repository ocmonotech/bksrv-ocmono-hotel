from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.reports import service
from app.modules.reports.schemas import (
    AiUsageSummaryReport,
    CampaignPerformanceReport,
    CommunicationSummaryReport,
    CustomerRepeatReport,
    DashboardSummary,
    DiscountReport,
    EventsSummaryReport,
    FoodCostReport,
    ItemPerformanceReport,
    OutletComparisonReport,
    PaymentSummaryReport,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/dashboard-summary", response_model=DashboardSummary)
def dashboard_summary(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> DashboardSummary:
    return service.dashboard_summary(db, current_user.tenant_id, outlet_id)


@router.get("/outlet-comparison", response_model=OutletComparisonReport)
def outlet_comparison(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> OutletComparisonReport:
    return service.outlet_comparison(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )


@router.get("/item-performance", response_model=ItemPerformanceReport)
def item_performance(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> ItemPerformanceReport:
    return service.item_performance(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )


@router.get("/food-cost", response_model=FoodCostReport)
def food_cost_report(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> FoodCostReport:
    return service.food_cost_report(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )


@router.get("/payment-summary", response_model=PaymentSummaryReport)
def payment_summary(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> PaymentSummaryReport:
    return service.payment_summary(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )


@router.get("/discount-report", response_model=DiscountReport)
def discount_report(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> DiscountReport:
    return service.discount_report(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )


@router.get("/customer-repeat-report", response_model=CustomerRepeatReport)
def customer_repeat_report(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> CustomerRepeatReport:
    return service.customer_repeat_report(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )


@router.get("/campaign-performance", response_model=CampaignPerformanceReport)
def campaign_performance(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> CampaignPerformanceReport:
    return service.campaign_performance(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/ai-usage-summary", response_model=AiUsageSummaryReport)
def ai_usage_summary(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> AiUsageSummaryReport:
    return service.ai_usage_summary(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/communication-summary", response_model=CommunicationSummaryReport)
def communication_summary(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> CommunicationSummaryReport:
    return service.communication_summary(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )


@router.get("/events-summary", response_model=EventsSummaryReport)
def events_summary(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REPORTS_READ)),
) -> EventsSummaryReport:
    return service.events_summary(
        db,
        current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        outlet_id=outlet_id,
    )
