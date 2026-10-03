"""Shared segment filter logic for leads, customers, and campaigns."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.modules.customers.models import Customer
from app.modules.leads.models import Lead, LeadStage, LeadStatus, Segment


def parse_filter_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def apply_lead_filters(query: Query, filters: dict) -> Query:
    outlet_id = filters.get("outlet_id")
    if outlet_id is not None:
        query = query.filter(or_(Lead.outlet_id == outlet_id, Lead.outlet_id.is_(None)))

    source = filters.get("source")
    if source is not None:
        query = query.filter(Lead.source == source)

    stage = filters.get("stage")
    if stage is not None:
        query = query.filter(Lead.stage == stage)

    status = filters.get("status")
    if status is not None:
        query = query.filter(Lead.status == status)

    min_score = filters.get("min_lead_score")
    if min_score is not None:
        query = query.filter(Lead.lead_score >= min_score)

    max_score = filters.get("max_lead_score")
    if max_score is not None:
        query = query.filter(Lead.lead_score <= max_score)

    assigned_to = filters.get("assigned_to")
    if assigned_to is not None:
        query = query.filter(Lead.assigned_to == assigned_to)

    campaign_id = filters.get("campaign_id")
    if campaign_id is not None:
        query = query.filter(Lead.campaign_id == campaign_id)

    date_from = filters.get("date_from")
    if date_from is not None:
        query = query.filter(Lead.created_at >= _parse_datetime(date_from))

    date_to = filters.get("date_to")
    if date_to is not None:
        query = query.filter(Lead.created_at <= _parse_datetime(date_to))

    tags = filters.get("tags")
    if tags:
        for tag in tags if isinstance(tags, list) else [tags]:
            query = query.filter(Lead.tags_json.ilike(f"%{tag}%"))

    return query


def apply_customer_filters(query: Query, filters: dict) -> Query:
    outlet_id = filters.get("outlet_id")
    if outlet_id is not None:
        query = query.filter(
            or_(Customer.favourite_outlet_id == outlet_id, Customer.favourite_outlet_id.is_(None))
        )

    min_visits = filters.get("min_visits")
    if min_visits is not None:
        query = query.filter(Customer.total_visits >= min_visits)

    min_spend = filters.get("min_total_spend")
    if min_spend is not None:
        query = query.filter(Customer.total_spend >= min_spend)

    customer_status = filters.get("customer_status")
    if customer_status is not None:
        query = query.filter(Customer.status == customer_status)

    return query


def count_segment_leads(db: Session, tenant_id: int, segment: Segment) -> int:
    filters = parse_filter_json(segment.filter_json)
    query = db.query(Lead).filter(Lead.tenant_id == tenant_id, Lead.is_active.is_(True))

    if segment.brand_id is not None:
        query = query.filter(or_(Lead.brand_id.is_(None), Lead.brand_id == segment.brand_id))

    query = apply_lead_filters(query, filters)
    return query.count()


def count_segment_customers(db: Session, tenant_id: int, segment: Segment) -> int:
    filters = parse_filter_json(segment.filter_json)
    query = db.query(Customer).filter(Customer.tenant_id == tenant_id, Customer.is_active.is_(True))

    if segment.brand_id is not None:
        query = query.filter(or_(Customer.brand_id.is_(None), Customer.brand_id == segment.brand_id))

    query = apply_customer_filters(query, filters)
    return query.count()


def resolve_segment_leads(
    db: Session,
    tenant_id: int,
    segment: Segment,
    limit: int = 500,
) -> list[Lead]:
    filters = parse_filter_json(segment.filter_json)
    query = db.query(Lead).filter(Lead.tenant_id == tenant_id, Lead.is_active.is_(True))

    if segment.brand_id is not None:
        query = query.filter(or_(Lead.brand_id.is_(None), Lead.brand_id == segment.brand_id))

    query = apply_lead_filters(query, filters)
    return query.limit(limit).all()


def resolve_segment_customers(
    db: Session,
    tenant_id: int,
    segment: Segment,
    limit: int = 500,
) -> list[Customer]:
    filters = parse_filter_json(segment.filter_json)
    query = db.query(Customer).filter(Customer.tenant_id == tenant_id, Customer.is_active.is_(True))

    if segment.brand_id is not None:
        query = query.filter(or_(Customer.brand_id.is_(None), Customer.brand_id == segment.brand_id))

    query = apply_customer_filters(query, filters)
    return query.limit(limit).all()


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
