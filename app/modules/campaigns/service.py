from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.brands.models import Brand
from app.modules.campaigns.models import (
    Campaign,
    CampaignEvent,
    CampaignRecipient,
    CampaignStatus,
    RecipientStatus,
)
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignDetailRead,
    CampaignRead,
    CampaignRecipientRead,
    CampaignReport,
    CampaignSchedule,
    CampaignUpdate,
    MockLaunchResponse,
)
from app.modules.communications.models import MessageTemplate
from app.modules.communications.providers.registry import get_provider_adapter
from app.modules.customers.models import Customer, CustomerStatus
from app.modules.leads.models import Lead, LeadStatus, Segment
from app.modules.outlets.models import Outlet

CHANNEL_COST_INR = {
    "whatsapp": 0.50,
    "sms": 0.15,
    "email": 0.05,
}

EDITABLE_STATUSES = {CampaignStatus.DRAFT, CampaignStatus.SCHEDULED, CampaignStatus.PAUSED}


def create_campaign(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: CampaignCreate,
    default_brand_id: int | None = None,
) -> CampaignRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    for outlet_id in data.selected_outlets:
        _get_outlet(db, tenant_id, outlet_id)

    if data.template_id is not None:
        _get_template(db, tenant_id, data.template_id)

    campaign = Campaign(
        tenant_id=tenant_id,
        brand_id=brand_id,
        campaign_name=data.campaign_name,
        channel=data.channel,
        goal=data.goal,
        status=CampaignStatus.SCHEDULED if data.scheduled_at else CampaignStatus.DRAFT,
        selected_outlets_json=json.dumps(data.selected_outlets),
        audience_filter_json=json.dumps(data.audience_filter),
        template_id=data.template_id,
        scheduled_at=data.scheduled_at,
        estimated_cost=data.estimated_cost,
        created_by=user_id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign_to_read(campaign)


def list_campaigns(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    channel=None,
    status: CampaignStatus | None = None,
    brand_id: int | None = None,
) -> tuple[list[CampaignRead], int]:
    query = db.query(Campaign).filter(Campaign.tenant_id == tenant_id, Campaign.is_active.is_(True))

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Campaign.brand_id.is_(None), Campaign.brand_id == brand_id))

    if channel is not None:
        query = query.filter(Campaign.channel == channel)

    if status is not None:
        query = query.filter(Campaign.status == status)

    query = query.order_by(Campaign.created_at.desc(), Campaign.id.desc())
    campaigns, total = paginate_query(query, page, page_size)
    return [_campaign_to_read(campaign) for campaign in campaigns], total


def get_campaign_details(db: Session, tenant_id: int, campaign_id: int) -> CampaignDetailRead:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id)
    detail = CampaignDetailRead(**_campaign_to_read(campaign).model_dump())
    detail.recipient_count = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign.id)
        .count()
    )
    return detail


def update_campaign(
    db: Session,
    tenant_id: int,
    campaign_id: int,
    data: CampaignUpdate,
) -> CampaignRead:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id)

    if campaign.status not in EDITABLE_STATUSES:
        raise ConflictError("Campaign cannot be updated in its current status")

    updates = data.model_dump(exclude_unset=True)

    if "selected_outlets" in updates:
        for outlet_id in updates["selected_outlets"]:
            _get_outlet(db, tenant_id, outlet_id)
        campaign.selected_outlets_json = json.dumps(updates.pop("selected_outlets"))

    if "audience_filter" in updates:
        campaign.audience_filter_json = json.dumps(updates.pop("audience_filter"))

    if updates.get("template_id") is not None:
        _get_template(db, tenant_id, updates["template_id"])

    for field, value in updates.items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return _campaign_to_read(campaign)


def schedule_campaign(
    db: Session,
    tenant_id: int,
    campaign_id: int,
    data: CampaignSchedule,
) -> CampaignRead:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id)

    if campaign.status not in {CampaignStatus.DRAFT, CampaignStatus.PAUSED}:
        raise ConflictError("Only draft or paused campaigns can be scheduled")

    campaign.scheduled_at = data.scheduled_at
    campaign.status = CampaignStatus.SCHEDULED
    _add_campaign_event(
        db,
        campaign.id,
        None,
        "scheduled",
        {"scheduled_at": data.scheduled_at.isoformat()},
    )
    db.commit()
    db.refresh(campaign)
    return _campaign_to_read(campaign)


def pause_campaign(db: Session, tenant_id: int, campaign_id: int) -> CampaignRead:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id)

    if campaign.status != CampaignStatus.RUNNING:
        raise ConflictError("Only running campaigns can be paused")

    campaign.status = CampaignStatus.PAUSED
    _add_campaign_event(db, campaign.id, None, "paused", {})
    db.commit()
    db.refresh(campaign)
    return _campaign_to_read(campaign)


