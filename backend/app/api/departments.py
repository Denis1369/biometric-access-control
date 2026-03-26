from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from app.core.database import get_session
from app.models.departments import Department

router = APIRouter(prefix="/api/departments", tags=["Отделы"])

@router.get(
    "/", 
    response_model=List[Department],
    summary="Получить список всех отделов",
    description="Возвращает полный список отделов компании для выпадающих списков на фронтенде."
)
def get_departments(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = select(Department).offset(skip).limit(limit)
    return session.exec(statement).all()

@router.get(
    "/{department_id}", 
    response_model=Department,
    summary="Получить отдел по ID",
    description="Возвращает информацию о конкретном отделе."
)
def get_department(department_id: int, session: Session = Depends(get_session)):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")
    return department

@router.post(
    "/", 
    response_model=Department, 
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый отдел",
    description="Добавляет новый отдел в структуру компании."
)
def create_department(department: Department, session: Session = Depends(get_session)):
    existing = session.exec(select(Department).where(Department.name == department.name)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отдел с таким названием уже существует")
        
    session.add(department)
    session.commit()
    session.refresh(department)
    return department

@router.patch(
    "/{department_id}", 
    response_model=Department,
    summary="Обновить название отдела",
    description="Изменяет данные существующего отдела."
)
def update_department(department_id: int, department_data: dict, session: Session = Depends(get_session)):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")
    
    if "name" in department_data:
        existing = session.exec(select(Department).where(Department.name == department_data["name"])).first()
        if existing and existing.id != department_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отдел с таким названием уже существует")
        department.name = department_data["name"]
            
    session.add(department)
    session.commit()
    session.refresh(department)
    return department

@router.delete(
    "/{department_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить отдел",
    description="Удаляет отдел из базы данных. Если к отделу привязаны сотрудники, возникнет ошибка целостности."
)
def delete_department(department_id: int, session: Session = Depends(get_session)):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")
        
    session.delete(department)
    session.commit()
    return None