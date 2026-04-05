from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, Session, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.buildings import Building
from app.models.cameras import Camera
from app.models.floors import Floor
from app.models.user import UserRole
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/api/cameras", tags=["Камеры"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    )
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
    )
SNAPSHOT_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    )


class CameraCreate(SQLModel):
    name: str = Field(min_length=1)
    ip_address: str = Field(min_length=1)
    is_active: bool = True
    direction: str = "internal"
    building_id: int | None = None
    floor_id: int | None = None
    plan_x: float | None = None
    plan_y: float | None = None


class CameraUpdate(SQLModel):
    name: str | None = None
    ip_address: str | None = None
    is_active: bool | None = None
    direction: str | None = None
    building_id: int | None = None
    floor_id: int | None = None
    plan_x: float | None = None
    plan_y: float | None = None


class CameraRead(SQLModel):
    id: int
    name: str
    ip_address: str
    is_active: bool
    direction: str | None = None
    building_id: int | None = None
    floor_id: int | None = None
    plan_x: float | None = None
    plan_y: float | None = None


class CameraReadWithNames(CameraRead):
    building_name: str | None = None
    floor_name: str | None = None
    floor_number: int | None = None


def _validate_location(
    session: Session,
    building_id: int | None,
    floor_id: int | None,
):
    if building_id is not None:
        building = session.get(Building, building_id)
        if not building:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Здание с id={building_id} не найдено",
            )

    if floor_id is not None:
        floor = session.get(Floor, floor_id)
        if not floor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Этаж с id={floor_id} не найден",
            )

        if building_id is not None and floor.building_id != building_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Этаж не принадлежит выбранному зданию",
            )

        if building_id is None:
            building_id = floor.building_id

    return building_id, floor_id


@router.get(
    "/",
    response_model=List[CameraReadWithNames],
    summary="Получить камеры",
    description="Возвращает список камер. Можно фильтровать по building_id и floor_id.",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_cameras(
    building_id: int | None = None,
    floor_id: int | None = None,
    session: Session = Depends(get_session),
):
    statement = (
        select(Camera, Building, Floor)
        .join(Building, Camera.building_id == Building.id, isouter=True)
        .join(Floor, Camera.floor_id == Floor.id, isouter=True)
    )

    if building_id is not None:
        statement = statement.where(Camera.building_id == building_id)
    if floor_id is not None:
        statement = statement.where(Camera.floor_id == floor_id)

    statement = statement.order_by(Camera.name.asc())
    rows = session.exec(statement).all()

    result = []
    for camera, building, floor in rows:
        result.append(
            CameraReadWithNames(
                id=camera.id,
                name=camera.name,
                ip_address=camera.ip_address,
                is_active=camera.is_active,
                direction=camera.direction,
                building_id=camera.building_id,
                floor_id=camera.floor_id,
                plan_x=camera.plan_x,
                plan_y=camera.plan_y,
                building_name=building.name if building else None,
                floor_name=floor.name if floor else None,
                floor_number=floor.floor_number if floor else None,
            )
        )
    return result


@router.get(
    "/{camera_id}",
    response_model=CameraReadWithNames,
    summary="Получить камеру по ID",
    description="Возвращает карточку камеры.",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_camera(camera_id: int, session: Session = Depends(get_session)):
    statement = (
        select(Camera, Building, Floor)
        .join(Building, Camera.building_id == Building.id, isouter=True)
        .join(Floor, Camera.floor_id == Floor.id, isouter=True)
        .where(Camera.id == camera_id)
    )
    row = session.exec(statement).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )

    camera, building, floor = row
    return CameraReadWithNames(
        id=camera.id,
        name=camera.name,
        ip_address=camera.ip_address,
        is_active=camera.is_active,
        direction=camera.direction,
        building_id=camera.building_id,
        floor_id=camera.floor_id,
        plan_x=camera.plan_x,
        plan_y=camera.plan_y,
        building_name=building.name if building else None,
        floor_name=floor.name if floor else None,
        floor_number=floor.floor_number if floor else None,
    )


@router.post(
    "/",
    response_model=CameraRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать камеру",
    description="Создает новую камеру.",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_camera(payload: CameraCreate, session: Session = Depends(get_session)):
    building_id, floor_id = _validate_location(session, payload.building_id, payload.floor_id)

    camera = Camera(
        name=payload.name.strip(),
        ip_address=payload.ip_address.strip(),
        is_active=payload.is_active,
        direction=payload.direction,
        building_id=building_id,
        floor_id=floor_id,
        plan_x=payload.plan_x,
        plan_y=payload.plan_y,
    )

    try:
        session.add(camera)
        session.commit()
        session.refresh(camera)

        if camera.is_active:
            stream_manager.add_camera(camera.id, camera.ip_address, camera.direction)

        return camera
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось создать камеру",
        )


@router.patch(
    "/{camera_id}",
    response_model=CameraRead,
    summary="Обновить камеру",
    description="Обновляет камеру, ее этаж и позицию на плане.",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    session: Session = Depends(get_session),
):
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )

    next_building_id = payload.building_id if payload.building_id is not None else camera.building_id
    next_floor_id = payload.floor_id if payload.floor_id is not None else camera.floor_id
    next_building_id, next_floor_id = _validate_location(session, next_building_id, next_floor_id)

    if payload.name is not None:
        camera.name = payload.name.strip()
    if payload.ip_address is not None:
        camera.ip_address = payload.ip_address.strip()
    if payload.is_active is not None:
        camera.is_active = payload.is_active
    if payload.direction is not None:
        camera.direction = payload.direction

    camera.building_id = next_building_id
    camera.floor_id = next_floor_id

    if payload.plan_x is not None:
        if payload.plan_x < 0 or payload.plan_x > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="plan_x должен быть в диапазоне от 0 до 1",
            )
        camera.plan_x = payload.plan_x

    if payload.plan_y is not None:
        if payload.plan_y < 0 or payload.plan_y > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="plan_y должен быть в диапазоне от 0 до 1",
            )
        camera.plan_y = payload.plan_y

    try:
        session.add(camera)
        session.commit()
        session.refresh(camera)

        if camera.is_active:
            stream_manager.add_camera(camera.id, camera.ip_address, camera.direction)
        else:
            stream_manager.remove_camera(camera.id)

        return camera
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось обновить камеру",
        )




@router.get(
    "/{camera_id}/snapshot",
    summary="Сделать моментальный снимок с камеры",
    description="Забирает последний кадр из фонового видеопотока. Идеально для регистрации гостей.",
    dependencies=[Depends(require_roles(*SNAPSHOT_ROLES))],
)
def get_camera_snapshot(camera_id: int):
    frame_bytes = stream_manager.get_latest_frame(camera_id, max_age_sec=3.0)

    if not frame_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера неактивна или поток временно недоступен",
        )

    return Response(content=frame_bytes, media_type="image/jpeg")
