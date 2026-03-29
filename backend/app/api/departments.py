from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List
from datetime import time
from pydantic import BaseModel

from app.core.database import get_session
from app.models.departments import Department

router = APIRouter(prefix="/api/departments", tags=["Отделы"])

class GlobalScheduleUpdate(BaseModel):
    work_start: time
    work_end: time
    lunch_start: time
    lunch_end: time

@router.get("/", response_model=List[Department])
def get_departments(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = select(Department).offset(skip).limit(limit)
    return session.exec(statement).all()

@router.post("/", response_model=Department, status_code=status.HTTP_201_CREATED)
def create_department(department: Department, session: Session = Depends(get_session)):
    existing = session.exec(select(Department).where(Department.name == department.name)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отдел уже существует")
    session.add(department)
    session.commit()
    session.refresh(department)
    return department

@router.patch("/{department_id}", response_model=Department)
def update_department(department_id: int, department_data: dict, session: Session = Depends(get_session)):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")
    
    for key, value in department_data.items():
        if hasattr(department, key):
            setattr(department, key, value)
            
    session.add(department)
    session.commit()
    session.refresh(department)
    return department

@router.post("/apply-global-schedule", summary="Применить график ко всем отделам")
def apply_global_schedule(schedule: GlobalScheduleUpdate, session: Session = Depends(get_session)):
    departments = session.exec(select(Department)).all()
    for dept in departments:
        dept.work_start = schedule.work_start
        dept.work_end = schedule.work_end
        dept.lunch_start = schedule.lunch_start
        dept.lunch_end = schedule.lunch_end
        session.add(dept)
    
    session.commit()
    return {"message": "Успешно применено ко всем отделам"}

@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: int, session: Session = Depends(get_session)):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")
    session.delete(department)
    session.commit()
    return None