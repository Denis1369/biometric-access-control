import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from sqlmodel import Session, SQLModel, select
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session
from app.models.employees import Employee
from app.models.departments import Department
from app.models.employee_face_samples import EmployeeFaceSample
from app.services.photo_conversion import extract_face_encoding

router = APIRouter(prefix="/api/employees", tags=["Сотрудники"])


class EmployeeFaceSampleRead(SQLModel):
    id: int
    is_primary: bool
    created_at: datetime


class EmployeeListItem(SQLModel):
    id: int
    last_name: str
    first_name: str
    middle_name: str | None = None
    department_id: int | None = None
    is_active: bool


class EmployeeDetail(EmployeeListItem):
    face_samples: list[EmployeeFaceSampleRead] = []


def parse_delete_sample_ids(raw: str | None) -> list[int]:
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delete_sample_ids должен быть JSON-массивом id"
        )

    if not isinstance(data, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delete_sample_ids должен быть списком"
        )

    result = []
    for item in data:
        if not isinstance(item, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="delete_sample_ids должен содержать только целые id"
            )
        result.append(item)

    return result


def build_employee_list_item(employee: Employee) -> EmployeeListItem:
    return EmployeeListItem(
        id=employee.id,
        last_name=employee.last_name,
        first_name=employee.first_name,
        middle_name=employee.middle_name,
        department_id=employee.department_id,
        is_active=employee.is_active
    )


def build_employee_detail(session: Session, employee: Employee) -> EmployeeDetail:
    samples = session.exec(
        select(EmployeeFaceSample)
        .where(EmployeeFaceSample.employee_id == employee.id)
        .order_by(EmployeeFaceSample.is_primary.desc(), EmployeeFaceSample.id.asc())
    ).all()

    return EmployeeDetail(
        id=employee.id,
        last_name=employee.last_name,
        first_name=employee.first_name,
        middle_name=employee.middle_name,
        department_id=employee.department_id,
        is_active=employee.is_active,
        face_samples=[
            EmployeeFaceSampleRead(
                id=sample.id,
                is_primary=sample.is_primary,
                created_at=sample.created_at
            )
            for sample in samples
        ]
    )


@router.get(
    "/",
    response_model=List[EmployeeListItem],
    summary="Получить всех сотрудников",
    description="Получить список всех сотрудников. Поддерживает пагинацию через параметры skip и limit."
)
def get_employees(
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100
):
    statement = select(Employee).offset(skip).limit(limit)
    employees = session.exec(statement).all()
    return [build_employee_list_item(employee) for employee in employees]


@router.get(
    "/{employee_id}",
    response_model=EmployeeDetail,
    summary="Получить сотрудника по ID",
    description="Получить карточку сотрудника вместе с фотографиями лица."
)
def get_employee(employee_id: int, session: Session = Depends(get_session)):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сотрудник не найден"
        )

    return build_employee_detail(session, employee)


@router.get(
    "/face-samples/{sample_id}/photo",
    summary="Получить фотографию лица по id sample",
    description="Возвращает бинарные данные фотографии сотрудника."
)
def get_face_sample_photo(sample_id: int, session: Session = Depends(get_session)):
    sample = session.get(EmployeeFaceSample, sample_id)
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фотография не найдена"
        )

    return Response(content=sample.photo_data, media_type=sample.mime_type)


@router.post(
    "/",
    response_model=EmployeeDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Создать сотрудника с несколькими фото",
    description="Добавить нового сотрудника и сохранить несколько фотографий лица с выбором основной."
)
async def create_employee(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str | None = Form(None),
    department_id: int = Form(...),
    primary_index: int = Form(0),
    photos: list[UploadFile] = File(...),
    session: Session = Depends(get_session)
):
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Отдел с id={department_id} не найден"
        )

    if not photos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нужно загрузить хотя бы одну фотографию"
        )

    if primary_index < 0 or primary_index >= len(photos):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный индекс основной фотографии"
        )

    employee = Employee(
        last_name=last_name.strip(),
        first_name=first_name.strip(),
        middle_name=middle_name.strip() if middle_name else None,
        department_id=department_id,
        is_active=True
    )

    try:
        session.add(employee)
        session.flush()

        created_samples: list[EmployeeFaceSample] = []

        for index, photo in enumerate(photos):
            image_bytes = await photo.read()

            if not image_bytes:
                continue

            try:
                face_vector = extract_face_encoding(image_bytes)
            except HTTPException:
                continue

            sample = EmployeeFaceSample(
                employee_id=employee.id,
                mime_type=photo.content_type or "image/jpeg",
                photo_data=image_bytes,
                embedding=face_vector,
                is_primary=(index == primary_index)
            )
            session.add(sample)
            created_samples.append(sample)

        if not created_samples:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ни на одной из загруженных фотографий не удалось корректно выделить лицо"
            )

        has_primary = any(sample.is_primary for sample in created_samples)
        if not has_primary:
            created_samples[0].is_primary = True

        session.commit()
        session.refresh(employee)

        return build_employee_detail(session, employee)

    except HTTPException:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка целостности данных при создании сотрудника"
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании сотрудника: {str(e)}"
        )


