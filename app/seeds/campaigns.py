"""Marketing campaigns, recipients, events, and automation flows."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.campaigns.models import (
    AutomationFlow,
    AutomationFlowStatus,
    Campaign,
    CampaignChannel,
    CampaignEvent,
    CampaignRecipient,
    CampaignStatus,
    RecipientStatus,
)
from app.seeds.base import SeedContext
from app.seeds.constants import SUPER_ADMIN_EMAIL


def seed_campaigns(db: Session, ctx: SeedContext) -> None:
    ctx.campaigns = _seed_campaigns(db, ctx)
    _seed_campaign_recipients(db, ctx)
    _seed_automation_flows(db, ctx)


def _seed_campaigns(db: Session, ctx: SeedContext) -> dict[str, Campaign]:
    tenant, brand = ctx.tenant, ctx.brand
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    marketing = ctx.users.get("marketing@restrochain.test")
    created_by = marketing.id if marketing else (admin.id if admin else None)
    if created_by is None:
        return {}

    welcome_template = ctx.templates.get("welcome_message")
    promo_template = ctx.templates.get("newsletter_promo")
    andheri_id = ctx.outlets["Andheri West"].id

    campaign_specs = [
        {
            "name": "Weekend Welcome Blast",
            "channel": CampaignChannel.WHATSAPP,
            "goal": "Drive weekend footfall",
            "status": CampaignStatus.COMPLETED,
            "template": welcome_template,
            "sent": 120,
            "delivered": 115,
            "read": 89,
            "replied": 23,
            "converted": 8,
        },
        {
            "name": "Monsoon Promo Email",
            "channel": CampaignChannel.EMAIL,
            "goal": "Promote monsoon specials",
            "status": CampaignStatus.SCHEDULED,
            "template": promo_template,
            "sent": 0,
            "delivered": 0,
            "read": 0,
            "replied": 0,
            "converted": 0,
        },
        {
            "name": "Diwali SMS Burst",
            "channel": CampaignChannel.SMS,
            "goal": "Festive season footfall boost",
            "status": CampaignStatus.COMPLETED,
            "template": None,
            "sent": 340,
            "delivered": 325,
            "read": 0,
            "replied": 0,
            "converted": 42,
        },
        {
            "name": "New Year WhatsApp Greet",
            "channel": CampaignChannel.WHATSAPP,
            "goal": "New Year reservations drive",
            "status": CampaignStatus.DRAFT,
            "template": welcome_template,
            "sent": 0,
            "delivered": 0,
            "read": 0,
            "replied": 0,
            "converted": 0,
        },
        {
            "name": "Corporate Lunch Email",
            "channel": CampaignChannel.EMAIL,
            "goal": "Acquire corporate lunch regulars",
            "status": CampaignStatus.PAUSED,
            "template": promo_template,
            "sent": 80,
            "delivered": 76,
            "read": 48,
            "replied": 6,
            "converted": 3,
        },
    ]

    campaigns: dict[str, Campaign] = {}
    for spec in campaign_specs:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.tenant_id == tenant.id, Campaign.campaign_name == spec["name"])
            .first()
        )
        if campaign is None:
            campaign = Campaign(
                tenant_id=tenant.id,
                brand_id=brand.id,
                campaign_name=spec["name"],
                channel=spec["channel"],
                goal=spec["goal"],
                status=spec["status"],
                selected_outlets_json=json.dumps([andheri_id]),
                audience_filter_json=json.dumps({"consent_whatsapp": True}),
                template_id=spec["template"].id if spec["template"] else None,
                scheduled_at=datetime.utcnow() + timedelta(days=3) if spec["status"] == CampaignStatus.SCHEDULED else None,
                sent_count=spec["sent"],
                delivered_count=spec["delivered"],
                read_count=spec["read"],
                replied_count=spec["replied"],
                converted_count=spec["converted"],
                estimated_cost=500,
                actual_cost=420 if spec["sent"] else 0,
                created_by=created_by,
            )
            db.add(campaign)
            db.flush()
        campaigns[spec["name"]] = campaign
    return campaigns


def _seed_campaign_recipients(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant
    campaign = ctx.campaigns.get("Weekend Welcome Blast")
    if campaign is None:
        return

    andheri = ctx.outlets["Andheri West"]
    recipient_specs = [
        ("+919800000001", RecipientStatus.CONVERTED),
        ("+919800000002", RecipientStatus.READ),
        ("+919810000001", RecipientStatus.REPLIED),
    ]

    for mobile, status in recipient_specs:
        customer = ctx.customers.get(mobile)
        lead = ctx.leads.get(mobile)
        existing = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.mobile == mobile,
            )
            .first()
        )
        if existing is not None:
            continue

        recipient = CampaignRecipient(
            campaign_id=campaign.id,
            customer_id=customer.id if customer else None,
            lead_id=lead.id if lead else None,
            outlet_id=andheri.id,
            mobile=mobile,
            email=customer.email if customer else None,
            status=status,
            provider_message_id=f"demo-campaign-msg-{mobile}",
        )
        db.add(recipient)
        db.flush()

        db.add(
            CampaignEvent(
                campaign_id=campaign.id,
                recipient_id=recipient.id,
                event_type=status.value,
                event_payload_json=json.dumps({"demo": True}),
            )
        )


def _seed_automation_flows(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    flows = [
        ("New Lead Welcome", "lead_created", CampaignChannel.WHATSAPP, AutomationFlowStatus.ACTIVE),
        ("Birthday Greeting", "customer_birthday", CampaignChannel.WHATSAPP, AutomationFlowStatus.DRAFT),
        ("Post-Visit Feedback SMS", "order_completed", CampaignChannel.SMS, AutomationFlowStatus.ACTIVE),
        ("Re-engagement Email", "customer_inactive_30d", CampaignChannel.EMAIL, AutomationFlowStatus.ACTIVE),
        ("Booking Reminder WhatsApp", "booking_confirmed", CampaignChannel.WHATSAPP, AutomationFlowStatus.ACTIVE),
    ]
    for name, trigger, channel, status in flows:
        existing = (
            db.query(AutomationFlow)
            .filter(AutomationFlow.tenant_id == tenant.id, AutomationFlow.name == name)
            .first()
        )
        if existing is not None:
            continue
        db.add(
            AutomationFlow(
                tenant_id=tenant.id,
                brand_id=brand.id,
                name=name,
                trigger_type=trigger,
                channel=channel,
                definition_json=json.dumps({"steps": [{"action": "send_template", "delay_minutes": 0}]}),
                status=status,
            )
        )
