import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["AUTO_SEED_ON_STARTUP"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.modules  # noqa: F401 — register models
from app.common.base_model import Base
from app.core.database import get_db
from app.main import app
from app.modules.users.models import User
from app.seed import run_seed

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        run_seed(session)
        admin = session.query(User).filter(User.email == "admin@restrochain.test").first()
        if admin is not None:
            admin.email = "admin@example.com"
            session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
