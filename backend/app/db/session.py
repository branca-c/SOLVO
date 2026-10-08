from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.demo_access import (
    DEMO_SESSION_GENERATION_INFO,
    demo_session_generation,
    demo_session_write_fence,
)

settings = get_settings()
engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def prepare_request_session(session: Session) -> None:
    generation = demo_session_generation.get()
    if generation is None:
        return
    session.info[DEMO_SESSION_GENERATION_INFO] = generation
    if demo_session_write_fence.get():
        # Imported lazily to avoid a module cycle through reset_demo.
        from app.services import demo_sessions

        demo_sessions.require_generation(
            session, generation, get_settings(), lock=True
        )


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        prepare_request_session(session)
        yield session
