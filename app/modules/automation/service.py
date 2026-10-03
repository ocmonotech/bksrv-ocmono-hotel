from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.automation.models import (
    AutomationActionType,
    AutomationRule,
    AutomationRuleStatus,
    AutomationRun,
    AutomationRunStatus,
    AutomationTriggerType,
)
from app.modules.automation.schemas import (
    AutomationRuleCreate,
    AutomationRuleRead,
    AutomationRuleUpdate,
    AutomationRunRead,
    MockRunRequest,
    MockRunResponse,
)
from app.modules.brands.models import Brand


def create_rule(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: AutomationRuleCreate,
    default_brand_id: int | None = None,
) -> AutomationRuleRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    rule = AutomationRule(
        tenant_id=tenant_id,
        brand_id=brand_id,
        rule_name=data.rule_name,
        trigger_type=data.trigger_type,
        conditions_json=json.dumps(data.conditions),
        actions_json=json.dumps(data.actions),
        timing_json=json.dumps(data.timing),
        status=data.status,
        created_by=user_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_to_read(rule)


def list_rules(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    trigger_type: AutomationTriggerType | None = None,
    status: AutomationRuleStatus | None = None,
    brand_id: int | None = None,
) -> tuple[list[AutomationRuleRead], int]:
    query = db.query(AutomationRule).filter(
        AutomationRule.tenant_id == tenant_id,
        AutomationRule.is_active.is_(True),
    )

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(AutomationRule.brand_id.is_(None), AutomationRule.brand_id == brand_id))

    if trigger_type is not None:
        query = query.filter(AutomationRule.trigger_type == trigger_type)

    if status is not None:
        query = query.filter(AutomationRule.status == status)

    query = query.order_by(AutomationRule.rule_name)
    rules, total = paginate_query(query, page, page_size)
    return [_rule_to_read(rule) for rule in rules], total


def update_rule(
    db: Session,
    tenant_id: int,
    rule_id: int,
    data: AutomationRuleUpdate,
) -> AutomationRuleRead:
    rule = _get_rule(db, tenant_id, rule_id)
    updates = data.model_dump(exclude_unset=True)

    if "conditions" in updates:
        rule.conditions_json = json.dumps(updates.pop("conditions"))
    if "actions" in updates:
        rule.actions_json = json.dumps(updates.pop("actions"))
    if "timing" in updates:
        rule.timing_json = json.dumps(updates.pop("timing"))

    for field, value in updates.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return _rule_to_read(rule)


def activate_rule(db: Session, tenant_id: int, rule_id: int) -> AutomationRuleRead:
    rule = _get_rule(db, tenant_id, rule_id)

    actions = _parse_json_list(rule.actions_json)
    if not actions:
        raise ConflictError("Rule must have at least one action before activation")

    rule.status = AutomationRuleStatus.ACTIVE
    db.commit()
    db.refresh(rule)
    return _rule_to_read(rule)


def deactivate_rule(db: Session, tenant_id: int, rule_id: int) -> AutomationRuleRead:
    rule = _get_rule(db, tenant_id, rule_id)
    rule.status = AutomationRuleStatus.INACTIVE
    db.commit()
    db.refresh(rule)
    return _rule_to_read(rule)


async def run_automation_mock(
    db: Session,
    tenant_id: int,
    rule_id: int,
    data: MockRunRequest,
) -> MockRunResponse:
    rule = _get_rule(db, tenant_id, rule_id)
    started_at = datetime.utcnow()

    run = AutomationRun(
        tenant_id=tenant_id,
        brand_id=rule.brand_id,
        rule_id=rule.id,
        trigger_payload_json=json.dumps({"input": data.trigger_payload}),
        status=AutomationRunStatus.RUNNING,
        started_at=started_at,
    )
    db.add(run)
    db.flush()

    mock_results: list[dict] = []
    actions = _parse_json_list(rule.actions_json)

    try:
        for action in actions:
            result = await _execute_mock_action(rule, action, data.trigger_payload)
            mock_results.append(result)

        payload = {
            "input": data.trigger_payload,
            "mock_results": mock_results,
        }
        run.trigger_payload_json = json.dumps(payload)
        run.status = AutomationRunStatus.COMPLETED
        run.completed_at = datetime.utcnow()
        run.error_message = None
        db.commit()
        db.refresh(run)

        return MockRunResponse(
            success=True,
            run=_run_to_read(run),
            message=f"Mock automation completed with {len(mock_results)} action(s)",
        )
    except Exception as exc:
        run.status = AutomationRunStatus.FAILED
        run.completed_at = datetime.utcnow()
        run.error_message = str(exc)
        run.trigger_payload_json = json.dumps(
            {
                "input": data.trigger_payload,
                "mock_results": mock_results,
            }
        )
        db.commit()
        db.refresh(run)

        return MockRunResponse(
            success=False,
            run=_run_to_read(run),
            message=f"Mock automation failed: {exc}",
        )


