from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError
from app.core.permissions import Permission, user_has_permission
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User


def require_permission(permission: Permission) -> Callable:
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not user_has_permission(db, current_user, permission):
            raise ForbiddenError(f"Missing permission: {permission.value}")
        return current_user

    return dependency
