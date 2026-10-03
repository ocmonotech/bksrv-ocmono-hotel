from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.modules.communications.models import MessageChannel, MessageStatus, ProviderName


@dataclass
class ProviderSendResult:
    success: bool
    provider_message_id: str
    status: MessageStatus
    error_message: str | None = None


class BaseCommunicationProvider(ABC):
    provider_name: ProviderName
    channel: MessageChannel

    @abstractmethod
    async def send(
        self,
        *,
        sender: str,
        receiver: str,
        message_text: str,
        subject: str | None = None,
        config: dict | None = None,
    ) -> ProviderSendResult:
        raise NotImplementedError
