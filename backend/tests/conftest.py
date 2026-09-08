import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://solvo:solvo-test-only@localhost:5432/solvo_test",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Category, User, UserRole


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Category(id=1, name="Elettrico"), Category(id=2, name="Idraulico")])
        db.add(User(
            id=1, first_name="Ada", last_name="Rossi", phone="12345", role=UserRole.UTENTE
        ))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()

