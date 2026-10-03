"""Communications providers, templates, conversations, and messages."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.communications.models import (
    CommunicationProvider,
    Conversation,
    ConversationStatus,
    Message,
    MessageChannel,
    MessageDirection,
    MessageStatus,
    MessageTemplate,
    MessageType,
    ProviderName,
    ProviderStatus,
    TemplateStatus,
)
from app.seeds.base import SeedContext
from app.seeds.constants import MESSAGE_TEMPLATES, SUPER_ADMIN_EMAIL


def seed_comms(db: Session, ctx: SeedContext) -> None:
    _seed_communication_providers(db, ctx)
    ctx.templates = _seed_message_templates(db, ctx)
    _seed_conversations(db, ctx)


def _seed_communication_providers(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    specs = [
        (MessageChannel.WHATSAPP, ProviderName.MOCK, ProviderStatus.ACTIVE),
        (MessageChannel.SMS, ProviderName.MOCK, ProviderStatus.ACTIVE),
        (MessageChannel.EMAIL, ProviderName.MOCK, ProviderStatus.ACTIVE),
    ]
    for channel, provider_name, status in specs:
        provider = (
            db.query(CommunicationProvider)
            .filter(
                CommunicationProvider.tenant_id == tenant.id,
                CommunicationProvider.brand_id == brand.id,
                CommunicationProvider.channel == channel,
                CommunicationProvider.provider_name == provider_name,
            )
            .first()
        )
        if provider is None:
            db.add(
                CommunicationProvider(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    channel=channel,
                    provider_name=provider_name,
                    status=status,
                    config_json=json.dumps({"mode": "mock", "enabled": True}),
                    encrypted_api_key="MOCK_ENC:demo-comms-key",
                    api_key_last4="demo",
                    is_default=True,
                )
            )


def _seed_message_templates(db: Session, ctx: SeedContext) -> dict[str, MessageTemplate]:
    tenant, brand = ctx.tenant, ctx.brand
    templates: dict[str, MessageTemplate] = {}

    for channel, template_name, category, body, variables in MESSAGE_TEMPLATES:
        template = (
            db.query(MessageTemplate)
            .filter(
                MessageTemplate.tenant_id == tenant.id,
                MessageTemplate.brand_id == brand.id,
                MessageTemplate.channel == channel,
                MessageTemplate.template_name == template_name,
            )
            .first()
        )
        if template is None:
            template = MessageTemplate(
                tenant_id=tenant.id,
                brand_id=brand.id,
                channel=channel,
                template_name=template_name,
                category=category,
                language="English",
                body=body,
                variables_json=json.dumps(variables),
                provider_template_id=f"mock_{template_name}",
                status=TemplateStatus.APPROVED,
            )
            db.add(template)
            db.flush()
        templates[template_name] = template
    return templates


def _seed_conversations(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    marketing = ctx.users.get("marketing@restrochain.test")

    conv_specs = [
        {
            "key": "wa-aarav",
            "customer_mobile": "+919800000001",
            "lead_mobile": None,
            "channel": MessageChannel.WHATSAPP,
            "status": ConversationStatus.OPEN,
            "last_message": "Can I book a table for 4 this Saturday?",
            "messages": [
                (MessageDirection.INBOUND, "+919800000001", "restaurant", "Hi, I want to book a table for 4"),
                (MessageDirection.OUTBOUND, "restaurant", "+919800000001", "Sure! Which date works for you?"),
                (MessageDirection.INBOUND, "+919800000001", "restaurant", "Can I book a table for 4 this Saturday?"),
            ],
        },
        {
            "key": "wa-lead-ananya",
            "customer_mobile": None,
            "lead_mobile": "+919810000001",
            "channel": MessageChannel.WHATSAPP,
            "status": ConversationStatus.PENDING,
            "last_message": "Looking for birthday party packages",
            "messages": [
                (MessageDirection.INBOUND, "+919810000001", "restaurant", "Looking for birthday party packages"),
            ],
        },
        {
            "key": "sms-rahul",
            "customer_mobile": "+919800000003",
            "lead_mobile": None,
            "channel": MessageChannel.SMS,
            "status": ConversationStatus.CLOSED,
            "last_message": "Thank you for the feedback!",
            "messages": [
                (MessageDirection.INBOUND, "+919800000003", "restaurant", "Food was great but delivery was late."),
                (MessageDirection.OUTBOUND, "restaurant", "+919800000003", "Thank you for the feedback!"),
            ],
        },
        {
            "key": "wa-vikram",
            "customer_mobile": "+919800000005",
            "lead_mobile": None,
            "channel": MessageChannel.WHATSAPP,
            "status": ConversationStatus.OPEN,
            "last_message": "Can I get the menu for tonight?",
            "messages": [
                (MessageDirection.INBOUND, "+919800000005", "restaurant", "Can I get the menu for tonight?"),
                (MessageDirection.OUTBOUND, "restaurant", "+919800000005", "Sure! Here is our dinner menu link: menu.bombaybiteco.in"),
                (MessageDirection.INBOUND, "+919800000005", "restaurant", "Thanks! Do you have any veg specials today?"),
            ],
        },
        {
            "key": "wa-lead-karan",
            "customer_mobile": None,
            "lead_mobile": "+919810000002",
            "channel": MessageChannel.WHATSAPP,
            "status": ConversationStatus.PENDING,
            "last_message": "Interested in group dining packages",
            "messages": [
                (MessageDirection.INBOUND, "+919810000002", "restaurant", "Interested in group dining packages"),
                (MessageDirection.OUTBOUND, "restaurant", "+919810000002", "We'd love to help! How many guests are you expecting?"),
            ],
        },
    ]

    for spec in conv_specs:
        customer = ctx.customers.get(spec["customer_mobile"]) if spec["customer_mobile"] else None
        lead = ctx.leads.get(spec["lead_mobile"]) if spec["lead_mobile"] else None
        thread_id = f"demo-thread-{spec['key']}"

        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.tenant_id == tenant.id,
                Conversation.external_thread_id == thread_id,
            )
            .first()
        )
        if conversation is None:
            conversation = Conversation(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                customer_id=customer.id if customer else None,
                lead_id=lead.id if lead else None,
                channel=spec["channel"],
                external_thread_id=thread_id,
                status=spec["status"],
                assigned_to=marketing.id if marketing else None,
                last_message=spec["last_message"],
                last_message_at=datetime.utcnow() - timedelta(minutes=15),
                unread_count=1,
            )
            db.add(conversation)
            db.flush()

            for index, (direction, sender, receiver, text) in enumerate(spec["messages"]):
                db.add(
                    Message(
                        tenant_id=tenant.id,
                        brand_id=brand.id,
                        outlet_id=andheri.id,
                        conversation_id=conversation.id,
                        channel=spec["channel"],
                        direction=direction,
                        sender=sender,
                        receiver=receiver,
                        message_text=text,
                        message_type=MessageType.TEXT,
                        provider_message_id=f"demo-msg-{spec['key']}-{index}",
                        status=MessageStatus.DELIVERED,
                        sent_by=marketing.id if direction == MessageDirection.OUTBOUND and marketing else None,
                    )
                )
