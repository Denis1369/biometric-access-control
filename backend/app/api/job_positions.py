from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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

@router.get(
    "/",
    response_model=List[JobPosition],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_job_positions(only_active: bool = False, session: Session = Depends(get_session)):
    query = select(JobPosition)
    if only_active:
        query = query.where(JobPosition.is_active == True)
    query = query.order_by(JobPosition.sort_order)
    return session.exec(query).all()


@router.post(
    "/",
    response_model=JobPosition,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_job_position(position_data: dict, session: Session = Depends(get_session)):
    # Используем dict, чтобы динамически принимать все поля, включая новый department_id
    position = JobPosition(**position_data)
    session.add(position)
    session.commit()
    session.refresh(position)
    return position


@router.patch(
    "/{position_id}",
    response_model=JobPosition,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def update_job_position(position_id: int, position_data: dict, session: Session = Depends(get_session)):
    position = session.get(JobPosition, position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Должность не найдена")

    for key, value in position_data.items():
        if hasattr(position, key):
            setattr(position, key, value)

    session.add(position)
    session.commit()
    session.refresh(position)
    return position