def resume_campaign(db: Session, tenant_id: int, campaign_id: int) -> CampaignRead:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id)

    if campaign.status != CampaignStatus.PAUSED:
        raise ConflictError("Only paused campaigns can be resumed")

    campaign.status = CampaignStatus.RUNNING
    _add_campaign_event(db, campaign.id, None, "resumed", {})
    db.commit()
    db.refresh(campaign)
    return _campaign_to_read(campaign)


def cancel_campaign(db: Session, tenant_id: int, campaign_id: int) -> CampaignRead:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id)

    if campaign.status in {CampaignStatus.COMPLETED, CampaignStatus.FAILED}:
        raise ConflictError("Campaign is already finished")

    campaign.status = CampaignStatus.FAILED
    pending = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status == RecipientStatus.PENDING,
        )
        .all()
    )
    for recipient in pending:
        recipient.status = RecipientStatus.FAILED
        recipient.error_message = "Campaign cancelled"
        campaign.failed_count += 1

    _add_campaign_event(db, campaign.id, None, "cancelled", {})
    db.commit()
    db.refresh(campaign)
    return _campaign_to_read(campaign)


def get_campaign_recipients(
    db: Session,
    tenant_id: int,
    campaign_id: int,
    page: int,
    page_size: int,
    status: RecipientStatus | None = None,
) -> tuple[list[CampaignRecipientRead], int]:
    _get_campaign_entity(db, tenant_id, campaign_id)

    query = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id)
    if status is not None:
        query = query.filter(CampaignRecipient.status == status)

    query = query.order_by(CampaignRecipient.id)
    recipients, total = paginate_query(query, page, page_size)
    return [CampaignRecipientRead.model_validate(item) for item in recipients], total


def get_campaign_report(db: Session, tenant_id: int, campaign_id: int) -> CampaignReport:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id)
    recipient_total = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign.id)
        .count()
    )

    breakdown: dict[str, int] = {}
    for status in RecipientStatus:
        count = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.status == status,
            )
            .count()
        )
        if count:
            breakdown[status.value] = count

    sent = campaign.sent_count or 0
    delivered = campaign.delivered_count or 0
    read = campaign.read_count or 0
    replied = campaign.replied_count or 0
    converted = campaign.converted_count or 0

    return CampaignReport(
        campaign_id=campaign.id,
        campaign_name=campaign.campaign_name,
        status=campaign.status,
        channel=campaign.channel,
        sent_count=sent,
        delivered_count=delivered,
        read_count=read,
        replied_count=replied,
        converted_count=converted,
        failed_count=campaign.failed_count or 0,
        delivery_rate=_rate(delivered, sent),
        read_rate=_rate(read, sent),
        reply_rate=_rate(replied, sent),
        conversion_rate=_rate(converted, sent),
        estimated_cost=float(campaign.estimated_cost or 0),
        actual_cost=float(campaign.actual_cost or 0),
        recipient_total=recipient_total,
        recipient_breakdown=breakdown,
    )


