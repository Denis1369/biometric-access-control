from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from app.core.database import get_session
from app.models.cameras import Camera

router = APIRouter(prefix="/api/cameras", tags=["Камеры"])

@router.get(
    "/", 
    response_model=List[Camera],
    summary="Получить список всех камер",
    description="Возвращает список всех зарегистрированных IP/RTSP камер в системе."
)
def get_cameras(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = select(Camera).offset(skip).limit(limit)
    return session.exec(statement).all()

@router.get(
    "/{camera_id}", 
    response_model=Camera,
    summary="Получить камеру по ID",
    description="Возвращает настройки конкретной камеры."
)
def get_camera(camera_id: int, session: Session = Depends(get_session)):
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Камера не найдена")
    return camera

@router.post(
    "/", 
    response_model=Camera, 
    status_code=status.HTTP_201_CREATED,
    summary="Добавить новую камеру",
    description="Регистрирует новую камеру. IP/RTSP адрес должен быть уникальным."
)
def create_camera(camera: Camera, session: Session = Depends(get_session)):
    existing = session.exec(select(Camera).where(Camera.ip_address == camera.ip_address)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Камера с таким адресом уже существует")
        
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return camera

@router.patch(
    "/{camera_id}", 
    response_model=Camera,
    summary="Обновить настройки камеры",
    description="Изменяет параметры камеры, включая возможность её включения/отключения (is_active)."
)
def update_camera(camera_id: int, camera_data: dict, session: Session = Depends(get_session)):
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Камера не найдена")
    
    if "ip_address" in camera_data:
        existing = session.exec(select(Camera).where(Camera.ip_address == camera_data["ip_address"])).first()
        if existing and existing.id != camera_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Камера с таким адресом уже существует")
            
    for key, value in camera_data.items():
        if hasattr(camera, key):
            setattr(camera, key, value)
            
    session.add(camera)
    session.commit()
    session.refresh(camera)
    return camera

@router.delete(
    "/{camera_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить камеру",
    description="Удаляет камеру из системы."
)
def delete_camera(camera_id: int, session: Session = Depends(get_session)):
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Камера не найдена")
        
    session.delete(camera)
    session.commit()
    return None