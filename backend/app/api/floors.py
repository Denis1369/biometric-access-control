from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.buildings import Building
from app.models.cameras import Camera
from app.models.floors import Floor
from app.models.user import UserRole

router = APIRouter(prefix="/api/floors", tags=["Этажи"])

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    )
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
    )


class FloorRead(SQLModel):
    id: int
    building_id: int
    name: str
    floor_number: int
    has_plan: bool
    created_at: datetime
    updated_at: datetime


class FloorWithBuildingRead(FloorRead):
    building_name: str | None = None


@router.get(
    "/",
    response_model=List[FloorRead],
    summary="Получить этажи",
    description="Возвращает этажи. Можно отфильтровать по building_id.",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_floors(
    building_id: int | None = None,
    session: Session = Depends(get_session),
):
    statement = select(Floor)
    if building_id is not None:
        statement = statement.where(Floor.building_id == building_id)
    statement = statement.order_by(Floor.floor_number.asc(), Floor.name.asc())

    floors = session.exec(statement).all()
    return [
        FloorRead(
            id=floor.id,
            building_id=floor.building_id,
            name=floor.name,
            floor_number=floor.floor_number,
            has_plan=floor.plan_image is not None,
            created_at=floor.created_at,
            updated_at=floor.updated_at,
        )
        for floor in floors
    ]


@router.get(
    "/{floor_id}",
    response_model=FloorWithBuildingRead,
    summary="Получить этаж по ID",
    description="Возвращает карточку этажа.",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_floor(floor_id: int, session: Session = Depends(get_session)):
    statement = (
        select(Floor, Building)
        .join(Building, Floor.building_id == Building.id)
        .where(Floor.id == floor_id)
    )
    row = session.exec(statement).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )

    floor, building = row
    return FloorWithBuildingRead(
        id=floor.id,
        building_id=floor.building_id,
        name=floor.name,
        floor_number=floor.floor_number,
        has_plan=floor.plan_image is not None,
        created_at=floor.created_at,
        updated_at=floor.updated_at,
        building_name=building.name if building else None,
    )


@router.get(
    "/{floor_id}/plan",
    summary="Получить план этажа",
    description="Возвращает изображение плана этажа.",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_floor_plan(floor_id: int, session: Session = Depends(get_session)):
    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )
    if not floor.plan_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="План этажа не загружен",
        )

    return Response(content=floor.plan_image, media_type=floor.plan_mime_type or "image/png")


@router.post(
    "/",
    response_model=FloorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать этаж",
    description="Создает этаж и при необходимости загружает план.",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
async def create_floor(
    building_id: int = Form(...),
    name: str = Form(...),
    floor_number: int = Form(...),
    plan: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    building = session.get(Building, building_id)
    if not building:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Здание с id={building_id} не найдено",
        )

    plan_bytes = await plan.read() if plan else None
    if plan and not plan_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл плана этажа пустой",
        )

    floor = Floor(
        building_id=building_id,
        name=name.strip(),
        floor_number=floor_number,
        plan_mime_type=plan.content_type if plan and plan_bytes else None,
        plan_image=plan_bytes,
    )

    try:
        session.add(floor)
        session.commit()
        session.refresh(floor)
        return FloorRead(
            id=floor.id,
            building_id=floor.building_id,
            name=floor.name,
            floor_number=floor.floor_number,
            has_plan=floor.plan_image is not None,
            created_at=floor.created_at,
            updated_at=floor.updated_at,
        )
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этаж с таким номером уже существует в этом здании",
        )


@router.patch(
    "/{floor_id}",
    response_model=FloorRead,
    summary="Обновить этаж",
    description="Обновляет название, номер и план этажа.",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
async def update_floor(
    floor_id: int,
    name: str | None = Form(None),
    floor_number: int | None = Form(None),
    plan: UploadFile | None = File(None),
    remove_plan: bool = Form(False),
    session: Session = Depends(get_session),
):
    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Этаж не найден",
        )

    if name is not None:
        floor.name = name.strip()
    if floor_number is not None:
        floor.floor_number = floor_number

    if remove_plan:
        floor.plan_image = None
        floor.plan_mime_type = None

    if plan is not None:
        plan_bytes = await plan.read()
        if not plan_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Файл плана этажа пустой",
            )
        floor.plan_image = plan_bytes
        floor.plan_mime_type = plan.content_type or "image/png"

    floor.updated_at = datetime.now()

    try:
        session.add(floor)
        session.commit()
        session.refresh(floor)
        return FloorRead(
            id=floor.id,
            building_id=floor.building_id,
            name=floor.name,
            floor_number=floor.floor_number,
            has_plan=floor.plan_image is not None,
            created_at=floor.created_at,
            updated_at=floor.updated_at,
        )
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось обновить этаж",
        )


