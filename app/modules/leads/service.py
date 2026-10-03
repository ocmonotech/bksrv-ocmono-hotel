from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import NotFoundError
from app.modules.brands.models import Brand
from app.modules.campaigns.models import Campaign
from app.modules.customers.models import Customer
from app.modules.leads.models import (
    Lead,
    LeadActivity,
    LeadActivityType,
    LeadStage,
    LeadStatus,
    Segment,
)
from app.modules.leads.schemas import (
    LeadActivityCreate,
    LeadActivityRead,
    LeadAssign,
    LeadCreate,
    LeadDetailRead,
    LeadFollowUpUpdate,
    LeadRead,
    LeadStageUpdate,
    SegmentCreate,
    SegmentEstimateResponse,
    SegmentRead,
    SegmentUpdate,
)
from app.modules.outlets.models import Outlet
from app.modules.users.models import User


def create_lead(
    db: Session,
    tenant_id: int,
    data: LeadCreate,
    default_brand_id: int | None = None,
) -> LeadRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    if data.outlet_id is not None:
        _get_outlet(db, tenant_id, data.outlet_id)
    if data.customer_id is not None:
        _get_customer(db, tenant_id, data.customer_id)
    if data.campaign_id is not None:
        _get_campaign(db, tenant_id, data.campaign_id)
    if data.assigned_to is not None:
        _get_user(db, tenant_id, data.assigned_to)

    lead = Lead(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        customer_id=data.customer_id,
        lead_name=data.lead_name,
        mobile=data.mobile,
        email=data.email,
        source=data.source,
        campaign_id=data.campaign_id,
        lead_score=data.lead_score,
        stage=data.stage,
        assigned_to=data.assigned_to,
        last_message=data.last_message,
        next_followup_at=data.next_followup_at,
        status=LeadStatus.OPEN,
        tags_json=_serialize_tags(data.tags),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return _lead_to_read(lead)


def list_leads(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    source=None,
    campaign_id: int | None = None,
    stage=None,
    min_lead_score: int | None = None,
    max_lead_score: int | None = None,
    assigned_user: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tags: list[str] | None = None,
    brand_id: int | None = None,
    status: LeadStatus | None = None,
) -> tuple[list[LeadRead], int]:
    query = db.query(Lead).filter(Lead.tenant_id == tenant_id)

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Lead.brand_id.is_(None), Lead.brand_id == brand_id))

    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(Lead.outlet_id == outlet_id)

    if source is not None:
        query = query.filter(Lead.source == source)

    if campaign_id is not None:
        _get_campaign(db, tenant_id, campaign_id)
        query = query.filter(Lead.campaign_id == campaign_id)

    if stage is not None:
        query = query.filter(Lead.stage == stage)

    if min_lead_score is not None:
        query = query.filter(Lead.lead_score >= min_lead_score)

    if max_lead_score is not None:
        query = query.filter(Lead.lead_score <= max_lead_score)

    if assigned_user is not None:
        _get_user(db, tenant_id, assigned_user)
        query = query.filter(Lead.assigned_to == assigned_user)

    if date_from is not None:
        query = query.filter(Lead.created_at >= date_from)

    if date_to is not None:
        query = query.filter(Lead.created_at <= date_to)

    if status is not None:
        query = query.filter(Lead.status == status)

    if tags:
        for tag in tags:
            normalized = tag.strip().lower()
            if normalized:
                query = query.filter(Lead.tags_json.ilike(f'%{normalized}%'))

    query = query.order_by(Lead.lead_score.desc(), Lead.created_at.desc())
    leads, total = paginate_query(query, page, page_size)
    return [_lead_to_read(lead) for lead in leads], total


def get_lead_details(db: Session, tenant_id: int, lead_id: int) -> LeadDetailRead:
    lead = _get_lead_entity(db, tenant_id, lead_id, with_activities=True)
    detail = LeadDetailRead.model_validate(_lead_to_read(lead))
    detail.activities = [LeadActivityRead.model_validate(activity) for activity in lead.activities]
    return detail


def update_lead_stage(
    db: Session,
    tenant_id: int,
    user_id: int,
    lead_id: int,
    data: LeadStageUpdate,
) -> LeadRead:
    lead = _get_lead_entity(db, tenant_id, lead_id)
    previous_stage = lead.stage
    lead.stage = data.stage

    if data.stage in {LeadStage.CONVERTED, LeadStage.LOST}:
        lead.status = LeadStatus.CLOSED

    db.add(
        LeadActivity(
            tenant_id=lead.tenant_id,
            brand_id=lead.brand_id,
            lead_id=lead.id,
            activity_type=LeadActivityType.STAGE_CHANGE,
            note=data.note or f"Stage changed from {previous_stage.value} to {data.stage.value}",
            created_by=user_id,
        )
    )
    db.commit()
    db.refresh(lead)
    return _lead_to_read(lead)


def assign_lead(
    db: Session,
    tenant_id: int,
    user_id: int,
    lead_id: int,
    data: LeadAssign,
) -> LeadRead:
    lead = _get_lead_entity(db, tenant_id, lead_id)
    assignee = _get_user(db, tenant_id, data.assigned_to)

    lead.assigned_to = assignee.id
    db.add(
        LeadActivity(
            tenant_id=lead.tenant_id,
            brand_id=lead.brand_id,
            lead_id=lead.id,
            activity_type=LeadActivityType.ASSIGNMENT,
            note=f"Lead assigned to user {assignee.id}",
            created_by=user_id,
        )
    )
    db.commit()
    db.refresh(lead)
    return _lead_to_read(lead)