async def mock_launch_campaign(
    db: Session,
    tenant_id: int,
    campaign_id: int,
    user_id: int | None = None,
) -> MockLaunchResponse:
    campaign = _get_campaign_entity(db, tenant_id, campaign_id, with_recipients=True)
    previous_status = campaign.status

    if campaign.status not in {
        CampaignStatus.DRAFT,
        CampaignStatus.SCHEDULED,
        CampaignStatus.PAUSED,
        CampaignStatus.RUNNING,
    }:
        raise ConflictError("Campaign cannot be launched in its current status")

    existing_pending = [
        recipient
        for recipient in campaign.recipients
        if recipient.status == RecipientStatus.PENDING
    ]
    if not existing_pending:
        _build_recipients_from_audience(db, campaign)

    campaign.status = CampaignStatus.RUNNING
    _add_campaign_event(db, campaign.id, None, "launch_started", {"mock": True})

    adapter = get_provider_adapter(campaign.channel)
    cost_per_message = CHANNEL_COST_INR.get(campaign.channel.value, 0.10)
    processed = 0

    recipients = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.campaign_id == campaign.id,
            CampaignRecipient.status == RecipientStatus.PENDING,
        )
        .all()
    )

    for index, recipient in enumerate(recipients):
        receiver = recipient.mobile or recipient.email or f"mock_{recipient.id}@local"
        sender = _default_sender(campaign.channel.value)

        try:
            result = await adapter.send(
                sender=sender,
                receiver=receiver,
                message_text=f"Campaign: {campaign.campaign_name}",
                config={},
            )
            if not result.success:
                raise RuntimeError(result.error_message or "Mock send failed")

            recipient.provider_message_id = result.provider_message_id
            recipient.status = RecipientStatus.SENT
            recipient.error_message = None
            campaign.sent_count += 1
            campaign.actual_cost = float(campaign.actual_cost or 0) + cost_per_message
            _add_campaign_event(
                db,
                campaign.id,
                recipient.id,
                "sent",
                {"provider_message_id": result.provider_message_id, "mock": True},
            )

            if index % 10 != 9:
                recipient.status = RecipientStatus.DELIVERED
                campaign.delivered_count += 1
                _add_campaign_event(db, campaign.id, recipient.id, "delivered", {"mock": True})

            if index % 3 == 0:
                recipient.status = RecipientStatus.READ
                campaign.read_count += 1
                _add_campaign_event(db, campaign.id, recipient.id, "read", {"mock": True})

            if index % 7 == 0:
                recipient.status = RecipientStatus.REPLIED
                campaign.replied_count += 1
                _add_campaign_event(db, campaign.id, recipient.id, "replied", {"mock": True})

            if index % 11 == 0:
                recipient.status = RecipientStatus.CONVERTED
                campaign.converted_count += 1
                _add_campaign_event(db, campaign.id, recipient.id, "converted", {"mock": True})

            processed += 1
        except Exception as exc:
            recipient.status = RecipientStatus.FAILED
            recipient.error_message = str(exc)
            campaign.failed_count += 1
            _add_campaign_event(
                db,
                campaign.id,
                recipient.id,
                "failed",
                {"error": str(exc), "mock": True},
            )

    campaign.status = CampaignStatus.COMPLETED
    _add_campaign_event(
        db,
        campaign.id,
        None,
        "launch_completed",
        {
            "processed": processed,
            "sent_count": campaign.sent_count,
            "mock": True,
        },
    )

    from app.modules.audit.models import AuditAction
    from app.modules.audit.service import log_audit

    log_audit(
        db,
        tenant_id=tenant_id,
        brand_id=campaign.brand_id,
        outlet_id=None,
        user_id=user_id,
        action=AuditAction.CAMPAIGN_LAUNCHED.value,
        module_name="campaigns",
        record_type="campaign",
        record_id=campaign.id,
        old_data={"status": previous_status.value},
        new_data={
            "status": campaign.status.value,
            "recipients_processed": processed,
            "sent_count": campaign.sent_count,
            "failed_count": campaign.failed_count,
        },
    )

    db.commit()
    db.refresh(campaign)

    return MockLaunchResponse(
        success=True,
        campaign_id=campaign.id,
        status=campaign.status,
        recipients_processed=processed,
        message=f"Mock campaign launch completed for {processed} recipients",
    )


