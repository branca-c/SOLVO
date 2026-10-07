"""Start an isolated, seeded backend exclusively for local browser E2E tests."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    if os.environ.get("APP_ENV") != "test":
        raise SystemExit("The E2E server requires APP_ENV=test.")
    database_url = os.environ.get("DATABASE_URL", "")
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise SystemExit("The E2E server requires an isolated SQLite DATABASE_URL.")
    database_path = Path(database_url.removeprefix(prefix)).resolve()
    if database_path.parent != Path("/tmp"):
        raise SystemExit("The E2E database must be located directly under /tmp.")
    database_path.unlink(missing_ok=True)

    import uvicorn

    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.scripts.seed_demo import seed_demo

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="warning")


if __name__ == "__main__":
    main()
