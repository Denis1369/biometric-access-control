"""API гостевых пропусков.

Модуль создаёт временные пропуска гостей, сохраняет образцы лица, при
необходимости формирует Re-ID вектор полного роста и позволяет оператору
аннулировать пропуск без удаления истории событий.
"""

from datetime import datetime
import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import (
    GUESTS_READ,
    GUESTS_WRITE,
    GUEST_PASSES_CLOSE,
    GUEST_PASSES_ISSUE,
)
from app.models.employees import Employee
from app.models.guests import Guest, GuestFaceSample
from app.services.photo_conversion import extract_face_encoding
from app.services.reid_service import extract_primary_body_embedding_from_image_bytes

router = APIRouter(prefix="/api/guests", tags=["Гости"])
logger = logging.getLogger(__name__)

def _normalize_required_name(value: str, field_name: str) -> str:
    """Проверить обязательное текстовое поле гостя и убрать лишние пробелы.

    ФИО гостя вводит оператор КПП вручную. Пустая фамилия или имя не должны
    попадать в базу, потому что дальше эти данные отображаются в пропуске,
    журнале событий и выборе гостя для построения маршрута.
    """

    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"Поле {field_name} не может быть пустым")
    return normalized


def _normalize_valid_until(value: datetime) -> datetime:
    """Привести дату окончания пропуска к формату, используемому в базе.

    Frontend может прислать datetime с timezone. В базе проекта даты хранятся
    как naive datetime, поэтому значение переводится в локальный вид без
    временной зоны, чтобы сравнения срока действия пропуска работали одинаково.
    """

    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)


async def _read_upload_file(upload: UploadFile | None, empty_detail: str) -> tuple[bytes, str] | None:
    """Прочитать необязательный файл формы гостя.

    При создании пропуска могут прийти фото лица и фото полного роста. Если файл
    не передан, функция возвращает ``None``. Если поле есть, но файл пустой,
    пользователь получает понятную ошибку, потому что биометрические сервисы не
    смогут обработать пустой payload.
    """

    if upload is None:
        return None
    payload = await upload.read()
    if not payload:
        raise HTTPException(status_code=400, detail=empty_detail)
    return payload, upload.content_type or "image/jpeg"


class GuestRead(SQLModel):
    """DTO гостя для списка гостей и модального окна пропуска на frontend."""

    id: int
    last_name: str
    first_name: str
    middle_name: str | None = None
    employee_id: int | None = None
    employee_name: str | None = None
    valid_until: datetime
    is_active: bool
    photo_id: int | None = None
    has_body_embedding: bool = False
    body_embedding_updated_at: datetime | None = None


def build_employee_name(employee: Employee | None) -> str | None:
    """Собрать ФИО сотрудника для отображения в карточке гостя."""
    if not employee:
        return None
    full_name = " ".join(
        part for part in [employee.last_name, employee.first_name, employee.middle_name] if part
    ).strip()
    return full_name or None


def build_guest_read(session: Session, guest: Guest) -> GuestRead:
    """Преобразовать модель Guest в ответ, удобный для frontend."""
    sample = session.exec(select(GuestFaceSample).where(GuestFaceSample.guest_id == guest.id)).first()
    employee = session.get(Employee, guest.employee_id) if guest.employee_id else None
    return GuestRead(
        **guest.model_dump(),
        employee_name=build_employee_name(employee),
        photo_id=sample.id if sample else None,
        has_body_embedding=bool(guest.body_embedding),
    )


@router.get(
    "/",
    response_model=List[GuestRead],
    dependencies=[Depends(require_permissions(GUESTS_READ))],
)
def get_guests(session: Session = Depends(get_session)):
    """Вернуть гостей со статусом пропуска, id фото лица и признаком Re-ID."""
    guests = session.exec(select(Guest).order_by(Guest.id.desc())).all()
    return [build_guest_read(session, guest) for guest in guests]


