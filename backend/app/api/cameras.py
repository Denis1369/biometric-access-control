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

ALLOWED_DIRECTIONS = {"in", "out", "both", "internal"}


class CameraCreate(SQLModel):
    name: str = Field(min_length=1)
    ip_address: str = Field(min_length=1)
    is_active: bool = True
    direction: str = "internal"
    building_id: int | None = None
    floor_id: int | None = None
    plan_x: float | None = None
    plan_y: float | None = None
    visibility_polygon: list[dict[str, float]] | None = None


class CameraUpdate(SQLModel):
    name: str | None = None
    ip_address: str | None = None
    is_active: bool | None = None
    direction: str | None = None
    building_id: int | None = None
    floor_id: int | None = None
    plan_x: float | None = None
    plan_y: float | None = None
    visibility_polygon: list[dict[str, float]] | None = None


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
    visibility_polygon: list[dict[str, float]] | None = None


class CameraReadWithNames(CameraRead):
    building_name: str | None = None
    floor_name: str | None = None
    floor_number: int | None = None


class DemoRecognitionUpdate(SQLModel):
    enabled: bool


class DemoRecognitionState(SQLModel):
    camera_id: int
    recognition_enabled: bool
    is_demo_source: bool


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


def _validate_ratio(value: float | None, field_name: str):
    if value is None:
        return
    if value < 0 or value > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} должен быть в диапазоне от 0 до 1",
        )


def _normalize_visibility_polygon(
    value: list[dict[str, float]] | None,
) -> list[dict[str, float]] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Зона видимости камеры должна содержать ровно 4 точки",
        )

    points: list[dict[str, float]] = []
    for index, raw_point in enumerate(value, start=1):
        if not isinstance(raw_point, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Точка зоны видимости #{index} должна быть объектом",
            )
        try:
            x = float(raw_point.get("x"))
            y = float(raw_point.get("y"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Точка зоны видимости #{index} должна содержать числовые x и y",
            ) from exc

        _validate_ratio(x, f"visibility_polygon[{index}].x")
        _validate_ratio(y, f"visibility_polygon[{index}].y")
        points.append({"x": x, "y": y})

    return points


def _normalize_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Поле {field_name} не может быть пустым",
        )
    return normalized


def _normalize_direction(direction: str) -> str:
    normalized = direction.strip().lower()
    if normalized not in ALLOWED_DIRECTIONS:
        allowed = ", ".join(sorted(ALLOWED_DIRECTIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Некорректное направление камеры. Допустимые значения: {allowed}",
        )
    return normalized


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
                visibility_polygon=camera.visibility_polygon,
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
        visibility_polygon=camera.visibility_polygon,
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
    _validate_ratio(payload.plan_x, "plan_x")
    _validate_ratio(payload.plan_y, "plan_y")
    visibility_polygon = _normalize_visibility_polygon(payload.visibility_polygon)

    camera = Camera(
        name=_normalize_non_empty(payload.name, "name"),
        ip_address=_normalize_non_empty(payload.ip_address, "ip_address"),
        is_active=payload.is_active,
        direction=_normalize_direction(payload.direction),
        building_id=building_id,
        floor_id=floor_id,
        plan_x=payload.plan_x,
        plan_y=payload.plan_y,
        visibility_polygon=visibility_polygon,
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

    update_data = payload.model_dump(exclude_unset=True)

    if "building_id" in update_data or "floor_id" in update_data:
        next_building_id = update_data.get("building_id", camera.building_id)
        next_floor_id = update_data.get("floor_id", camera.floor_id)
        
        next_building_id, next_floor_id = _validate_location(session, next_building_id, next_floor_id)
        
        camera.building_id = next_building_id
        camera.floor_id = next_floor_id

    for key, value in update_data.items():
        if key in ["building_id", "floor_id"]:
            continue

        if key in ["plan_x", "plan_y"]:
            _validate_ratio(value, key)
            setattr(camera, key, value)
        elif key == "visibility_polygon":
            camera.visibility_polygon = _normalize_visibility_polygon(value)
        elif key in ["name", "ip_address"]:
            if value is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Поле {key} не может быть null",
                )
            setattr(camera, key, _normalize_non_empty(value, key))
        elif key == "direction":
            if value is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Поле direction не может быть null",
                )
            setattr(camera, key, _normalize_direction(value))
        elif isinstance(value, str):
            setattr(camera, key, value.strip())
        else:
            setattr(camera, key, value)

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
            detail="Не удалось обновить камеру. Возможно, такой IP уже существует.",
        )



@router.post(
    "/{camera_id}/demo-recognition",
    response_model=DemoRecognitionState,
    summary="Управление распознаванием демо-камеры",
    description="Включает или выключает распознавание для локального видеоисточника в рантайме.",
    dependencies=[Depends(require_roles(*SNAPSHOT_ROLES))],
)
def update_demo_recognition(camera_id: int, payload: DemoRecognitionUpdate):
    state = stream_manager.set_demo_recognition_enabled(camera_id, payload.enabled)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена или поток не запущен",
        )

    return DemoRecognitionState(**state)


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

