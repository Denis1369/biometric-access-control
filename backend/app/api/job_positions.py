from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, Session, select

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


class JobPositionRead(SQLModel):
    id: int
    name: str
    is_active: bool
    sort_order: int


class JobPositionCreate(SQLModel):
    name: str
    sort_order: int = 100


class JobPositionUpdate(SQLModel):
    name: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


@router.get(
    "/",
    response_model=List[JobPositionRead],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_job_positions(
    session: Session = Depends(get_session),
    include_inactive: bool = False,
):
    statement = select(JobPosition)
    if not include_inactive:
        statement = statement.where(JobPosition.is_active == True)
    statement = statement.order_by(JobPosition.sort_order.asc(), JobPosition.name.asc())
    return session.exec(statement).all()


@router.post(
    "/",
    response_model=JobPositionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_job_position(
    payload: JobPositionCreate,
    session: Session = Depends(get_session),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название должности не может быть пустым")

    position = JobPosition(name=name, sort_order=payload.sort_order, is_active=True)
    try:
        session.add(position)
        session.commit()
        session.refresh(position)
        return position
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Такая должность уже существует")


@router.patch(
    "/{position_id}",
    response_model=JobPositionRead,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def update_job_position(
    position_id: int,
    payload: JobPositionUpdate,
    session: Session = Depends(get_session),
):
    position = session.get(JobPosition, position_id)
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Должность не найдена")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Название должности не может быть пустым")
        position.name = name
    if payload.is_active is not None:
        position.is_active = payload.is_active
    if payload.sort_order is not None:
        position.sort_order = payload.sort_order

    try:
        session.add(position)
        session.commit()
        session.refresh(position)
        return position
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Такая должность уже существует")
