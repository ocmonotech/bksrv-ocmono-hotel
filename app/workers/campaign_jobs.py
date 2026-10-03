import logging

from app.workers.celery_app import celery_app
from app.workers.utils import task_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name="campaigns.send_campaign_messages_mock", bind=True)
def send_campaign_messages_mock(self, campaign_id: int, tenant_id: int) -> dict:
    """
    Mock campaign send job — no external messaging APIs.

    Loads campaign metadata and returns a simulated send summary.
    """
    from app.modules.campaigns.models import Campaign, CampaignStatus, RecipientStatus

    with task_db_session() as db:
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
            .first()
        )
        if campaign is None:
            return {
                "ok": False,
                "mock": True,
                "task_id": self.request.id,
                "campaign_id": campaign_id,
                "tenant_id": tenant_id,
                "message": "Campaign not found",
            }

        pending_count = sum(
            1 for recipient in campaign.recipients if recipient.status == RecipientStatus.PENDING
        )
        simulated_sent = pending_count or len(campaign.recipients)

        logger.info(
            "Mock campaign send job %s for campaign_id=%s tenant_id=%s recipients=%s",
            self.request.id,
            campaign_id,
            tenant_id,
            simulated_sent,
        )

        return {
            "ok": True,
            "mock": True,
            "task_id": self.request.id,
            "campaign_id": campaign_id,
            "tenant_id": tenant_id,
            "campaign_name": campaign.campaign_name,
            "channel": campaign.channel.value,
            "status": campaign.status.value if isinstance(campaign.status, CampaignStatus) else str(campaign.status),
            "recipients_simulated": simulated_sent,
            "message": "Mock campaign messages queued (no external API calls)",
        }
