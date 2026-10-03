from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.settings import service
from app.modules.settings.schemas import (
    AiSettingsRead,
    AiSettingsUpdate,
    BrandSettingsRead,
    CommunicationSettingsRead,
    CommunicationSettingsUpdate,
    OrganizationSettingsRead,
    OrganizationSettingsUpdate,
    OutletSettingsRead,
    PmsTaxSettingsRead,
    PmsTaxSettingsUpdate,
    ReminderSettingsRead,
    ReminderSettingsUpdate,
    SettingValueUpdate,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/brands/{brand_id}", response_model=BrandSettingsRead)
def get_brand_settings(
    brand_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_READ)),
) -> BrandSettingsRead:
    return service.get_brand_settings(db, current_user.tenant_id, brand_id)


@router.patch("/brands/{brand_id}", response_model=BrandSettingsRead)
def update_brand_setting(
    brand_id: int,
    body: SettingValueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_WRITE)),
) -> BrandSettingsRead:
    return service.update_brand_setting(db, current_user.tenant_id, brand_id, body)


@router.get("/outlets/{outlet_id}", response_model=OutletSettingsRead)
def get_outlet_settings(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_READ)),
) -> OutletSettingsRead:
    return service.get_outlet_settings(db, current_user.tenant_id, outlet_id)


@router.patch("/outlets/{outlet_id}", response_model=OutletSettingsRead)
def update_outlet_setting(
    outlet_id: int,
    body: SettingValueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_WRITE)),
) -> OutletSettingsRead:
    return service.update_outlet_setting(db, current_user.tenant_id, outlet_id, body)


@router.get("/communication", response_model=CommunicationSettingsRead)
def get_communication_settings(
    brand_id: int | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_READ)),
) -> CommunicationSettingsRead:
    return service.get_communication_settings(
        db,
        current_user.tenant_id,
        brand_id=brand_id,
        outlet_id=outlet_id,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/communication", response_model=CommunicationSettingsRead)
def update_communication_settings(
    body: CommunicationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_WRITE)),
) -> CommunicationSettingsRead:
    return service.update_communication_settings(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/ai", response_model=AiSettingsRead)
def get_ai_settings(
    brand_id: int | None = Query(None),
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_READ)),
) -> AiSettingsRead:
    return service.get_ai_settings(
        db,
        current_user.tenant_id,
        brand_id=brand_id,
        outlet_id=outlet_id,
        default_brand_id=current_user.brand_id,
    )


@router.patch("/ai", response_model=AiSettingsRead)
def update_ai_settings(
    body: AiSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_WRITE)),
) -> AiSettingsRead:
    return service.update_ai_settings(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/reminders", response_model=ReminderSettingsRead)
def get_reminder_settings(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_READ)),
) -> ReminderSettingsRead:
    return service.get_reminder_settings(db, current_user.tenant_id, outlet_id)


@router.patch("/reminders", response_model=ReminderSettingsRead)
def update_reminder_settings(
    body: ReminderSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_WRITE)),
) -> ReminderSettingsRead:
    return service.update_reminder_settings(db, current_user.tenant_id, body)


@router.get("/pms-tax", response_model=PmsTaxSettingsRead)
def get_pms_tax_settings(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_READ)),
) -> PmsTaxSettingsRead:
    return service.get_pms_tax_settings(db, current_user.tenant_id, outlet_id)


@router.patch("/pms-tax", response_model=PmsTaxSettingsRead)
def update_pms_tax_settings(
    body: PmsTaxSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_WRITE)),
) -> PmsTaxSettingsRead:
    return service.update_pms_tax_settings(db, current_user.tenant_id, body)


@router.get("/organization", response_model=OrganizationSettingsRead)
def get_organization_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_READ)),
) -> OrganizationSettingsRead:
    return service.get_organization_settings(db, current_user.tenant_id)


@router.patch("/organization", response_model=OrganizationSettingsRead)
def update_organization_settings(
    body: OrganizationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.SETTINGS_WRITE)),
) -> OrganizationSettingsRead:
    return service.update_organization_settings(db, current_user.tenant_id, body)
