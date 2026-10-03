from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin


class User(Base, BaseMixin):
    __tablename__ = "users"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    brand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[Optional[int]] = mapped_column(ForeignKey("roles.id"), nullable=True, index=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    role: Mapped["Role | None"] = relationship(back_populates="users")
    user_outlets: Mapped[list["UserOutlet"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def primary_outlet_id(self) -> int | None:
        return self.user_outlets[0].outlet_id if self.user_outlets else None


class UserOutlet(Base):
    __tablename__ = "user_outlets"
    __table_args__ = (UniqueConstraint("user_id", "outlet_id", name="uq_user_outlet"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id", ondelete="CASCADE"), index=True)

    user: Mapped["User"] = relationship(back_populates="user_outlets")
    outlet: Mapped["Outlet"] = relationship()
