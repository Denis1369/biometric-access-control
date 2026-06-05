"""API вероятного маршрута гостя по журналам и зонам камер.

Этот router не анализирует видео напрямую. Он берёт уже записанные события
гостя из журналов, смотрит, какие камеры участвовали в выбранный период, связывает
эти камеры с зонами видимости и просит сервис построить вероятный путь по
ручному графу маршрутов этажа.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import SQLModel, Session

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import GUEST_ROUTES_READ
from app.models.floors import Floor
from app.services.guest_route_service import (
    build_guest_probable_route,
    get_floor_camera_route_candidates,
)

router = APIRouter(prefix="/api", tags=["Вероятные маршруты гостей"])

class GuestProbableRouteRead(SQLModel):
    """Ответ с готовым вероятным маршрутом гостя для модального окна."""

    guest_id: int
    floor_id: int
    events: list[dict[str, Any]]
    route_nodes: list[dict[str, Any]]
    route_edges: list[dict[str, Any]]
    camera_zones: list[dict[str, Any]]
    distance: float
    warnings: list[str]


class CameraRouteCandidatesRead(SQLModel):
    """Отладочный ответ: какие участки графа попадают в зоны камер этажа."""

    floor_id: int
    cameras: list[dict[str, Any]]
    warnings: list[str]


@router.get(
    "/floors/{floor_id}/camera-route-candidates",
    response_model=CameraRouteCandidatesRead,
    summary="Получить участки графа, попадающие в зоны камер",
    dependencies=[Depends(require_permissions(GUEST_ROUTES_READ))],
)
def get_camera_route_candidates_for_floor(
    floor_id: int,
    session: Session = Depends(get_session),
):
    """Показать связь зон камер с графом маршрутов.

    Endpoint нужен технику и разработчику для проверки разметки. Если зона камеры
    не пересекает ни одну линию графа, маршрут по этой камере построить нельзя,
    поэтому API возвращает warnings, которые frontend показывает в интерфейсе.
    """
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
    dependencies=[Depends(require_permissions(GUEST_ROUTES_READ))],
)
def get_guest_probable_route(
    floor_id: int,
    guest_id: int,
    time_from: datetime | None = Query(default=None),
    time_to: datetime | None = Query(default=None),
    session: Session = Depends(get_session),
):
    """Построить маршрут гостя по уже записанным событиям камер.

    Пользователь выбирает гостя, этаж и период времени. Backend фильтрует события
    этого гостя, оставляет камеры выбранного этажа и строит путь по графу через
    зоны видимости камер. Если данных недостаточно, возвращается понятная ошибка
    или предупреждения, а не технический stack trace.
    """
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
