from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.common.response import ORMSchema, TimestampSchema
from app.modules.automation.models import (
    AutomationActionType,
    AutomationRuleStatus,
    AutomationRunStatus,
    AutomationTriggerType,
)

SUPPORTED_TRIGGERS = {item.value for item in AutomationTriggerType}
SUPPORTED_ACTIONS = {item.value for item in AutomationActionType}


class AutomationRuleCreate(BaseModel):
    rule_name: str = Field(min_length=1, max_length=255)
    trigger_type: AutomationTriggerType
    conditions: dict = Field(default_factory=dict)
    actions: list[dict] = Field(default_factory=list)
    timing: dict = Field(default_factory=dict)
    status: AutomationRuleStatus = AutomationRuleStatus.DRAFT
    brand_id: int | None = None

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, actions: list[dict]) -> list[dict]:
        for action in actions:
            action_type = action.get("type")
            if action_type and action_type not in SUPPORTED_ACTIONS:
                raise ValueError(f"Unsupported action type: {action_type}")
        return actions


class AutomationRuleUpdate(BaseModel):
    rule_name: str | None = Field(default=None, min_length=1, max_length=255)
    trigger_type: AutomationTriggerType | None = None
    conditions: dict | None = None
    actions: list[dict] | None = None
    timing: dict | None = None
    status: AutomationRuleStatus | None = None

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, actions: list[dict] | None) -> list[dict] | None:
        if actions is None:
            return actions
        for action in actions:
            action_type = action.get("type")
            if action_type and action_type not in SUPPORTED_ACTIONS:
                raise ValueError(f"Unsupported action type: {action_type}")
        return actions


class AutomationRuleRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    rule_name: str
    trigger_type: AutomationTriggerType
    conditions: dict = {}
    actions: list[dict] = []
    timing: dict = {}
    status: AutomationRuleStatus
    created_by: int
    is_active: bool


class AutomationRunRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    rule_id: int
    trigger_payload: dict = {}
    status: AutomationRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    mock_results: list[dict] = []


class MockRunRequest(BaseModel):
    trigger_payload: dict = Field(default_factory=dict)


class MockRunResponse(BaseModel):
    success: bool
    run: AutomationRunRead
    message: str
    mock: bool = True
