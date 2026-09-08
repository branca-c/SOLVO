"""Run from backend: python -m app.scripts.seed_demo (local/demo only)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Category, Technician, User, UserRole

DEMO_CATEGORIES = (
    "Vetri", "Climatizzazione", "Riscaldamento", "Ascensore", "Rete", "Elettrico",
    "Edile", "Idraulico", "Serramenti", "Antincendio", "Sicurezza", "Arredi", "Altro",
)
DEMO_USER_EMAIL = "richiedente@solvo-demo.example"


def seed_demo(db: Session) -> int:
    """Insert missing demo rows atomically; refuse conflicting routing configuration."""
    try:
        for index, name in enumerate(DEMO_CATEGORIES):
            category = db.scalar(select(Category).where(Category.name == name))
            if category is None:
                category = Category(name=name)
                db.add(category)
                db.flush()
            for order in range(1, 5):
                email = f"{name.lower()}.{order}@solvo-demo.example"
                technician = db.scalar(select(Technician).where(Technician.email == email))
                if technician is not None:
                    if (technician.category_id, technician.escalation_order, technician.is_team_leader) != (category.id, order, order == 4):
                        raise ValueError(f"Configurazione demo modificata: {name}, posizione {order}")
                    continue
                occupied = db.scalar(select(Technician).where(
                    Technician.category_id == category.id, Technician.escalation_order == order
                ))
                if occupied is not None:
                    raise ValueError(f"Posizione già configurata: {name}, {order}; nessun dato sovrascritto")
                db.add(Technician(
                    first_name=f"Demo {order}", last_name=name,
                    phone=f"+120255501{index * 4 + order:02d}", email=email,
                    category_id=category.id, escalation_order=order, is_team_leader=order == 4,
                ))
                db.flush()
        user = db.scalar(select(User).where(User.email == DEMO_USER_EMAIL))
        if user is None:
            user = User(first_name="Richiedente", last_name="Demo", phone="+12025550199",
                        email=DEMO_USER_EMAIL, role=UserRole.UTENTE)
            db.add(user)
            db.flush()
        user_id = user.id
        db.commit()
        return user_id
    except Exception:
        db.rollback()
        raise


def main() -> None:
    with SessionLocal() as db:
        user_id = seed_demo(db)
    print(f"Demo pronta: 13 categorie, 52 tecnici. Utente solleciti created_by={user_id}.")
    print("Dati fittizi locali; nessun ODL creato.")


if __name__ == "__main__":
    main()
