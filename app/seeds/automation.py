"""Automation rules and run history."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.automation.models import (
    AutomationActionType,
    AutomationRule,
    AutomationRuleStatus,
    AutomationRun,
    AutomationRunStatus,
    AutomationTriggerType,
)
from app.seeds.base import SeedContext
from app.seeds.constants import SUPER_ADMIN_EMAIL


def seed_automation(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    marketing = ctx.users.get("marketing@restrochain.test")
    created_by = marketing.id if marketing else (admin.id if admin else None)
    if created_by is None:
        return

    welcome_template = ctx.templates.get("welcome_message")
    template_id = welcome_template.id if welcome_template else None

    rule_specs = [
        {
            "name": "Welcome New Customer",
            "trigger": AutomationTriggerType.NEW_CUSTOMER_ADDED,
            "status": AutomationRuleStatus.ACTIVE,
            "actions": [{"type": AutomationActionType.SEND_WHATSAPP_TEMPLATE.value, "template_id": template_id}],
        },
        {
            "name": "Re-engage Inactive Customers",
            "trigger": AutomationTriggerType.NO_VISIT_30_DAYS,
            "status": AutomationRuleStatus.ACTIVE,
            "actions": [{"type": AutomationActionType.SEND_SMS.value, "message": "We miss you! Visit us this week."}],
        },
        {
            "name": "Spa Booking Confirmation Follow-up",
            "trigger": AutomationTriggerType.SPA_BOOKING_CONFIRMED,
            "status": AutomationRuleStatus.ACTIVE,
            "actions": [
                {
                    "type": AutomationActionType.SEND_SMS.value,
                    "message": "Your spa appointment is confirmed. We look forward to seeing you!",
                }
            ],
        },
        {
            "name": "Banquet Booking Confirmation Follow-up",
            "trigger": AutomationTriggerType.BANQUET_BOOKING_CONFIRMED,
            "status": AutomationRuleStatus.ACTIVE,
            "actions": [
                {
                    "type": AutomationActionType.SEND_SMS.value,
                    "message": "Your banquet event is confirmed. Our events team will be in touch with final details.",
                }
            ],
        },
        {
            "name": "Guest Stay Confirmation Follow-up",
            "trigger": AutomationTriggerType.GUEST_RESERVATION_CONFIRMED,
            "status": AutomationRuleStatus.ACTIVE,
            "actions": [
                {
                    "type": AutomationActionType.SEND_SMS.value,
                    "message": "Your room reservation is confirmed. We look forward to welcoming you!",
                }
            ],
        },
        {
            "name": "Negative Feedback Alert",
            "trigger": AutomationTriggerType.NEGATIVE_FEEDBACK_RECEIVED,
            "status": AutomationRuleStatus.DRAFT,
            "actions": [{"type": AutomationActionType.NOTIFY_MANAGER.value}],
        },
    ]

    for spec in rule_specs:
        rule = (
            db.query(AutomationRule)
            .filter(AutomationRule.tenant_id == tenant.id, AutomationRule.rule_name == spec["name"])
            .first()
        )
        if rule is None:
            rule = AutomationRule(
                tenant_id=tenant.id,
                brand_id=brand.id,
                rule_name=spec["name"],
                trigger_type=spec["trigger"],
                conditions_json=json.dumps({}),
                actions_json=json.dumps(spec["actions"]),
                timing_json=json.dumps({"delay_minutes": 0}),
                status=spec["status"],
                created_by=created_by,
            )
            db.add(rule)
            db.flush()

            if spec["status"] == AutomationRuleStatus.ACTIVE:
                db.add(
                    AutomationRun(
                        tenant_id=tenant.id,
                        brand_id=brand.id,
                        rule_id=rule.id,
                        trigger_payload_json=json.dumps({"customer_id": 1, "demo": True}),
                        status=AutomationRunStatus.COMPLETED,
                        started_at=datetime.utcnow() - timedelta(hours=1),
                        completed_at=datetime.utcnow() - timedelta(minutes=58),
                    )
                )
