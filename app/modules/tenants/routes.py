from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.tenants import service
from app.modules.tenants.schemas import TenantCreate, TenantRead, TenantUpdate
from app.modules.users.models import User

router = APIRouter()


@router.get("/me", response_model=TenantRead)
def get_my_tenant(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TENANTS_READ)),
) -> TenantRead:
    return service.get_tenant(db, current_user.tenant_id)


@router.get("", response_model=list[TenantRead])
def list_tenants(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.TENANTS_READ)),
) -> list[TenantRead]:
    return service.list_tenants(db)


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    body: TenantCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.TENANTS_WRITE)),
) -> TenantRead:
    return service.create_tenant(db, body)


@router.patch("/{tenant_id}", response_model=TenantRead)
def update_tenant(
    tenant_id: int,
    body: TenantUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.TENANTS_WRITE)),
) -> TenantRead:
    return service.update_tenant(db, tenant_id, body)
