from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.response import MessageResponse
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.roles import service
from app.modules.roles.schemas import (
    PermissionRead,
    RoleCreate,
    RolePermissionAssign,
    RoleRead,
    RoleUpdate,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/permissions", response_model=list[PermissionRead])
def list_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.ROLES_READ)),
) -> list[PermissionRead]:
    return service.list_permissions(db)


@router.get("", response_model=list[RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ROLES_READ)),
) -> list[RoleRead]:
    return service.list_roles(db, current_user.tenant_id)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ROLES_WRITE)),
) -> RoleRead:
    return service.create_role(db, current_user.tenant_id, body)


@router.get("/{role_id}", response_model=RoleRead)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ROLES_READ)),
) -> RoleRead:
    return service.get_role(db, current_user.tenant_id, role_id)


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(
    role_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ROLES_WRITE)),
) -> RoleRead:
    return service.update_role(db, current_user.tenant_id, role_id, body)


@router.delete("/{role_id}", response_model=MessageResponse)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ROLES_WRITE)),
) -> MessageResponse:
    service.delete_role(db, current_user.tenant_id, role_id)
    return MessageResponse(message="Role deactivated")


@router.put("/{role_id}/permissions", response_model=RoleRead)
def assign_role_permissions(
    role_id: int,
    body: RolePermissionAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ROLES_WRITE)),
) -> RoleRead:
    return service.assign_permissions(db, current_user.tenant_id, role_id, body)
