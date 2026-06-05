"""API справочника должностей сотрудников.

Должности используются в карточках сотрудников и помогают HR-разделу хранить
более структурированные данные. Справочник поддерживает архивирование через
`is_active`, чтобы старые должности не исчезали из истории, но не мешали при
создании новых карточек.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, SQLModel
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import JOB_POSITIONS_READ, JOB_POSITIONS_WRITE
from app.models.job_positions import JobPosition

router = APIRouter(prefix="/api/job-positions", tags=["Должности"])

class JobPositionCreate(SQLModel):
    """Данные для создания новой должности."""

    name: str = Field(min_length=1)
    is_active: bool = True
    sort_order: int = 100
    department_id: int | None = None


class JobPositionUpdate(SQLModel):
    """Частичное обновление должности.

    Можно изменить название, активность, порядок сортировки или привязку к
    отделу. Все поля необязательные, потому что форма редактирования может
    отправлять только изменённые значения.
    """

    name: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    department_id: int | None = None


def _normalize_required_name(value: str) -> str:
    """Очистить название должности и запретить пустую строку.

    Пустая должность плохо выглядит в карточке сотрудника и аналитике, поэтому
    backend не полагается только на frontend-валидацию и повторно проверяет поле.
    """
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Название должности не может быть пустым")
    return normalized

@router.get(
    "/",
    response_model=List[JobPosition],
    dependencies=[Depends(require_permissions(JOB_POSITIONS_READ))],
)
def get_job_positions(only_active: bool = False, session: Session = Depends(get_session)):
    """Вернуть список должностей для форм сотрудников.

    Если `only_active=True`, API отдаёт только должности, которые можно выбирать
    при создании или редактировании сотрудника. Полный список нужен для
    администрирования справочника, где архивные должности тоже видны.
    """
    query = select(JobPosition)
    if only_active:
        query = query.where(JobPosition.is_active.is_(True))
    query = query.order_by(JobPosition.sort_order)
    return session.exec(query).all()


@router.post(
    "/",
    response_model=JobPosition,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(JOB_POSITIONS_WRITE))],
)
def create_job_position(
    position_data: JobPositionCreate,
    session: Session = Depends(get_session),
):
    """Создать должность в справочнике.

    Super-admin или HR задаёт название, порядок сортировки и при необходимости
    отдел. После сохранения должность сразу становится доступной в форме
    сотрудника, если `is_active` не выключен.
    """
    position = JobPosition(
        name=_normalize_required_name(position_data.name),
        is_active=position_data.is_active,
        sort_order=position_data.sort_order,
        department_id=position_data.department_id,
    )
    session.add(position)
    session.commit()
    session.refresh(position)
    return position


@router.patch(
    "/{position_id}",
    response_model=JobPosition,
    dependencies=[Depends(require_permissions(JOB_POSITIONS_WRITE))],
)
def update_job_position(
    position_id: int,
    position_data: JobPositionUpdate,
    session: Session = Depends(get_session),
):
    """Обновить существующую должность.

    Функция сначала проверяет, что запись существует, затем применяет только
    переданные поля. Такой PATCH-подход уменьшает риск случайно сбросить
    остальные настройки должности.
    """
    position = session.get(JobPosition, position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Должность не найдена")

    update_data = position_data.model_dump(exclude_unset=True)
    if "name" in update_data:
        position.name = _normalize_required_name(update_data.pop("name"))

    for key, value in update_data.items():
        setattr(position, key, value)

    session.add(position)
    session.commit()
    session.refresh(position)
    return position