@router.post(
    "/",
    response_model=GuestRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(GUESTS_WRITE, GUEST_PASSES_ISSUE))],
)
async def create_guest(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str | None = Form(None),
    employee_id: int = Form(...),
    valid_until: datetime = Form(...),
    photo: UploadFile | None = File(None),
    face_photo: UploadFile | None = File(None),
    body_photo: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    """Создать гостевой пропуск из multipart-формы.

    Параметры:
        last_name: обязательная фамилия гостя.
        first_name: обязательное имя гостя.
        middle_name: необязательное отчество.
        employee_id: сотрудник, к которому оформляется визит.
        valid_until: дата и время окончания действия пропуска.
        photo: старое поле изображения для обратной совместимости.
        face_photo: фото лица для создания GuestFaceSample.
        body_photo: фото полного роста для создания ``body_embedding`` Re-ID.
        session: сессия работы с базой данных.
    """
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

        face_upload = face_photo or photo
        explicit_face_upload = face_photo is not None
        face_payload = await _read_upload_file(face_upload, "Фотография лица пуста")
        body_payload = await _read_upload_file(body_photo, "Фотография полного роста пуста")

        if face_payload is None and body_payload is None:
            raise HTTPException(status_code=400, detail="Загрузите фото лица или фото полного роста")

        face_vector = None
        if face_payload is not None:
            face_bytes, face_mime_type = face_payload
            try:
                face_vector = extract_face_encoding(face_bytes)
            except ValueError:
                face_vector = None

            if face_vector is not None:
                sample = GuestFaceSample(
                    guest_id=guest.id,
                    mime_type=face_mime_type,
                    photo_data=face_bytes,
                    embedding=face_vector,
                )
                session.add(sample)
            elif explicit_face_upload or body_payload is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Не удалось распознать лицо на фото лица",
                )

        if body_payload is not None:
            body_bytes, _body_mime_type = body_payload
            body_vector = extract_primary_body_embedding_from_image_bytes(body_bytes)
            if body_vector is None:
                raise HTTPException(
                    status_code=400,
                    detail="Не удалось извлечь Re-ID признаки. Загрузите фото человека в полный рост.",
                )
            guest.body_embedding = body_vector
            guest.body_embedding_updated_at = datetime.now()
            session.add(guest)
        elif face_payload is not None and face_vector is None:
            # Backward compatibility: old clients uploaded one field named "photo",
            # which could be either a face photo or a full-body Re-ID enrollment image.
            face_bytes, _face_mime_type = face_payload
            body_vector = extract_primary_body_embedding_from_image_bytes(face_bytes)
            if body_vector is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Не удалось распознать лицо или полный силуэт на фото. "
                        "Для Re-ID загрузите снимок человека в полный рост."
                    ),
                )
            guest.body_embedding = body_vector
            guest.body_embedding_updated_at = datetime.now()
            session.add(guest)

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


@router.post(
    "/{guest_id}/body-photo",
    response_model=GuestRead,
    dependencies=[Depends(require_permissions(GUESTS_WRITE))],
)
async def upload_guest_body_photo(
    guest_id: int,
    body_photo: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Загрузить или заменить фото полного роста и обновить Re-ID вектор гостя."""
    guest = session.get(Guest, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Гость не найден")

    body_payload = await _read_upload_file(body_photo, "Фотография полного роста пуста")
    if body_payload is None:
        raise HTTPException(status_code=400, detail="Загрузите фото полного роста")

    body_bytes, _mime_type = body_payload
    body_vector = extract_primary_body_embedding_from_image_bytes(body_bytes)
    if body_vector is None:
        raise HTTPException(
            status_code=400,
            detail="Не удалось извлечь Re-ID признаки. Загрузите фото человека в полный рост.",
        )

    guest.body_embedding = body_vector
    guest.body_embedding_updated_at = datetime.now()

    try:
        session.add(guest)
        session.commit()
        session.refresh(guest)
        return build_guest_read(session, guest)
    except Exception:
        session.rollback()
        logger.exception("Не удалось обновить body_embedding гостя")
        raise HTTPException(status_code=500, detail="Не удалось обновить Re-ID фото гостя")


@router.patch(
    "/{guest_id}/deactivate",
    dependencies=[Depends(require_permissions(GUEST_PASSES_CLOSE))],
)
def deactivate_guest(guest_id: int, session: Session = Depends(get_session)):
    """Немедленно закрыть пропуск гостя без удаления исторических журналов."""
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
    dependencies=[Depends(require_permissions(GUESTS_READ))],
)
def get_guest_photo(photo_id: int, session: Session = Depends(get_session)):
    """Вернуть бинарные данные сохранённого фото лица по id GuestFaceSample."""
    sample = session.get(GuestFaceSample, photo_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return Response(content=sample.photo_data, media_type=sample.mime_type)
