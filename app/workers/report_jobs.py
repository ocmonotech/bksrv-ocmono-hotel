from __future__ import annotations

import logging
from datetime import date

from app.workers.celery_app import celery_app
from app.workers.utils import task_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name="reports.daily_sales_report_mock", bind=True)
def daily_sales_report_mock(
    self,
    tenant_id: int | None = None,
    outlet_id: int | None = None,
) -> dict:
    """
    Mock daily sales report job — aggregates from DB, no external exports.
    """
    from app.modules.reports.service import dashboard_summary
    from app.modules.tenants.models import Tenant

    with task_db_session() as db:
        if tenant_id is None:
            tenant = db.query(Tenant).order_by(Tenant.id).first()
            if tenant is None:
                return {
                    "ok": False,
                    "mock": True,
                    "task_id": self.request.id,
                    "message": "No tenants found for daily sales report",
                }
            tenant_id = tenant.id

        summary = dashboard_summary(db, tenant_id, outlet_id=outlet_id)

        logger.info(
            "Mock daily sales report job %s tenant_id=%s outlet_id=%s sales=%s",
            self.request.id,
            tenant_id,
            outlet_id,
            summary.today_sales,
        )

        return {
            "ok": True,
            "mock": True,
            "task_id": self.request.id,
            "tenant_id": tenant_id,
            "outlet_id": outlet_id,
            "report_date": date.today().isoformat(),
            "today_sales": summary.today_sales,
            "total_orders": summary.total_orders,
            "average_bill_value": summary.average_bill_value,
            "active_outlets": summary.active_outlets,
            "total_discounts": summary.total_discounts,
            "cancelled_bills": summary.cancelled_bills,
            "message": "Mock daily sales report generated (no external API calls)",
        }


@celery_app.task(name="reports.low_stock_alert_mock", bind=True)
def low_stock_alert_mock(
    self,
    tenant_id: int | None = None,
    outlet_id: int | None = None,
) -> dict:
    """
    Mock low-stock alert job — reads inventory balances, no external notifications.
    """
    from app.modules.inventory.service import low_stock_report
    from app.modules.tenants.models import Tenant

    with task_db_session() as db:
        if tenant_id is None:
            tenant = db.query(Tenant).order_by(Tenant.id).first()
            if tenant is None:
                return {
                    "ok": False,
                    "mock": True,
                    "task_id": self.request.id,
                    "message": "No tenants found for low stock alert",
                }
            tenant_id = tenant.id

        low_items = low_stock_report(db, tenant_id, outlet_id=outlet_id)

        logger.info(
            "Mock low stock alert job %s tenant_id=%s outlet_id=%s items=%s",
            self.request.id,
            tenant_id,
            outlet_id,
            len(low_items),
        )

        return {
            "ok": True,
            "mock": True,
            "task_id": self.request.id,
            "tenant_id": tenant_id,
            "outlet_id": outlet_id,
            "low_stock_count": len(low_items),
            "items": [
                {
                    "outlet_id": item.outlet_id,
                    "raw_material_id": item.raw_material_id,
                    "name": item.name,
                    "quantity_on_hand": item.quantity_on_hand,
                    "reorder_level": item.reorder_level,
                    "shortfall": item.shortfall,
                }
                for item in low_items[:50]
            ],
            "message": "Mock low stock alert generated (no external API calls)",
        }
