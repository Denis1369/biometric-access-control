"""API камер видеонаблюдения и их размещения на плане.

Камера в проекте одновременно является источником видеопотока и объектом на
плане здания. В поле `ip_address` может храниться RTSP/HTTP-адрес реальной
камеры или путь к локальному `file://` видео для демонстрационного режима. Этот
router управляет справочником камер, их активностью, положением на плане и
получением последнего кадра для регистрации гостей.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, Session, select

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import (
    CAMERAS_WRITE,
    CAMERA_PLACEMENT_READ,
    CAMERA_SNAPSHOT_READ,
)
from app.models.buildings import Building
from app.models.camera_visibility_zones import CameraVisibilityZone
from app.models.cameras import Camera
from app.models.floors import Floor
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/api/cameras", tags=["Камеры"])

ALLOWED_DIRECTIONS = {"in", "out", "both", "internal"}


class CameraCreate(SQLModel):
    """Данные для создания камеры.

    `plan_x` и `plan_y` хранятся как относительные координаты от 0 до 1, потому
    что иконка камеры должна оставаться на правильном месте при любом размере
    изображения плана в браузере.
    """

    name: str = Field(min_length=1)
    ip_address: str = Field(min_length=1)
    is_active: bool = True
    direction: str = "internal"
    building_id: int | None = None
    floor_id: int | None = None
    plan_x: float | None = None
    plan_y: float | None = None


class CameraUpdate(SQLModel):
    """Частичное обновление камеры, источника видео и позиции на плане."""

    name: str | None = None
    ip_address: str | None = None
    is_active: bool | None = None
    direction: str | None = None
    building_id: int | None = None
    floor_id: int | None = None
    plan_x: float | None = None
    plan_y: float | None = None


class CameraRead(SQLModel):
    """Основное представление камеры, возвращаемое большинством endpoint-ов."""

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
    """Камера вместе с человекочитаемыми названиями здания и этажа."""

    building_name: str | None = None
    floor_name: str | None = None
    floor_number: int | None = None


class DemoRecognitionUpdate(SQLModel):
    """Запрос на включение или выключение распознавания для демо-видео."""

    enabled: bool


class DemoRecognitionState(SQLModel):
    """Текущее состояние распознавания на демо-камере."""

    camera_id: int
    recognition_enabled: bool
    is_demo_source: bool


def _validate_location(
    session: Session,
    building_id: int | None,
    floor_id: int | None,
):
    """Проверить, что выбранные здание и этаж существуют и согласованы.

    Камеру можно создать без этажа, но если этаж передан, он обязан принадлежать
    выбранному зданию. Иначе камера визуально окажется в одном объекте, а
    логически будет связана с другим, что сломает план здания и маршруты гостей.
    """
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
    """Проверить относительную координату камеры на плане.

    Для `plan_x` и `plan_y` допустим только диапазон от 0 до 1. Это не пиксели, а
    доля ширины/высоты изображения плана, поэтому значения меньше 0 или больше 1
    означают, что камера находится за пределами плана.
    """
    if value is None:
        return
    if value < 0 or value > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} должен быть в диапазоне от 0 до 1",
        )


def _normalize_non_empty(value: str, field_name: str) -> str:
    """Очистить обязательное строковое поле камеры и запретить пустую строку."""
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Поле {field_name} не может быть пустым",
        )
    return normalized


def _normalize_direction(direction: str) -> str:
    """Нормализовать направление камеры и проверить допустимые значения.

    Направление используется в сценариях проходной и аналитики. Например, камера
    может фиксировать вход, выход, оба направления или внутреннее перемещение по
    зданию. Некорректная строка отклоняется на backend, даже если frontend уже
    ограничивает выбор.
    """
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
    dependencies=[Depends(require_permissions(CAMERA_PLACEMENT_READ))],
)
def get_cameras(
    building_id: int | None = None,
    floor_id: int | None = None,
    session: Session = Depends(get_session),
):
    """Вернуть камеры, при необходимости отфильтрованные по зданию или этажу.

    Endpoint используется сразу в нескольких местах: в списке камер, в редакторе
    плана здания, в проходной и в офлайн-анализе. Поэтому ответ дополнен названиями
    здания и этажа, чтобы frontend не делал лишние запросы ради отображения.
    """
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
    dependencies=[Depends(require_permissions(CAMERA_PLACEMENT_READ))],
)
def get_camera(camera_id: int, session: Session = Depends(get_session)):
    """Вернуть одну камеру вместе с названиями здания и этажа."""
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
    dependencies=[Depends(require_permissions(CAMERAS_WRITE))],
)
def create_camera(payload: CameraCreate, session: Session = Depends(get_session)):
    """Создать камеру и при необходимости сразу запустить её поток.

    Если камера активна, после сохранения она передаётся в `stream_manager`.
    Благодаря этому новый источник начинает обрабатываться без перезапуска
    backend. Для локальных demo-видео используется тот же механизм, что и для
    реальных камер.
    """
    building_id, floor_id = _validate_location(session, payload.building_id, payload.floor_id)
    _validate_ratio(payload.plan_x, "plan_x")
    _validate_ratio(payload.plan_y, "plan_y")

    camera = Camera(
        name=_normalize_non_empty(payload.name, "name"),
        ip_address=_normalize_non_empty(payload.ip_address, "ip_address"),
        is_active=payload.is_active,
        direction=_normalize_direction(payload.direction),
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
    dependencies=[Depends(require_permissions(CAMERAS_WRITE))],
)
def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    session: Session = Depends(get_session),
):
    """Обновить камеру, её расположение и состояние фонового потока.

    Если камеру перенесли на другой этаж, старая зона видимости удаляется: зона
    нарисована в координатах конкретного плана и не может автоматически
    переноситься на другое изображение. После сохранения stream manager либо
    запускает/обновляет поток активной камеры, либо останавливает его.
    """
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )

    update_data = payload.model_dump(exclude_unset=True)
    previous_floor_id = camera.floor_id

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
        if previous_floor_id != camera.floor_id:
            old_zone = session.exec(
                select(CameraVisibilityZone).where(CameraVisibilityZone.camera_id == camera.id)
            ).first()
            if old_zone:
                session.delete(old_zone)

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
    dependencies=[Depends(require_permissions(CAMERA_SNAPSHOT_READ))],
)
def update_demo_recognition(camera_id: int, payload: DemoRecognitionUpdate):
    """Включить или выключить распознавание на локальной демо-камере.

    Эта функция нужна для защиты и тестирования: можно оставить видео включённым,
    но временно отключить тяжёлый анализ кадров, чтобы не засорять журналы или не
    нагружать слабый компьютер.
    """
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
    dependencies=[Depends(require_permissions(CAMERA_SNAPSHOT_READ))],
)
def get_camera_snapshot(camera_id: int):
    """Вернуть последний JPEG-кадр активной камеры.

    Снимок используется при оформлении гостевого пропуска: оператор может взять
    актуальный кадр с проходной вместо загрузки файла с диска. Если свежего кадра
    нет, backend возвращает 404, чтобы frontend показал, что камера недоступна.
    """
    frame_bytes = stream_manager.get_latest_frame(camera_id, max_age_sec=3.0)

    if not frame_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера неактивна или поток временно недоступен",
        )

    return Response(content=frame_bytes, media_type="image/jpeg")

