"""API отделов и рабочих графиков.

Отделы используются не только как справочник для карточек сотрудников. Их
рабочее время участвует в аналитике посещаемости: система сравнивает фактические
приходы/уходы сотрудников с графиком отдела и показывает опоздания,
отсутствия и дисциплину за день или месяц.
"""

from datetime import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import DEPARTMENTS_READ, DEPARTMENTS_WRITE
from app.models.departments import Department

router = APIRouter(prefix="/api/departments", tags=["Отделы"])

class GlobalScheduleUpdate(BaseModel):
    """Единый график, который можно применить ко всем отделам сразу."""

    work_start: time
    work_end: time
    lunch_start: time
    lunch_end: time


class DepartmentCreate(SQLModel):
    """Данные для создания отдела с графиком рабочего дня."""

    name: str = Field(min_length=1)
    work_start: time = time(9, 0)
    work_end: time = time(18, 0)
    lunch_start: time = time(13, 0)
    lunch_end: time = time(14, 0)


class DepartmentUpdate(SQLModel):
    """Частичное обновление отдела и его расписания."""

    name: str | None = None
    work_start: time | None = None
    work_end: time | None = None
    lunch_start: time | None = None
    lunch_end: time | None = None


def _normalize_required_name(value: str) -> str:
    """Проверить название отдела перед сохранением.

    Отдел отображается в карточках сотрудников, фильтрах аналитики и отчётах.
    Пустое название сделает эти места нечитаемыми, поэтому backend отклоняет
    строку, состоящую только из пробелов.
    """
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
    dependencies=[Depends(require_permissions(DEPARTMENTS_READ))],
)
def get_departments(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    """Вернуть справочник отделов для HR-раздела и аналитики.

    Параметры `skip` и `limit` оставлены для совместимости с постраничной
    загрузкой. Сейчас список обычно небольшой, но API уже готов к росту
    количества подразделений.
    """
    statement = select(Department).offset(skip).limit(limit)
    return session.exec(statement).all()


@router.post(
    "/",
    response_model=Department,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(DEPARTMENTS_WRITE))],
)
def create_department(
    department: DepartmentCreate,
    session: Session = Depends(get_session),
):
    """Создать новый отдел и его рабочий график.

    HR или super-admin задаёт название и временные границы рабочего дня. Перед
    сохранением backend проверяет, что отдел с таким названием ещё не существует,
    иначе отчёты и фильтры будут показывать два одинаковых подразделения.
    """
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
    dependencies=[Depends(require_permissions(DEPARTMENTS_WRITE))],
)
def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    session: Session = Depends(get_session),
):
    """Обновить название отдела или его расписание.

    Функция принимает только изменённые поля. Это удобно для формы редактирования:
    пользователь может поменять, например, только время начала рабочего дня, не
    отправляя заново все остальные значения.
    """
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
    dependencies=[Depends(require_permissions(DEPARTMENTS_WRITE))],
)
def apply_global_schedule(schedule: GlobalScheduleUpdate, session: Session = Depends(get_session)):
    """Применить один график работы ко всем отделам.

    Эта операция нужна для быстрого демо и для организаций, где все подразделения
    работают по одинаковому расписанию. Вместо ручного редактирования каждого
    отдела backend проходит по всем записям и обновляет четыре временных поля.
    """
    departments = session.exec(select(Department)).all()
    for dept in departments:
        dept.work_start = schedule.work_start
        dept.work_end = schedule.work_end
        dept.lunch_start = schedule.lunch_start
        dept.lunch_end = schedule.lunch_end
        session.add(dept)

    session.commit()
    return {"message": "Успешно применено ко всем отделам"}