def add_activity(
    db: Session,
    tenant_id: int,
    user_id: int,
    lead_id: int,
    data: LeadActivityCreate,
) -> LeadActivityRead:
    lead = _get_lead_entity(db, tenant_id, lead_id)

    activity = LeadActivity(
        tenant_id=lead.tenant_id,
        brand_id=lead.brand_id,
        lead_id=lead.id,
        activity_type=data.activity_type,
        note=data.note,
        created_by=user_id,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return LeadActivityRead.model_validate(activity)


def add_follow_up(
    db: Session,
    tenant_id: int,
    user_id: int,
    lead_id: int,
    data: LeadFollowUpUpdate,
) -> LeadRead:
    lead = _get_lead_entity(db, tenant_id, lead_id)
    lead.next_followup_at = data.next_followup_at

    if lead.stage == LeadStage.NEW:
        lead.stage = LeadStage.FOLLOW_UP

    db.add(
        LeadActivity(
            tenant_id=lead.tenant_id,
            brand_id=lead.brand_id,
            lead_id=lead.id,
            activity_type=LeadActivityType.FOLLOW_UP,
            note=data.note or f"Follow-up scheduled for {data.next_followup_at.isoformat()}",
            created_by=user_id,
        )
    )
    db.commit()
    db.refresh(lead)
    return _lead_to_read(lead)


def create_segment(
    db: Session,
    tenant_id: int,
    data: SegmentCreate,
    default_brand_id: int | None = None,
) -> SegmentRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    segment = Segment(
        tenant_id=tenant_id,
        brand_id=brand_id,
        segment_name=data.segment_name,
        description=data.description,
        filter_json=json.dumps(data.filter_json),
        estimated_count=0,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return _segment_to_read(segment)


def list_segments(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    brand_id: int | None = None,
) -> tuple[list[SegmentRead], int]:
    query = db.query(Segment).filter(Segment.tenant_id == tenant_id, Segment.is_active.is_(True))

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Segment.brand_id.is_(None), Segment.brand_id == brand_id))

    query = query.order_by(Segment.segment_name)
    segments, total = paginate_query(query, page, page_size)
    return [_segment_to_read(segment) for segment in segments], total


def update_segment(
    db: Session,
    tenant_id: int,
    segment_id: int,
    data: SegmentUpdate,
) -> SegmentRead:
    segment = _get_segment_entity(db, tenant_id, segment_id)
    payload = data.model_dump(exclude_unset=True)
    if "filter_json" in payload and payload["filter_json"] is not None:
        segment.filter_json = json.dumps(payload.pop("filter_json"))
    for key, value in payload.items():
        setattr(segment, key, value)
    db.commit()
    db.refresh(segment)
    return _segment_to_read(segment)


def delete_segment(db: Session, tenant_id: int, segment_id: int) -> SegmentRead:
    segment = _get_segment_entity(db, tenant_id, segment_id)
    segment.is_active = False
    db.commit()
    return _segment_to_read(segment)


def estimate_segment_count(db: Session, tenant_id: int, segment_id: int) -> SegmentEstimateResponse:
    from app.modules.leads.segment_filters import count_segment_customers, count_segment_leads

    segment = _get_segment_entity(db, tenant_id, segment_id)
    lead_count = count_segment_leads(db, tenant_id, segment)
    customer_count = count_segment_customers(db, tenant_id, segment)
    count = lead_count + customer_count

    segment.estimated_count = count
    db.commit()

    return SegmentEstimateResponse(
        segment_id=segment.id,
        estimated_count=count,
        message=f"Estimated audience: {lead_count} leads and {customer_count} customers",
    )


def _lead_to_read(lead: Lead) -> LeadRead:
    payload = LeadRead.model_validate(lead)
    payload.tags = _deserialize_tags(lead.tags_json)
    return payload


def _segment_to_read(segment: Segment) -> SegmentRead:
    payload = SegmentRead.model_validate(segment)
    payload.filter_json = _parse_json(segment.filter_json)
    return payload


def _serialize_tags(tags: list[str]) -> str:
    normalized = [tag.strip() for tag in tags if tag.strip()]
    return json.dumps(normalized)


def _deserialize_tags(tags_json: str | None) -> list[str]:
    if not tags_json:
        return []
    try:
        parsed = json.loads(tags_json)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(tag) for tag in parsed]
    return []


def _parse_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _get_lead_entity(
    db: Session,
    tenant_id: int,
    lead_id: int,
    with_activities: bool = False,
) -> Lead:
    query = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id)
    if with_activities:
        query = query.options(joinedload(Lead.activities))
    lead = query.first()
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


def _get_segment_entity(db: Session, tenant_id: int, segment_id: int) -> Segment:
    segment = (
        db.query(Segment)
        .filter(Segment.id == segment_id, Segment.tenant_id == tenant_id)
        .first()
    )
    if segment is None:
        raise NotFoundError("Segment not found")
    return segment


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


def _get_customer(db: Session, tenant_id: int, customer_id: int) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        .first()
    )
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer


def _get_campaign(db: Session, tenant_id: int, campaign_id: int) -> Campaign:
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
        .first()
    )
    if campaign is None:
        raise NotFoundError("Campaign not found")
    return campaign


def _get_user(db: Session, tenant_id: int, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if user is None:
        raise NotFoundError("User not found")
    return user
