from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Field, SQLModel
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.job_positions import JobPosition
from app.models.user import UserRole

router = APIRouter(prefix="/api/job-positions", tags=["Должности"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
)
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
)


class JobPositionCreate(SQLModel):
    name: str = Field(min_length=1)
    is_active: bool = True
    sort_order: int = 100
    department_id: int | None = None


class JobPositionUpdate(SQLModel):
    name: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    department_id: int | None = None


def _normalize_required_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Название должности не может быть пустым")
    return normalized

@router.get(
    "/",
    response_model=List[JobPosition],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_job_positions(only_active: bool = False, session: Session = Depends(get_session)):
    query = select(JobPosition)
    if only_active:
        query = query.where(JobPosition.is_active.is_(True))
    query = query.order_by(JobPosition.sort_order)
    return session.exec(query).all()


@router.post(
    "/",
    response_model=JobPosition,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_job_position(
    position_data: JobPositionCreate,
    session: Session = Depends(get_session),
):
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
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def update_job_position(
    position_id: int,
    position_data: JobPositionUpdate,
    session: Session = Depends(get_session),
):
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
