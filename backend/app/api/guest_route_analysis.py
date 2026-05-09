from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel, Session

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.floors import Floor
from app.models.guest_route_analysis_jobs import GuestRouteAnalysisJob
from app.models.user import UserRole
from app.services.guest_route_analysis_service import (
    build_job_payload,
    create_guest_route_analysis_job,
    schedule_guest_route_analysis,
)

router = APIRouter(prefix="/api", tags=["Офлайн-маршруты гостей"])

ALLOWED_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
)


class GuestRouteAnalysisJobRead(SQLModel):
    id: int
    guest_id: int
    floor_id: int
    status: str
    time_from: datetime | None = None
    time_to: datetime | None = None
    processed_cameras: int
    total_cameras: int
    events_written: int
    warnings: list[str]
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    probable_route: dict[str, Any] | None = None


@router.post(
    "/floors/{floor_id}/guests/{guest_id}/route-analysis-jobs",
    response_model=GuestRouteAnalysisJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить офлайн-анализ маршрута гостя по video-file камерам этажа",
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
def create_route_analysis_job(
    floor_id: int,
    guest_id: int,
    session: Session = Depends(get_session),
):
    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    try:
        job = create_guest_route_analysis_job(session, guest_id=guest_id, floor_id=floor_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    schedule_guest_route_analysis(job.id)
    return build_job_payload(session, job)


@router.get(
    "/guest-route-analysis-jobs/{job_id}",
    response_model=GuestRouteAnalysisJobRead,
    summary="Получить статус офлайн-анализа маршрута гостя",
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
def get_route_analysis_job(
    job_id: int,
    session: Session = Depends(get_session),
):
    job = session.get(GuestRouteAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа маршрута не найдена")

    return build_job_payload(session, job)
