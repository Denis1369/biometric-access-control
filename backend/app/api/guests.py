from datetime import datetime
import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.employees import Employee
from app.models.guests import Guest, GuestFaceSample
from app.models.user import UserRole
from app.services.photo_conversion import extract_face_encoding

router = APIRouter(prefix="/api/guests", tags=["Гости"])
logger = logging.getLogger(__name__)

READ_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    )
WRITE_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    )


def _normalize_required_name(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"Поле {field_name} не может быть пустым")
    return normalized


def _normalize_valid_until(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)

class GuestRead(SQLModel):
    id: int
    last_name: str
    first_name: str
    middle_name: str | None = None
    employee_id: int | None = None
    employee_name: str | None = None
    valid_until: datetime
    is_active: bool
    photo_id: int | None = None


def build_employee_name(employee: Employee | None) -> str | None:
    if not employee:
        return None
    full_name = " ".join(
        part for part in [employee.last_name, employee.first_name, employee.middle_name] if part
    ).strip()
    return full_name or None


def build_guest_read(session: Session, guest: Guest) -> GuestRead:
    sample = session.exec(select(GuestFaceSample).where(GuestFaceSample.guest_id == guest.id)).first()
    employee = session.get(Employee, guest.employee_id) if guest.employee_id else None
    return GuestRead(
        **guest.model_dump(),
        employee_name=build_employee_name(employee),
        photo_id=sample.id if sample else None,
    )


@router.get(
    "/",
    response_model=List[GuestRead],
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_guests(session: Session = Depends(get_session)):
    guests = session.exec(select(Guest).order_by(Guest.id.desc())).all()
    return [build_guest_read(session, guest) for guest in guests]


@router.post(
    "/",
    response_model=GuestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
async def create_guest(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str | None = Form(None),
    employee_id: int = Form(...),
    valid_until: datetime = Form(...),
    photo: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    valid_until = _normalize_valid_until(valid_until)
    current_time = datetime.now()
    
    if valid_until < current_time:
        raise HTTPException(
            status_code=400, 
            detail="Нельзя выдать пропуск задним числом. Укажите время в будущем."
        )
    
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=400, detail=f"Сотрудник с id={employee_id} не найден")

    guest = Guest(
        last_name=_normalize_required_name(last_name, "last_name"),
        first_name=_normalize_required_name(first_name, "first_name"),
        middle_name=middle_name.strip() if middle_name else None,
        employee_id=employee_id,
        valid_until=valid_until,
        is_active=True,
    )

    try:
        session.add(guest)
        session.flush()

        image_bytes = await photo.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Фотография пуста")

        try:
            face_vector = extract_face_encoding(image_bytes)
        except ValueError:
            raise HTTPException(status_code=400, detail="Не удалось распознать лицо на фото")

        sample = GuestFaceSample(
            guest_id=guest.id,
            mime_type=photo.content_type or "image/jpeg",
            photo_data=image_bytes,
            embedding=face_vector,
        )
        session.add(sample)
        session.commit()
        session.refresh(guest)

        return build_guest_read(session, guest)

    except HTTPException:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        logger.exception("Не удалось создать гостя")
        raise HTTPException(status_code=500, detail="Не удалось создать гостя из-за внутренней ошибки")


@router.patch(
    "/{guest_id}/deactivate",
    dependencies=[Depends(require_roles(*WRITE_ROLES))],
)
def deactivate_guest(guest_id: int, session: Session = Depends(get_session)):
    guest = session.get(Guest, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Гость не найден")

    guest.is_active = False
    guest.valid_until = datetime.now()

    session.add(guest)
    session.commit()
    return {"status": "ok", "message": "Пропуск успешно аннулирован"}




@router.get(
    "/photo/{photo_id}",
    dependencies=[Depends(require_roles(*READ_ROLES))],
)
def get_guest_photo(photo_id: int, session: Session = Depends(get_session)):
    sample = session.get(GuestFaceSample, photo_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return Response(content=sample.photo_data, media_type=sample.mime_type)
