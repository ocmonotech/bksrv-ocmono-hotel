"""CRM: customers, tags, visits, feedback, leads, activities, segments."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.customers.models import (
    Customer,
    CustomerSource,
    CustomerStatus,
    CustomerTag,
    CustomerTagMap,
    CustomerVisit,
    Feedback,
    FeedbackSentiment,
    FeedbackSource,
)
from app.modules.leads.models import Lead, LeadActivity, LeadActivityType, LeadStatus, Segment
from app.seeds.base import SeedContext
from app.seeds.constants import CUSTOMER_TAGS, LEAD_SEGMENTS, SAMPLE_CUSTOMERS, SAMPLE_LEADS, SUPER_ADMIN_EMAIL


def seed_crm(db: Session, ctx: SeedContext) -> None:
    ctx.customers = _seed_customers(db, ctx)
    _seed_customer_tags(db, ctx)
    ctx.leads = _seed_leads(db, ctx)
    _seed_lead_activities(db, ctx)
    _seed_segments(db, ctx)
    _seed_feedback(db, ctx)


def seed_customer_visits(db: Session, ctx: SeedContext) -> None:
    """Run after POS bills are seeded."""
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    bill = ctx.bills.get("BILL-AND-001")
    customer = ctx.customers.get("+919800000001")
    if bill is None or customer is None:
        return

    existing = (
        db.query(CustomerVisit)
        .filter(
            CustomerVisit.tenant_id == tenant.id,
            CustomerVisit.customer_id == customer.id,
            CustomerVisit.bill_id == bill.id,
        )
        .first()
    )
    if existing is not None:
        return

    db.add(
        CustomerVisit(
            tenant_id=tenant.id,
            brand_id=brand.id,
            outlet_id=andheri.id,
            customer_id=customer.id,
            bill_id=bill.id,
            visit_date=datetime.utcnow() - timedelta(hours=2),
            total_amount=float(bill.grand_total),
        )
    )
    customer.total_visits = max(customer.total_visits, 3)
    customer.total_spend = max(float(customer.total_spend), float(bill.grand_total) * 3)
    customer.last_visit_at = datetime.utcnow() - timedelta(hours=2)


def _seed_customers(db: Session, ctx: SeedContext) -> dict[str, Customer]:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    customers: dict[str, Customer] = {}

    for index, (name, mobile, email, wa, sms, email_consent) in enumerate(SAMPLE_CUSTOMERS):
        customer = (
            db.query(Customer)
            .filter(Customer.tenant_id == tenant.id, Customer.mobile == mobile)
            .first()
        )
        if customer is None:
            customer = Customer(
                tenant_id=tenant.id,
                brand_id=brand.id,
                full_name=name,
                mobile=mobile,
                email=email,
                source=CustomerSource.WALK_IN,
                consent_whatsapp=wa,
                consent_sms=sms,
                consent_email=email_consent,
                total_visits=index + 1,
                total_spend=(index + 1) * 850,
                loyalty_points=(index + 1) * 20,
                favourite_outlet_id=andheri.id,
                status=CustomerStatus.ACTIVE,
            )
            db.add(customer)
            db.flush()
        customers[mobile] = customer
    return customers


def _seed_customer_tags(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    tag_objects: dict[str, CustomerTag] = {}

    for tag_name in CUSTOMER_TAGS:
        tag = (
            db.query(CustomerTag)
            .filter(CustomerTag.tenant_id == tenant.id, CustomerTag.name == tag_name)
            .first()
        )
        if tag is None:
            tag = CustomerTag(tenant_id=tenant.id, brand_id=brand.id, name=tag_name)
            db.add(tag)
            db.flush()
        tag_objects[tag_name] = tag

    assignments = [
        ("+919800000001", "VIP"),
        ("+919800000001", "High Spender"),
        ("+919800000002", "Regular"),
        ("+919800000004", "Birthday Club"),
        ("+919800000003", "Corporate"),
    ]
    for mobile, tag_name in assignments:
        customer = ctx.customers.get(mobile)
        tag = tag_objects.get(tag_name)
        if customer is None or tag is None:
            continue
        existing = (
            db.query(CustomerTagMap)
            .filter(CustomerTagMap.customer_id == customer.id, CustomerTagMap.tag_id == tag.id)
            .first()
        )
        if existing is None:
            db.add(CustomerTagMap(customer_id=customer.id, tag_id=tag.id))


def _seed_leads(db: Session, ctx: SeedContext) -> dict[str, Lead]:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    leads: dict[str, Lead] = {}

    for name, mobile, email, source, stage, score in SAMPLE_LEADS:
        lead = (
            db.query(Lead)
            .filter(Lead.tenant_id == tenant.id, Lead.mobile == mobile)
            .first()
        )
        if lead is None:
            lead = Lead(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                lead_name=name,
                mobile=mobile,
                email=email,
                source=source,
                lead_score=score,
                stage=stage,
                status=LeadStatus.OPEN,
                last_message=f"Interested in dining at {andheri.outlet_name}",
                tags_json=json.dumps(["demo", source.value]),
            )
            db.add(lead)
            db.flush()
        leads[mobile] = lead
    return leads


def _seed_lead_activities(db: Session, ctx: SeedContext) -> None:
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    if admin is None:
        return

    activity_specs = [
        ("+919810000001", LeadActivityType.NOTE, "Initial WhatsApp inquiry about party booking"),
        ("+919810000002", LeadActivityType.WHATSAPP, "Sent menu PDF via WhatsApp"),
        ("+919810000003", LeadActivityType.FOLLOW_UP, "Scheduled follow-up call for tomorrow"),
        ("+919810000004", LeadActivityType.STAGE_CHANGE, "Moved to table booked after confirmation"),
    ]

    for mobile, activity_type, note in activity_specs:
        lead = ctx.leads.get(mobile)
        if lead is None:
            continue
        existing = (
            db.query(LeadActivity)
            .filter(
                LeadActivity.tenant_id == ctx.tenant.id,
                LeadActivity.lead_id == lead.id,
                LeadActivity.note == note,
            )
            .first()
        )
        if existing is not None:
            continue
        db.add(
            LeadActivity(
                tenant_id=ctx.tenant.id,
                brand_id=ctx.brand.id,
                lead_id=lead.id,
                activity_type=activity_type,
                note=note,
                created_by=admin.id,
            )
        )


def _seed_segments(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    for segment_name, description, filter_json, count in LEAD_SEGMENTS:
        segment = (
            db.query(Segment)
            .filter(Segment.tenant_id == tenant.id, Segment.segment_name == segment_name)
            .first()
        )
        if segment is None:
            db.add(
                Segment(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    segment_name=segment_name,
                    description=description,
                    filter_json=filter_json,
                    estimated_count=count,
                )
            )


def _seed_feedback(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]

    feedback_specs = [
        ("+919800000001", 5, "Amazing butter chicken!", FeedbackSentiment.POSITIVE, FeedbackSource.POS),
        ("+919800000002", 4, "Good food, slightly slow service", FeedbackSentiment.NEUTRAL, FeedbackSource.WHATSAPP),
        ("+919800000003", 2, "Order was delayed", FeedbackSentiment.NEGATIVE, FeedbackSource.WEB),
    ]

    for mobile, rating, message, sentiment, source in feedback_specs:
        customer = ctx.customers.get(mobile)
        if customer is None:
            continue
        existing = (
            db.query(Feedback)
            .filter(
                Feedback.tenant_id == tenant.id,
                Feedback.customer_id == customer.id,
                Feedback.message == message,
            )
            .first()
        )
        if existing is not None:
            continue
        db.add(
            Feedback(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                customer_id=customer.id,
                rating=rating,
                message=message,
                sentiment=sentiment,
                source=source,
            )
        )
