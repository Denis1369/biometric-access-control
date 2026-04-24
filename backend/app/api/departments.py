from datetime import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.departments import Department
from app.models.user import UserRole

router = APIRouter(prefix="/api/departments", tags=["Отделы"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    )
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
    )


class GlobalScheduleUpdate(BaseModel):
    work_start: time
    work_end: time
    lunch_start: time
    lunch_end: time


class DepartmentCreate(SQLModel):
    name: str = Field(min_length=1)
    work_start: time = time(9, 0)
    work_end: time = time(18, 0)
    lunch_start: time = time(13, 0)
    lunch_end: time = time(14, 0)


class DepartmentUpdate(SQLModel):
    name: str | None = None
    work_start: time | None = None
    work_end: time | None = None
    lunch_start: time | None = None
    lunch_end: time | None = None


def _normalize_required_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Название отдела не может быть пустым",
        )
    return normalized


@router.get(
    "/",
    response_model=List[Department],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_departments(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = select(Department).offset(skip).limit(limit)
    return session.exec(statement).all()


@router.post(
    "/",
    response_model=Department,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_department(
    department: DepartmentCreate,
    session: Session = Depends(get_session),
):
    normalized_name = _normalize_required_name(department.name)
    existing = session.exec(
        select(Department).where(Department.name == normalized_name)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отдел уже существует")
    department = Department(
        name=normalized_name,
        work_start=department.work_start,
        work_end=department.work_end,
        lunch_start=department.lunch_start,
        lunch_end=department.lunch_end,
    )
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


@router.patch(
    "/{department_id}",
    response_model=Department,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    session: Session = Depends(get_session),
):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")

    update_data = department_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        normalized_name = _normalize_required_name(update_data["name"])
        existing = session.exec(
            select(Department).where(
                Department.name == normalized_name,
                Department.id != department_id,
            )
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Отдел с таким названием уже существует",
            )
        department.name = normalized_name

    for key in ("work_start", "work_end", "lunch_start", "lunch_end"):
        if key in update_data:
            setattr(department, key, update_data[key])

    session.add(department)
    session.commit()
    session.refresh(department)
    return department


@router.post(
    "/apply-global-schedule",
    summary="Применить график ко всем отделам",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
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
