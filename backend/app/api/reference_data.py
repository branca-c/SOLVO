from typing import Annotated

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Category, Technician
from app.schemas.reference_data import CategoryResponse, TechnicianResponse, TechnicianUpdate

router = APIRouter(prefix="/api", tags=["reference-data"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(db: Database):
    return db.scalars(select(Category).order_by(Category.name, Category.id)).all()


@router.get("/technicians", response_model=list[TechnicianResponse])
def list_technicians(
    db: Database, category_id: Annotated[int | None, Query(gt=0)] = None
):
    query = select(Technician, Category.name).join(Category).order_by(
        Category.name, Technician.is_team_leader, Technician.escalation_order, Technician.id
    )
    if category_id is not None:
        query = query.where(Technician.category_id == category_id)
    return [
        TechnicianResponse(
            id=technician.id, first_name=technician.first_name,
            last_name=technician.last_name, phone=technician.phone,
            email=technician.email, category_id=technician.category_id,
            category_name=name, escalation_order=technician.escalation_order,
            is_team_leader=technician.is_team_leader,
        )
        for technician, name in db.execute(query)
    ]


@router.patch("/technicians/{technician_id}", response_model=TechnicianResponse)
def update_technician(technician_id: int, data: TechnicianUpdate, db: Database):
    technician = db.get(Technician, technician_id)
    if technician is None:
        raise HTTPException(status_code=404, detail="Tecnico non trovato")
    try:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(technician, field, value)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(technician)
    return TechnicianResponse(id=technician.id, first_name=technician.first_name,
        last_name=technician.last_name, phone=technician.phone, email=technician.email,
        category_id=technician.category_id, category_name=technician.category.name,
        escalation_order=technician.escalation_order, is_team_leader=technician.is_team_leader)
