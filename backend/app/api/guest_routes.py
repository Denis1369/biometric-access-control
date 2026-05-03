from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import SQLModel, Session

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.floors import Floor
from app.models.user import UserRole
from app.services.guest_route_service import (
    build_guest_probable_route,
    get_floor_camera_route_candidates,
)

router = APIRouter(prefix="/api", tags=["Вероятные маршруты гостей"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
)


class GuestProbableRouteRead(SQLModel):
    guest_id: int
    floor_id: int
    events: list[dict[str, Any]]
    route_nodes: list[dict[str, Any]]
    route_edges: list[dict[str, Any]]
    camera_zones: list[dict[str, Any]]
    distance: float
    warnings: list[str]


class CameraRouteCandidatesRead(SQLModel):
    floor_id: int
    cameras: list[dict[str, Any]]
    warnings: list[str]


@router.get(
    "/floors/{floor_id}/camera-route-candidates",
    response_model=CameraRouteCandidatesRead,
    summary="Получить участки графа, попадающие в зоны камер",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_camera_route_candidates_for_floor(
    floor_id: int,
    session: Session = Depends(get_session),
):
    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )

    return get_floor_camera_route_candidates(session, floor_id)


@router.get(
    "/floors/{floor_id}/guests/{guest_id}/probable-route",
    response_model=GuestProbableRouteRead,
    summary="Построить вероятный маршрут гостя по событиям камер",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_guest_probable_route(
    floor_id: int,
    guest_id: int,
    time_from: datetime | None = Query(default=None),
    time_to: datetime | None = Query(default=None),
    session: Session = Depends(get_session),
):
    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )

    try:
        return build_guest_probable_route(
            session=session,
            guest_id=guest_id,
            floor_id=floor_id,
            time_from=time_from,
            time_to=time_to,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
