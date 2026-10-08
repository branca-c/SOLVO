"""Safely reset runtime data in the configured SOLVO demo database.

Run from backend with ``python -m app.scripts.reset_demo --confirm``.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Assignment,
    Category,
    Reminder,
    Technician,
    WorkOrder,
    WorkOrderHistory,
    WorkOrderNote,
)
from app.scripts.seed_demo import seed_demo

RUNTIME_MODELS = (Assignment, Reminder, WorkOrderHistory, WorkOrderNote, WorkOrder)


def _count(db: Session, model: type[object]) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def reset_demo_data(db: Session, *, clear_telegram_bindings: bool = False) -> dict[str, int]:
    """Stage runtime cleanup and reference reseeding in the caller's transaction."""
    counts = {model.__tablename__: _count(db, model) for model in RUNTIME_MODELS}  # type: ignore[attr-defined]
    # Child rows are deleted explicitly in FK-safe order. Their FKs also use
    # ON DELETE CASCADE as a database backstop for ordinary ODL deletion.
    for model in RUNTIME_MODELS:
        db.execute(delete(model))
    cleared_bindings = 0
    if clear_telegram_bindings:
        result = db.execute(
            update(Technician)
            .where(Technician.telegram_chat_id.is_not(None))
            .values(telegram_chat_id=None)
        )
        cleared_bindings = int(result.rowcount or 0)
    seed_demo(db, commit=False)

    return {
        **counts,
        "categories": _count(db, Category),
        "technicians": _count(db, Technician),
        "telegram_bindings_cleared": cleared_bindings,
    }


def reset_demo(db: Session, *, clear_telegram_bindings: bool = False) -> dict[str, int]:
    """Remove runtime ODL data and restore missing demo reference data atomically."""
    try:
        counts = reset_demo_data(db, clear_telegram_bindings=clear_telegram_bindings)
        db.commit()
        return counts
    except Exception:
        db.rollback()
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset SOLVO demo runtime data.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="required explicit acknowledgement of this destructive operation",
    )
    parser.add_argument(
        "--clear-telegram-bindings",
        action="store_true",
        help="also clear technician Telegram bindings",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, *, session_factory: Callable[[], Session] = SessionLocal) -> None:
    args = parse_args(argv)
    if not args.confirm:
        raise SystemExit("Refused: pass --confirm to reset demo runtime data.")
    with session_factory() as db:
        counts = reset_demo(db, clear_telegram_bindings=args.clear_telegram_bindings)
    print(
        "Reset completato: "
        f"ODL={counts['work_orders']}, assegnazioni={counts['assignments']}, "
        f"solleciti={counts['reminders']}, storico={counts['work_order_history']}, "
        f"note={counts['work_order_notes']}; "
        f"categorie={counts['categories']}, tecnici={counts['technicians']}; "
        f"binding Telegram cancellati={counts['telegram_bindings_cleared']}."
    )


if __name__ == "__main__":
    main()
