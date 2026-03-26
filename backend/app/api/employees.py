from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from typing import List

from app.core.database import get_session
from app.models.employees import Employee
from app.services.photo_conversion import extract_face_encoding
from app.models.departments import Department
from app.models.employee_face_samples import EmployeeFaceSample

router = APIRouter(prefix="/api/employees", tags=["Сотрудники"])

@router.get(
    "/", 
    response_model=List[Employee],
    summary="Получить всех сотрудников",
    description="Получить список всех сотрудников. Поддерживает пагинацию через параметры skip и limit."
)
def get_employees(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = select(Employee).offset(skip).limit(limit)
    return session.exec(statement).all()

@router.get(
    "/{employee_id}", 
    response_model=Employee,
    summary="Получить сотрудника по ID",
    description="Получить карточку конкретного сотрудника по его уникальному идентификатору."
)
def get_employee(employee_id: int, session: Session = Depends(get_session)):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    return employee

@router.post(
    "/",
    response_model=Employee,
    status_code=status.HTTP_201_CREATED,
    summary="Создать сотрудника с фото",
    description="Добавить нового сотрудника. Фотография загружается как файл, сервер находит лицо и сохраняет фото и эмбеддинг отдельно."
)
async def create_employee(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str | None = Form(None),
    department_id: int = Form(...),
    photo: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Отдел с id={department_id} не найден"
        )

    image_bytes = await photo.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл фотографии пустой"
        )

    face_vector = extract_face_encoding(image_bytes)

    employee = Employee(
        last_name=last_name,
        first_name=first_name,
        middle_name=middle_name,
        department_id=department_id,
        is_active=True
    )

    try:
        session.add(employee)
        session.commit()
        session.refresh(employee)

        face_sample = EmployeeFaceSample(
            employee_id=employee.id,
            mime_type=photo.content_type or "image/jpeg",
            photo_data=image_bytes,
            embedding=face_vector,
            is_primary=True
        )

        session.add(face_sample)
        session.commit()
        session.refresh(employee)

        return employee

    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка целостности данных при создании сотрудника"
        )
    except Exception:
        session.rollback()
        raise

@router.patch(
    "/{employee_id}",
    response_model=Employee,
    summary="Обновить данные сотрудника",
    description="Обновить данные сотрудника. Можно отправить новые ФИО, отдел, активность и новую фотографию."
)
async def update_employee(
    employee_id: int,
    last_name: str | None = Form(None),
    first_name: str | None = Form(None),
    middle_name: str | None = Form(None),
    department_id: int | None = Form(None),
    is_active: bool | None = Form(None),
    photo: UploadFile | None = File(None),
    session: Session = Depends(get_session)
):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сотрудник не найден"
        )

    if department_id is not None:
        department = session.get(Department, department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Отдел с id={department_id} не найден"
            )
        employee.department_id = department_id

    if last_name is not None:
        employee.last_name = last_name

    if first_name is not None:
        employee.first_name = first_name

    if middle_name is not None:
        employee.middle_name = middle_name

    if is_active is not None:
        employee.is_active = is_active

    try:
        session.add(employee)
        session.commit()
        session.refresh(employee)

        if photo is not None:
            image_bytes = await photo.read()
            if not image_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Файл фотографии пустой"
                )

            face_vector = extract_face_encoding(image_bytes)

            statement = select(EmployeeFaceSample).where(
                EmployeeFaceSample.employee_id == employee.id,
                EmployeeFaceSample.is_primary == True
            )
            old_primary_samples = session.exec(statement).all()

            for sample in old_primary_samples:
                sample.is_primary = False
                session.add(sample)

            new_face_sample = EmployeeFaceSample(
                employee_id=employee.id,
                mime_type=photo.content_type or "image/jpeg",
                photo_data=image_bytes,
                embedding=face_vector,
                is_primary=True
            )

            session.add(new_face_sample)
            session.commit()

        session.refresh(employee)
        return employee

    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка целостности данных при обновлении сотрудника"
        )
    except Exception:
        session.rollback()
        raise

@router.delete(
    "/{employee_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить сотрудника",
    description="Полностью удалить сотрудника и его биометрический вектор из базы данных."
)
def delete_employee(employee_id: int, session: Session = Depends(get_session)):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
        
    session.delete(employee)
    session.commit()
    return None