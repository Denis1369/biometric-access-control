"""API справочника зданий.

Здание является верхним уровнем структуры объекта: внутри здания создаются этажи,
на этажах загружаются планы, размещаются камеры, зоны видимости и граф маршрутов.
Эти endpoint-ы используются в разделе «План здания», где техник или
super-admin подготавливает объект для дальнейшей работы системы контроля доступа.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import BUILDINGS_READ, BUILDINGS_WRITE
from app.models.buildings import Building
from app.models.cameras import Camera
from app.models.floors import Floor

router = APIRouter(prefix="/api/buildings", tags=["Здания"])

class BuildingCreate(SQLModel):
    """Данные, которые frontend отправляет при создании нового здания."""

    name: str = Field(min_length=1)
    address: str | None = None


class BuildingUpdate(SQLModel):
    """Частичное обновление здания.

    Все поля необязательные, потому что PATCH может изменить только название,
    только адрес или оба поля сразу.
    """

    name: str | None = None
    address: str | None = None


class BuildingRead(SQLModel):
    """Представление здания, возвращаемое frontend-у."""

    id: int
    name: str
    address: str | None = None
    created_at: datetime


def _normalize_required_name(value: str, field_name: str) -> str:
    """Очистить обязательное строковое поле и запретить пустые названия.

    Проверка нужна не только для красоты интерфейса. Пустое название здания
    делает невозможной нормальную работу выпадающих списков и создаёт путаницу
    при выборе этажа, поэтому backend жёстко отклоняет такие значения.
    """
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Поле {field_name} не может быть пустым",
        )
    return normalized


@router.get(
    "/",
    response_model=List[BuildingRead],
    summary="Получить список зданий",
    description="Возвращает список всех зданий.",
    dependencies=[Depends(require_permissions(BUILDINGS_READ))],
)
def get_buildings(session: Session = Depends(get_session)):
    """Вернуть список зданий для выбора объекта в интерфейсе.

    Страница плана здания сначала загружает здания, затем по выбранному зданию
    получает этажи. Список сортируется по названию, чтобы оператору было проще
    найти нужный объект.
    """
    statement = select(Building).order_by(Building.name.asc())
    return session.exec(statement).all()


@router.get(
    "/{building_id}",
    response_model=BuildingRead,
    summary="Получить здание по ID",
    description="Возвращает карточку здания.",
    dependencies=[Depends(require_permissions(BUILDINGS_READ))],
)
def get_building(building_id: int, session: Session = Depends(get_session)):
    """Вернуть одну карточку здания по идентификатору.

    Endpoint нужен для экранов редактирования и для случаев, когда frontend
    открывает ссылку на конкретное здание. Если запись удалена или id ошибочный,
    возвращается 404, чтобы интерфейс мог показать понятное сообщение.
    """
    building = session.get(Building, building_id)
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Здание не найдено",
        )
    return building


@router.post(
    "/",
    response_model=BuildingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать здание",
    description="Создает новое здание.",
    dependencies=[Depends(require_permissions(BUILDINGS_WRITE))],
)
def create_building(payload: BuildingCreate, session: Session = Depends(get_session)):
    """Создать новое здание в справочнике.

    Функция вызывается техником или super-admin. Backend нормализует название,
    сохраняет адрес и отдельно обрабатывает конфликт уникальности, чтобы вместо
    технической ошибки базы данных пользователь увидел понятное сообщение.
    """
    building = Building(
        name=_normalize_required_name(payload.name, "name"),
        address=payload.address.strip() if payload.address else None,
    )

    try:
        session.add(building)
        session.commit()
        session.refresh(building)
        return building
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Здание с таким названием уже существует",
        )


@router.patch(
    "/{building_id}",
    response_model=BuildingRead,
    summary="Обновить здание",
    description="Обновляет название и адрес здания.",
    dependencies=[Depends(require_permissions(BUILDINGS_WRITE))],
)
def update_building(
    building_id: int,
    payload: BuildingUpdate,
    session: Session = Depends(get_session),
):
    """Изменить название или адрес существующего здания.

    При обновлении нельзя допустить пустое название и дублирование зданий с
    одинаковыми названиями. Поэтому функция сначала загружает запись, применяет
    только переданные поля, а затем перехватывает ошибку уникальности.
    """
    building = session.get(Building, building_id)
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Здание не найдено",
        )

    if payload.name is not None:
        building.name = _normalize_required_name(payload.name, "name")
    if payload.address is not None:
        building.address = payload.address.strip() if payload.address else None

    try:
        session.add(building)
        session.commit()
        session.refresh(building)
        return building
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось обновить здание",
        )


