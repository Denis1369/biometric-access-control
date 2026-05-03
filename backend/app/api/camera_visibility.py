from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, Session, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.camera_visibility_zones import CameraVisibilityZone
from app.models.cameras import Camera
from app.models.floors import Floor
from app.models.user import UserRole

router = APIRouter(prefix="/api", tags=["Зоны видимости камер"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
)
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
)


class CameraZonePoint(SQLModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class CameraZoneUpsert(SQLModel):
    floor_id: int
    points: list[CameraZonePoint]


class CameraZoneRead(SQLModel):
    id: int
    camera_id: int
    floor_id: int
    points: list[CameraZonePoint]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FloorCameraZonesRead(SQLModel):
    zones: list[CameraZoneRead]


def _zone_to_read(zone: CameraVisibilityZone) -> CameraZoneRead:
    return CameraZoneRead(
        id=zone.id,
        camera_id=zone.camera_id,
        floor_id=zone.floor_id,
        points=[CameraZonePoint(**point) for point in zone.points_json],
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


def _validate_points(points: list[CameraZonePoint]) -> list[dict[str, float]]:
    if len(points) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Зона видимости камеры должна содержать ровно 4 точки",
        )

    return [{"x": float(point.x), "y": float(point.y)} for point in points]


@router.get(
    "/floors/{floor_id}/camera-visibility-zones",
    response_model=FloorCameraZonesRead,
    summary="Получить зоны видимости камер этажа",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_floor_camera_zones(floor_id: int, session: Session = Depends(get_session)):
    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )

    zones = session.exec(
        select(CameraVisibilityZone)
        .where(CameraVisibilityZone.floor_id == floor_id)
        .order_by(CameraVisibilityZone.camera_id.asc())
    ).all()
    return FloorCameraZonesRead(zones=[_zone_to_read(zone) for zone in zones])


@router.get(
    "/cameras/{camera_id}/visibility-zone",
    response_model=CameraZoneRead | None,
    summary="Получить зону видимости камеры",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_camera_zone(camera_id: int, session: Session = Depends(get_session)):
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )

    zone = session.exec(
        select(CameraVisibilityZone).where(CameraVisibilityZone.camera_id == camera_id)
    ).first()
    return _zone_to_read(zone) if zone else None


@router.put(
    "/cameras/{camera_id}/visibility-zone",
    response_model=CameraZoneRead,
    summary="Создать или обновить зону видимости камеры",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def upsert_camera_zone(
    camera_id: int,
    payload: CameraZoneUpsert,
    session: Session = Depends(get_session),
):
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )
    if camera.floor_id != payload.floor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Камера не относится к выбранному этажу",
        )

    floor = session.get(Floor, payload.floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )

    points_json = _validate_points(payload.points)
    zone = session.exec(
        select(CameraVisibilityZone).where(CameraVisibilityZone.camera_id == camera_id)
    ).first()

    if zone:
        zone.floor_id = payload.floor_id
        zone.points_json = points_json
        zone.updated_at = datetime.now()
    else:
        zone = CameraVisibilityZone(
            camera_id=camera_id,
            floor_id=payload.floor_id,
            points_json=points_json,
        )

    try:
        session.add(zone)
        session.commit()
        session.refresh(zone)
        return _zone_to_read(zone)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось сохранить зону видимости камеры",
        )


@router.delete(
    "/cameras/{camera_id}/visibility-zone",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить зону видимости камеры",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def delete_camera_zone(camera_id: int, session: Session = Depends(get_session)):
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )

    zone = session.exec(
        select(CameraVisibilityZone).where(CameraVisibilityZone.camera_id == camera_id)
    ).first()
    if zone:
        session.delete(zone)
        session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
