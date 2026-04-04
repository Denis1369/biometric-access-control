from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.buildings import Building
from app.models.cameras import Camera
from app.models.floors import Floor
from app.models.user import UserRole

router = APIRouter(prefix="/api/buildings", tags=["Здания"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    UserRole.MANAGER_ANALYST,
    UserRole.TECH_HR,
)
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.TECH_HR,
)


class BuildingCreate(SQLModel):
    name: str = Field(min_length=1)
    address: str | None = None


class BuildingUpdate(SQLModel):
    name: str | None = None
    address: str | None = None


class BuildingRead(SQLModel):
    id: int
    name: str
    address: str | None = None
    created_at: datetime


@router.get(
    "/",
    response_model=List[BuildingRead],
    summary="Получить список зданий",
    description="Возвращает список всех зданий.",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_buildings(session: Session = Depends(get_session)):
    statement = select(Building).order_by(Building.name.asc())
    return session.exec(statement).all()


@router.get(
    "/{building_id}",
    response_model=BuildingRead,
    summary="Получить здание по ID",
    description="Возвращает карточку здания.",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_building(building_id: int, session: Session = Depends(get_session)):
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
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def create_building(payload: BuildingCreate, session: Session = Depends(get_session)):
    building = Building(
        name=payload.name.strip(),
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
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def update_building(
    building_id: int,
    payload: BuildingUpdate,
    session: Session = Depends(get_session),
):
    building = session.get(Building, building_id)
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Здание не найдено",
        )

    if payload.name is not None:
        building.name = payload.name.strip()
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


@router.delete(
    "/{building_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить здание",
    description="Удаляет здание, его этажи и отвязывает камеры.",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def delete_building(building_id: int, session: Session = Depends(get_session)):
    building = session.get(Building, building_id)
    if not building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Здание не найдено",
        )

    cameras = session.exec(
        select(Camera).where(Camera.building_id == building_id)
    ).all()
    for camera in cameras:
        camera.building_id = None
        camera.floor_id = None
        session.add(camera)

    floors = session.exec(select(Floor).where(Floor.building_id == building_id)).all()
    for floor in floors:
        session.delete(floor)

    session.delete(building)
    session.commit()
    return None