def _build_recipients_from_audience(db: Session, campaign: Campaign) -> None:
    filters = _parse_json(campaign.audience_filter_json)
    selected_outlets = _parse_json_list(campaign.selected_outlets_json)
    outlet_id = filters.get("outlet_id") or (selected_outlets[0] if selected_outlets else None)

    recipients_data: list[dict] = []

    if filters.get("include_customers", True):
        customer_query = db.query(Customer).filter(
            Customer.tenant_id == campaign.tenant_id,
            Customer.is_active.is_(True),
            Customer.status == CustomerStatus.ACTIVE,
        )
        if campaign.brand_id is not None:
            customer_query = customer_query.filter(
                or_(Customer.brand_id.is_(None), Customer.brand_id == campaign.brand_id)
            )

        channel = campaign.channel.value
        if channel == "whatsapp":
            customer_query = customer_query.filter(Customer.consent_whatsapp.is_(True))
        elif channel == "sms":
            customer_query = customer_query.filter(Customer.consent_sms.is_(True))
        elif channel == "email":
            customer_query = customer_query.filter(
                Customer.consent_email.is_(True),
                Customer.email.isnot(None),
            )

        min_loyalty = filters.get("min_loyalty_points")
        if min_loyalty is not None:
            customer_query = customer_query.filter(Customer.loyalty_points >= min_loyalty)

        if outlet_id is not None:
            customer_query = customer_query.filter(
                or_(
                    Customer.favourite_outlet_id == outlet_id,
                    Customer.favourite_outlet_id.is_(None),
                )
            )

        for customer in customer_query.limit(100).all():
            recipients_data.append(
                {
                    "customer_id": customer.id,
                    "lead_id": None,
                    "outlet_id": outlet_id or customer.favourite_outlet_id,
                    "mobile": customer.mobile,
                    "email": customer.email,
                }
            )

    if filters.get("include_leads", False):
        lead_query = db.query(Lead).filter(
            Lead.tenant_id == campaign.tenant_id,
            Lead.is_active.is_(True),
            Lead.status == LeadStatus.OPEN,
        )
        if campaign.brand_id is not None:
            lead_query = lead_query.filter(
                or_(Lead.brand_id.is_(None), Lead.brand_id == campaign.brand_id)
            )
        if outlet_id is not None:
            lead_query = lead_query.filter(
                or_(Lead.outlet_id == outlet_id, Lead.outlet_id.is_(None))
            )

        min_score = filters.get("min_lead_score")
        if min_score is not None:
            lead_query = lead_query.filter(Lead.lead_score >= min_score)

        for lead in lead_query.limit(100).all():
            recipients_data.append(
                {
                    "customer_id": lead.customer_id,
                    "lead_id": lead.id,
                    "outlet_id": outlet_id or lead.outlet_id,
                    "mobile": lead.mobile,
                    "email": lead.email,
                }
            )

    segment_id = filters.get("segment_id")
    if segment_id is not None:
        from app.modules.leads.models import Segment
        from app.modules.leads.segment_filters import (
            resolve_segment_customers,
            resolve_segment_leads,
        )

        segment = (
            db.query(Segment)
            .filter(Segment.id == segment_id, Segment.tenant_id == campaign.tenant_id)
            .first()
        )
        if segment is not None:
            _add_campaign_event(
                db,
                campaign.id,
                None,
                "segment_filter_applied",
                {"segment_id": segment_id, "segment_name": segment.segment_name},
            )
            for lead in resolve_segment_leads(db, campaign.tenant_id, segment):
                if lead.mobile or lead.email:
                    recipients_data.append(
                        {
                            "customer_id": lead.customer_id,
                            "lead_id": lead.id,
                            "outlet_id": outlet_id or lead.outlet_id,
                            "mobile": lead.mobile,
                            "email": lead.email,
                        }
                    )
            for customer in resolve_segment_customers(db, campaign.tenant_id, segment):
                if customer.mobile or customer.email:
                    recipients_data.append(
                        {
                            "customer_id": customer.id,
                            "lead_id": None,
                            "outlet_id": outlet_id or customer.favourite_outlet_id,
                            "mobile": customer.mobile,
                            "email": customer.email,
                        }
                    )

    if not recipients_data:
        raise ConflictError("No recipients matched the selected audience filters")

    for item in recipients_data:
        db.add(
            CampaignRecipient(
                campaign_id=campaign.id,
                customer_id=item["customer_id"],
                lead_id=item["lead_id"],
                outlet_id=item["outlet_id"],
                mobile=item["mobile"],
                email=item["email"],
                status=RecipientStatus.PENDING,
            )
        )

    db.flush()


def _add_campaign_event(
    db: Session,
    campaign_id: int,
    recipient_id: int | None,
    event_type: str,
    payload: dict,
) -> None:
    db.add(
        CampaignEvent(
            campaign_id=campaign_id,
            recipient_id=recipient_id,
            event_type=event_type,
            event_payload_json=json.dumps(payload),
        )
    )


def _campaign_to_read(campaign: Campaign) -> CampaignRead:
    payload = CampaignRead.model_validate(campaign)
    payload.selected_outlets = _parse_json_list(campaign.selected_outlets_json)
    payload.audience_filter = _parse_json(campaign.audience_filter_json)
    return payload


def _get_campaign_entity(
    db: Session,
    tenant_id: int,
    campaign_id: int,
    with_recipients: bool = False,
) -> Campaign:
    query = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
    if with_recipients:
        query = query.options(joinedload(Campaign.recipients))
    campaign = query.first()
    if campaign is None:
        raise NotFoundError("Campaign not found")
    return campaign


def _validate_brand(db: Session, tenant_id: int, brand_id: int | None) -> None:
    if brand_id is None:
        return
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if brand is None:
        raise NotFoundError("Brand not found")


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_template(db: Session, tenant_id: int, template_id: int) -> MessageTemplate:
    template = (
        db.query(MessageTemplate)
        .filter(MessageTemplate.id == template_id, MessageTemplate.tenant_id == tenant_id)
        .first()
    )
    if template is None:
        raise NotFoundError("Message template not found")
    return template


def _default_sender(channel: str) -> str:
    if channel == "email":
        return "campaigns@mock.local"
    if channel == "sms":
        return "MOCKSMS"
    return "mock-whatsapp"


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 2)


def _parse_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return parsed
    return []