def list_runs(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    rule_id: int | None = None,
    status: AutomationRunStatus | None = None,
) -> tuple[list[AutomationRunRead], int]:
    query = db.query(AutomationRun).filter(AutomationRun.tenant_id == tenant_id)

    if rule_id is not None:
        _get_rule(db, tenant_id, rule_id)
        query = query.filter(AutomationRun.rule_id == rule_id)

    if status is not None:
        query = query.filter(AutomationRun.status == status)

    query = query.order_by(AutomationRun.started_at.desc().nullslast(), AutomationRun.id.desc())
    runs, total = paginate_query(query, page, page_size)
    return [_run_to_read(run) for run in runs], total


async def _execute_mock_action(
    rule: AutomationRule,
    action: dict,
    trigger_payload: dict,
) -> dict:
    action_type = action.get("type")
    if not action_type:
        raise ConflictError("Action missing type")

    try:
        parsed_type = AutomationActionType(action_type)
    except ValueError as exc:
        raise ConflictError(f"Unsupported action type: {action_type}") from exc

    mock_id = uuid.uuid4().hex[:12]
    base = {
        "action_type": parsed_type.value,
        "success": True,
        "mock": True,
        "reference_id": f"mock_{mock_id}",
    }

    if parsed_type == AutomationActionType.SEND_WHATSAPP_TEMPLATE:
        return {
            **base,
            "message": "Mock WhatsApp template queued",
            "template_id": action.get("template_id"),
            "recipient": trigger_payload.get("mobile", "unknown"),
        }
    if parsed_type == AutomationActionType.SEND_SMS:
        return {
            **base,
            "message": "Mock SMS queued",
            "recipient": trigger_payload.get("mobile", "unknown"),
        }
    if parsed_type == AutomationActionType.SEND_EMAIL:
        return {
            **base,
            "message": "Mock email queued",
            "recipient": trigger_payload.get("email", "unknown"),
        }
    if parsed_type == AutomationActionType.ASSIGN_USER:
        return {
            **base,
            "message": "Mock user assignment recorded",
            "user_id": action.get("user_id"),
        }
    if parsed_type == AutomationActionType.ADD_TAG:
        return {
            **base,
            "message": "Mock tag added",
            "tag": action.get("tag"),
        }
    if parsed_type == AutomationActionType.CHANGE_LEAD_STAGE:
        return {
            **base,
            "message": "Mock lead stage updated",
            "stage": action.get("stage"),
            "lead_id": trigger_payload.get("lead_id"),
        }
    if parsed_type == AutomationActionType.CREATE_FOLLOWUP_TASK:
        return {
            **base,
            "message": "Mock follow-up task created",
            "due_at": action.get("due_at"),
        }
    if parsed_type == AutomationActionType.NOTIFY_MANAGER:
        return {
            **base,
            "message": "Mock manager notification sent",
            "outlet_id": trigger_payload.get("outlet_id"),
        }
    if parsed_type == AutomationActionType.GENERATE_AI_REPLY_DRAFT:
        return {
            **base,
            "message": "Mock AI reply draft generated",
            "draft_preview": f"[Mock draft for trigger {rule.trigger_type.value}]",
        }

    return base


async def dispatch_trigger(
    db: Session,
    tenant_id: int,
    trigger_type: AutomationTriggerType,
    payload: dict,
) -> None:
    """Run all active automation rules matching the trigger (best-effort)."""
    rules = (
        db.query(AutomationRule)
        .filter(
            AutomationRule.tenant_id == tenant_id,
            AutomationRule.is_active.is_(True),
            AutomationRule.status == AutomationRuleStatus.ACTIVE,
            AutomationRule.trigger_type == trigger_type,
        )
        .all()
    )
    for rule in rules:
        try:
            await run_automation_mock(
                db,
                tenant_id,
                rule.id,
                MockRunRequest(trigger_payload=payload),
            )
        except Exception:
            continue


def _rule_to_read(rule: AutomationRule) -> AutomationRuleRead:
    payload = AutomationRuleRead.model_validate(rule)
    payload.conditions = _parse_json(rule.conditions_json)
    payload.actions = _parse_json_list(rule.actions_json)
    payload.timing = _parse_json(rule.timing_json)
    return payload


def _run_to_read(run: AutomationRun) -> AutomationRunRead:
    payload_dict = _parse_json(run.trigger_payload_json)
    input_payload = payload_dict.get("input", payload_dict)
    mock_results = payload_dict.get("mock_results", [])

    payload = AutomationRunRead.model_validate(run)
    payload.trigger_payload = input_payload if isinstance(input_payload, dict) else {}
    payload.mock_results = mock_results if isinstance(mock_results, list) else []
    return payload


def _get_rule(db: Session, tenant_id: int, rule_id: int) -> AutomationRule:
    rule = (
        db.query(AutomationRule)
        .filter(AutomationRule.id == rule_id, AutomationRule.tenant_id == tenant_id)
        .first()
    )
    if rule is None:
        raise NotFoundError("Automation rule not found")
    return rule


def _validate_brand(db: Session, tenant_id: int, brand_id: int | None) -> None:
    if brand_id is None:
        return
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if brand is None:
        raise NotFoundError("Brand not found")


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
