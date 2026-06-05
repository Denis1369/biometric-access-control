"""API зон видимости камер на плане этажа.

Зона видимости — это четырёхугольник, который оператор рисует вокруг участка
плана, попадающего в обзор конкретной камеры. Эти зоны используются не для
распознавания по видео, а для связывания событий камеры с графом маршрутов:
если гость найден на камере, система считает, что он мог находиться на линиях
графа, пересекающих эту зону.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, Session, select

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import CAMERA_ZONES_READ, CAMERA_ZONES_WRITE
from app.models.camera_visibility_zones import CameraVisibilityZone
from app.models.cameras import Camera
from app.models.floors import Floor

router = APIRouter(prefix="/api", tags=["Зоны видимости камер"])

class CameraZonePoint(SQLModel):
    """Одна точка полигона зоны видимости в координатах исходного плана."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)


class CameraZoneUpsert(SQLModel):
    """Запрос на создание или обновление зоны видимости камеры."""

    floor_id: int
    points: list[CameraZonePoint]


class CameraZoneRead(SQLModel):
    """Зона видимости в формате, удобном для отрисовки SVG-полигона."""

    id: int
    camera_id: int
    floor_id: int
    points: list[CameraZonePoint]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FloorCameraZonesRead(SQLModel):
    """Ответ со всеми зонами видимости камер выбранного этажа."""

    zones: list[CameraZoneRead]


def _zone_to_read(zone: CameraVisibilityZone) -> CameraZoneRead:
    """Преобразовать модель БД в DTO, где `points_json` называется просто `points`.

    В базе точки лежат в JSON-поле, а frontend работает с обычным массивом точек.
    Эта функция делает преобразование в одном месте, чтобы endpoint-ы не
    дублировали логику и всегда возвращали одинаковую структуру.
    """
    return CameraZoneRead(
        id=zone.id,
        camera_id=zone.camera_id,
        floor_id=zone.floor_id,
        points=[CameraZonePoint(**point) for point in zone.points_json],
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


def _validate_points(points: list[CameraZonePoint]) -> list[dict[str, float]]:
    """Проверить, что зона камеры задана ровно четырьмя точками.

    Для дипломного сценария выбран простой и управляемый формат зоны видимости:
    произвольный четырёхугольник. Он достаточно гибкий для коридора или холла,
    но не требует сложного редактора многоугольников. Отрицательные координаты
    запрещены схемой `CameraZonePoint`, потому что координаты считаются от
    левого верхнего угла исходного изображения плана.
    """
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
    dependencies=[Depends(require_permissions(CAMERA_ZONES_READ))],
)
def get_floor_camera_zones(floor_id: int, session: Session = Depends(get_session)):
    """Вернуть все зоны видимости активных камер этажа.

    Endpoint используется страницей плана здания, чтобы зоны всегда были видны
    поверх изображения плана. Join с таблицей камер нужен, чтобы не показывать
    «осиротевшие» зоны, если камера была удалена или перенесена на другой этаж.
    """
    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )

    zones = session.exec(
        select(CameraVisibilityZone)
        .join(Camera, CameraVisibilityZone.camera_id == Camera.id)
        .where(
            CameraVisibilityZone.floor_id == floor_id,
            Camera.floor_id == floor_id,
        )
        .order_by(CameraVisibilityZone.camera_id.asc())
    ).all()
    return FloorCameraZonesRead(zones=[_zone_to_read(zone) for zone in zones])


@router.get(
    "/cameras/{camera_id}/visibility-zone",
    response_model=CameraZoneRead | None,
    summary="Получить зону видимости камеры",
    dependencies=[Depends(require_permissions(CAMERA_ZONES_READ))],
)
def get_camera_zone(camera_id: int, session: Session = Depends(get_session)):
    """Вернуть зону видимости конкретной камеры или `null`, если зона не задана.

    Frontend вызывает этот endpoint при выборе камеры в режиме редактирования.
    Если в базе случайно осталась зона с другим `floor_id`, она не отдаётся, чтобы
    пользователь не увидел неверный полигон на текущем плане.
    """
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )

    zone = session.exec(
        select(CameraVisibilityZone).where(CameraVisibilityZone.camera_id == camera_id)
    ).first()
    if zone and camera.floor_id != zone.floor_id:
        return None
    return _zone_to_read(zone) if zone else None


@router.put(
    "/cameras/{camera_id}/visibility-zone",
    response_model=CameraZoneRead,
    summary="Создать или обновить зону видимости камеры",
    dependencies=[Depends(require_permissions(CAMERA_ZONES_WRITE))],
)
def upsert_camera_zone(
    camera_id: int,
    payload: CameraZoneUpsert,
    session: Session = Depends(get_session),
):
    """Создать новую или обновить существующую зону видимости камеры.

    Перед сохранением backend проверяет, что камера существует, действительно
    находится на выбранном этаже и что сам этаж существует. Это защищает от
    ситуации, когда frontend отправил устаревшие данные после смены здания,
    удаления камеры или перезагрузки страницы.
    """
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
    dependencies=[Depends(require_permissions(CAMERA_ZONES_WRITE))],
)
def delete_camera_zone(camera_id: int, session: Session = Depends(get_session)):
    """Удалить зону видимости камеры, не удаляя саму камеру.

    Оператор может заново разметить обзор камеры: сначала удалить старую зону,
    затем нарисовать новую. Если зоны уже нет, endpoint всё равно возвращает 204,
    потому что итоговое состояние достигнуто — у камеры зоны нет.
    """
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
