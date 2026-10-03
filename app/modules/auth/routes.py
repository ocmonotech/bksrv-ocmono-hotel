from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MeResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.modules.users.models import User

router = APIRouter()


@router.post("/login", response_model=LoginResponse, summary="Login with email and password")
def login(credentials: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    return service.login(db, credentials)


@router.get("/me", response_model=MeResponse, summary="Get current authenticated user")
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    return service.get_me(db, current_user)


@router.post("/refresh-token", response_model=RefreshTokenResponse, summary="Refresh access token")
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)) -> RefreshTokenResponse:
    return service.refresh_access_token(db, body.refresh_token)


@router.post("/logout", response_model=LogoutResponse, summary="Logout and revoke token")
def logout(
    authorization: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    return service.logout(db, current_user, token)
