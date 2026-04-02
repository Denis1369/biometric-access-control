from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.models.guests import Guest, GuestFaceSample
from app.services.photo_conversion import extract_face_encoding

router = APIRouter(prefix="/api/guests", tags=["Гости"])

class GuestRead(SQLModel):
    id: int
    last_name: str
    first_name: str
    middle_name: str | None = None
    purpose: str | None = None
    valid_until: datetime
    is_active: bool
    photo_id: int | None = None

@router.get("/", response_model=List[GuestRead])
def get_guests(session: Session = Depends(get_session)):
    guests = session.exec(select(Guest).order_by(Guest.id.desc())).all()
    result = []
    for g in guests:
        sample = session.exec(select(GuestFaceSample).where(GuestFaceSample.guest_id == g.id)).first()
        result.append(GuestRead(
            **g.model_dump(),
            photo_id=sample.id if sample else None
        ))
    return result

@router.post("/", response_model=GuestRead, status_code=status.HTTP_201_CREATED)
async def create_guest(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str | None = Form(None),
    purpose: str | None = Form(None),
    valid_until: datetime = Form(...),
    photo: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    guest = Guest(
        last_name=last_name.strip(),
        first_name=first_name.strip(),
        middle_name=middle_name.strip() if middle_name else None,
        purpose=purpose.strip() if purpose else None,
        valid_until=valid_until,
        is_active=True
    )

    try:
        session.add(guest)
        session.flush()

        image_bytes = await photo.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Фотография пуста")

        try:
            face_vector = extract_face_encoding(image_bytes)
        except Exception:
            raise HTTPException(status_code=400, detail="Не удалось распознать лицо на фото")

        sample = GuestFaceSample(
            guest_id=guest.id,
            mime_type=photo.content_type or "image/jpeg",
            photo_data=image_bytes,
            embedding=face_vector
        )
        session.add(sample)
        session.commit()
        session.refresh(guest)

        return GuestRead(**guest.model_dump(), photo_id=sample.id)

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания гостя: {str(e)}")

@router.patch("/{guest_id}/deactivate")
def deactivate_guest(guest_id: int, session: Session = Depends(get_session)):
    guest = session.get(Guest, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Гость не найден")
        
    guest.is_active = False
    guest.valid_until = datetime.now()
    
    session.add(guest)
    session.commit()
    return {"status": "ok", "message": "Пропуск успешно аннулирован"}

@router.delete("/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guest(guest_id: int, session: Session = Depends(get_session)):
    guest = session.get(Guest, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Гость не найден")
        
    samples = session.exec(select(GuestFaceSample).where(GuestFaceSample.guest_id == guest.id)).all()
    for s in samples:
        session.delete(s)
        
    session.delete(guest)
    session.commit()
    return None

@router.get("/photo/{photo_id}")
def get_guest_photo(photo_id: int, session: Session = Depends(get_session)):
    sample = session.get(GuestFaceSample, photo_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return Response(content=sample.photo_data, media_type=sample.mime_type)