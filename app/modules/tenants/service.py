from __future__ import annotations

from sqlalchemy.orm import Session

from app.common.base_model import RecordStatus, apply_record_status
from app.core.exceptions import NotFoundError
from app.modules.tenants.models import Tenant
from app.modules.tenants.schemas import TenantCreate, TenantRead, TenantUpdate


def seed_demo_tenant(db: Session) -> None:
    from app.seed import run_seed

    run_seed(db)


def list_tenants(db: Session) -> list[TenantRead]:
    tenants = db.query(Tenant).order_by(Tenant.company_name).all()
    return [_to_tenant_read(t) for t in tenants]


def get_tenant(db: Session, tenant_id: int) -> TenantRead:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    return _to_tenant_read(tenant)


def create_tenant(db: Session, data: TenantCreate) -> TenantRead:
    tenant = Tenant(
        **data.model_dump(),
        status=RecordStatus.TRIAL,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return _to_tenant_read(tenant)


def update_tenant(db: Session, tenant_id: int, data: TenantUpdate) -> TenantRead:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")

    payload = data.model_dump(exclude_unset=True)
    status = payload.pop("status", None)
    for key, value in payload.items():
        setattr(tenant, key, value)
    if status is not None:
        apply_record_status(tenant, status)

    db.commit()
    db.refresh(tenant)
    return _to_tenant_read(tenant)


def _to_tenant_read(tenant: Tenant) -> TenantRead:
    return TenantRead.model_validate(tenant)
