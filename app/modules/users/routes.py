from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.common.response import MessageResponse
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserOutletAssign, UserRead, UserUpdate

router = APIRouter()


@router.get("", response_model=PaginatedSuccessResponse[UserRead])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_READ)),
) -> PaginatedSuccessResponse[UserRead]:
    items, total = service.list_users(db, current_user.tenant_id, page, page_size)
    return success_paginated(items, total, page, page_size)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_WRITE)),
) -> UserRead:
    return service.create_user(db, current_user.tenant_id, body)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_READ)),
) -> UserRead:
    return service.get_user(db, current_user.tenant_id, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_WRITE)),
) -> UserRead:
    return service.update_user(db, current_user.tenant_id, user_id, body, current_user.id)


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_WRITE)),
) -> MessageResponse:
    service.delete_user(db, current_user.tenant_id, user_id)
    return MessageResponse(message="User deactivated")


@router.put("/{user_id}/outlets", response_model=UserRead)
def assign_user_outlets(
    user_id: int,
    body: UserOutletAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_WRITE)),
) -> UserRead:
    return service.assign_outlets(db, current_user.tenant_id, user_id, body)