@router.patch(
    "/{employee_id}",
    response_model=EmployeeDetail,
    summary="Обновить данные сотрудника",
    description=(
        "Обновить данные сотрудника. Можно изменить ФИО, отдел, активность, "
        "добавить новые фото, удалить старые и выбрать основную фотографию."
    )
)
async def update_employee(
    employee_id: int,
    last_name: str | None = Form(None),
    first_name: str | None = Form(None),
    middle_name: str | None = Form(None),
    department_id: int | None = Form(None),
    is_active: bool | None = Form(None),
    primary_photo: str | None = Form(None),
    delete_sample_ids: str | None = Form(None),
    photos: list[UploadFile] | None = File(None),
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

    delete_ids = parse_delete_sample_ids(delete_sample_ids)
    new_photos = photos or []

    existing_samples = session.exec(
        select(EmployeeFaceSample).where(EmployeeFaceSample.employee_id == employee.id)
    ).all()

    existing_by_id = {sample.id: sample for sample in existing_samples}

    for sample_id in delete_ids:
        if sample_id not in existing_by_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Фото с id={sample_id} не принадлежит сотруднику"
            )

    primary_existing_id: int | None = None
    primary_new_index: int | None = None

    if primary_photo:
        if primary_photo.startswith("existing:"):
            try:
                primary_existing_id = int(primary_photo.split(":", 1)[1])
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Некорректный формат primary_photo"
                )

            if primary_existing_id not in existing_by_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Указанная основная фотография не найдена"
                )

            if primary_existing_id in delete_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Нельзя сделать основной фотографию, которая помечена на удаление"
                )

        elif primary_photo.startswith("new:"):
            try:
                primary_new_index = int(primary_photo.split(":", 1)[1])
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Некорректный формат primary_photo"
                )

            if primary_new_index < 0 or primary_new_index >= len(new_photos):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Некорректный индекс новой основной фотографии"
                )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="primary_photo должен быть в формате existing:<id> или new:<index>"
            )

    if last_name is not None:
        employee.last_name = last_name.strip()

    if first_name is not None:
        employee.first_name = first_name.strip()

    if middle_name is not None:
        employee.middle_name = middle_name.strip() if middle_name else None

    if department_id is not None:
        employee.department_id = department_id

    if is_active is not None:
        employee.is_active = is_active

    try:
        session.add(employee)
        session.flush()

        old_primary_id = next(
            (sample.id for sample in existing_samples if sample.is_primary and sample.id not in delete_ids),
            None
        )

        for sample_id in delete_ids:
            session.delete(existing_by_id[sample_id])

        remaining_existing_samples = [
            sample for sample in existing_samples if sample.id not in delete_ids
        ]

        new_samples: list[EmployeeFaceSample] = []

        for index, photo in enumerate(new_photos):
            image_bytes = await photo.read()

            if not image_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Файл новой фотографии #{index + 1} пустой"
                )

            try:
                face_vector = extract_face_encoding(image_bytes)
            except HTTPException:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Не удалось выделить лицо на новой фотографии #{index + 1}"
                )

            sample = EmployeeFaceSample(
                employee_id=employee.id,
                mime_type=photo.content_type or "image/jpeg",
                photo_data=image_bytes,
                embedding=face_vector,
                is_primary=False
            )
            session.add(sample)
            new_samples.append(sample)

        session.flush()

        final_samples = remaining_existing_samples + new_samples

        if employee.is_active and len(final_samples) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="У активного сотрудника должна быть хотя бы одна фотография лица"
            )

        for sample in final_samples:
            sample.is_primary = False

        target_primary = None

        if primary_existing_id is not None:
            target_primary = next(
                (sample for sample in final_samples if sample.id == primary_existing_id),
                None
            )

        elif primary_new_index is not None:
            if 0 <= primary_new_index < len(new_samples):
                target_primary = new_samples[primary_new_index]

        elif old_primary_id is not None:
            target_primary = next(
                (sample for sample in final_samples if sample.id == old_primary_id),
                None
            )

        elif final_samples:
            target_primary = final_samples[0]

        if target_primary is not None:
            target_primary.is_primary = True

        session.commit()
        session.refresh(employee)

        return build_employee_detail(session, employee)

    except HTTPException:
        session.rollback()
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка целостности данных при обновлении сотрудника"
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении сотрудника: {str(e)}"
        )


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить сотрудника",
    description="Полностью удалить сотрудника и все связанные фотографии лица."
)
def delete_employee(employee_id: int, session: Session = Depends(get_session)):
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сотрудник не найден"
        )

    samples = session.exec(
        select(EmployeeFaceSample).where(EmployeeFaceSample.employee_id == employee.id)
    ).all()

    for sample in samples:
        session.delete(sample)

    session.delete(employee)
    session.commit()
    return None