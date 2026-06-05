"""API сотрудников и их биометрических образцов лица.

Этот router обслуживает HR-сценарии: просмотр сотрудников, создание карточки,
загрузка нескольких фотографий лица, выбор основной фотографии и обновление
данных сотрудника. Биометрические признаки извлекаются сразу при сохранении
фотографий, чтобы позже поток камер мог быстро сравнивать лицо с готовыми
embedding-векторами из базы.
"""

import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, Session, select

from app.core.database import get_session
from app.core.deps import require_any_permission, require_permissions
from app.core.permissions import EMPLOYEES_LOOKUP, EMPLOYEES_READ, EMPLOYEES_WRITE
from app.models.departments import Department
from app.models.employee_face_samples import EmployeeFaceSample
from app.models.employees import Employee
from app.services.photo_conversion import extract_face_encoding

router = APIRouter(prefix="/api/employees", tags=["Сотрудники"])
logger = logging.getLogger(__name__)

class EmployeeFaceSampleRead(SQLModel):
    """Краткая информация о сохранённом образце лица сотрудника."""

    id: int
    is_primary: bool
    created_at: datetime


class EmployeeListItem(SQLModel):
    """Упрощённая карточка сотрудника для списка.

    Список не возвращает сами фотографии и embedding-векторы, потому что это
    тяжёлые данные. Для отображения аватара frontend получает только id основной
    фотографии и при необходимости загружает изображение отдельным запросом.
    """

    id: int
    last_name: str
    first_name: str
    middle_name: str | None = None
    position: str | None = None
    department_id: int | None = None
    is_active: bool
    primary_sample_id: int | None = None


class EmployeeDetail(EmployeeListItem):
    """Полная карточка сотрудника вместе со списком образцов лица."""

    face_samples: list[EmployeeFaceSampleRead] = Field(default_factory=list)


def _normalize_required_text(value: str, field_name: str) -> str:
    """Очистить обязательное текстовое поле и запретить пустую строку.

    Проверка дублирует frontend-валидацию намеренно: пользователь может отправить
    запрос не через интерфейс, а база не должна получать пустые ФИО.
    """
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Поле {field_name} не может быть пустым",
        )
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    """Очистить необязательное текстовое поле.

    Если пользователь ввёл только пробелы, поле считается отсутствующим и в базе
    сохраняется `NULL`, а не строка с невидимыми символами.
    """
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def parse_delete_sample_ids(raw: str | None) -> list[int]:
    """Разобрать JSON-список id фотографий, которые нужно удалить.

    Форма сотрудника отправляет multipart-запрос: вместе с текстовыми полями и
    новыми файлами может прийти строковое поле `delete_sample_ids`. Здесь оно
    проверяется как JSON-массив целых id, чтобы случайная строка не удалила
    неверные биометрические образцы.
    """
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delete_sample_ids должен быть JSON-массивом id",
        )

    if not isinstance(data, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="delete_sample_ids должен быть списком",
        )

    result = []
    for item in data:
        if not isinstance(item, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="delete_sample_ids должен содержать только целые id",
            )
        result.append(item)
    return result



def build_employee_list_item(session: Session, employee: Employee) -> EmployeeListItem:
    """Собрать лёгкое представление сотрудника для списка.

    Функция выбирает основную фотографию, но не отдаёт бинарные данные. Такой
    подход ускоряет загрузку списка: карточки получают только метаданные, а фото
    запрашивается отдельно, когда оно действительно нужно для отображения.
    """
    sample = session.exec(
        select(EmployeeFaceSample)
        .where(EmployeeFaceSample.employee_id == employee.id)
        .order_by(EmployeeFaceSample.is_primary.desc(), EmployeeFaceSample.id.asc())
    ).first()

    return EmployeeListItem(
        id=employee.id,
        last_name=employee.last_name,
        first_name=employee.first_name,
        middle_name=employee.middle_name,
        position=employee.position,
        department_id=employee.department_id,
        is_active=employee.is_active,
        primary_sample_id=sample.id if sample else None,
    )



def build_employee_detail(session: Session, employee: Employee) -> EmployeeDetail:
    """Собрать полную карточку сотрудника для формы редактирования.

    В отличие от списка, детальная карточка содержит все сохранённые образцы
    лица. Frontend показывает их оператору/HR, позволяет выбрать основную
    фотографию, добавить новые изображения или удалить старые образцы.
    """
    samples = session.exec(
        select(EmployeeFaceSample)
        .where(EmployeeFaceSample.employee_id == employee.id)
        .order_by(EmployeeFaceSample.is_primary.desc(), EmployeeFaceSample.id.asc())
    ).all()
    primary_id = samples[0].id if samples else None

    return EmployeeDetail(
        id=employee.id,
        last_name=employee.last_name,
        first_name=employee.first_name,
        middle_name=employee.middle_name,
        position=employee.position,
        department_id=employee.department_id,
        is_active=employee.is_active,
        primary_sample_id=primary_id,
        face_samples=[
            EmployeeFaceSampleRead(
                id=sample.id,
                is_primary=sample.is_primary,
                created_at=sample.created_at,
            )
            for sample in samples
        ],
    )


@router.get(
    "/",
    response_model=List[EmployeeListItem],
    dependencies=[Depends(require_any_permission(EMPLOYEES_READ, EMPLOYEES_LOOKUP))],
)
def get_employees(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    """Вернуть список сотрудников для HR-раздела и связанных выпадающих списков."""
    statement = select(Employee).offset(skip).limit(limit)
    employees = session.exec(statement).all()
    return [build_employee_list_item(session, employee) for employee in employees]


@router.get(
    "/{employee_id}",
    response_model=EmployeeDetail,
    dependencies=[Depends(require_permissions(EMPLOYEES_READ))],
)
def get_employee(employee_id: int, session: Session = Depends(get_session)):
    """Вернуть полную карточку сотрудника по id."""
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    return build_employee_detail(session, employee)


@router.get(
    "/face-samples/{sample_id}/photo",
    dependencies=[Depends(require_permissions(EMPLOYEES_READ))],
)
def get_face_sample_photo(sample_id: int, session: Session = Depends(get_session)):
    """Вернуть бинарное изображение сохранённого образца лица сотрудника."""
    sample = session.get(EmployeeFaceSample, sample_id)
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Фотография не найдена")
    return Response(content=sample.photo_data, media_type=sample.mime_type)


@router.post(
    "/",
    response_model=EmployeeDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(EMPLOYEES_WRITE))],
)
async def create_employee(
    last_name: str = Form(...),
    first_name: str = Form(...),
    middle_name: str | None = Form(None),
    position: str | None = Form(None),
    department_id: int = Form(...),
    primary_index: int = Form(0),
    photos: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
):
    """Создать сотрудника и сохранить его фотографии лица.

    Endpoint принимает multipart-форму, потому что вместе с ФИО и отделом нужно
    отправить один или несколько файлов. Для каждой фотографии backend пытается
    найти лицо и извлечь embedding. Фото без подходящего лица пропускаются, но
    если ни одно изображение не дало embedding, сотрудник не создаётся как
    биометрически пригодная запись.
    """
    department = session.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Отдел с id={department_id} не найден")

    if not photos:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно загрузить хотя бы одну фотографию")

    if primary_index < 0 or primary_index >= len(photos):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный индекс основной фотографии")

    employee = Employee(
        last_name=_normalize_required_text(last_name, "last_name"),
        first_name=_normalize_required_text(first_name, "first_name"),
        middle_name=_normalize_optional_text(middle_name),
        position=_normalize_optional_text(position),
        department_id=department_id,
        is_active=True,
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
            except ValueError:
                continue

            sample = EmployeeFaceSample(
                employee_id=employee.id,
                mime_type=photo.content_type or "image/jpeg",
                photo_data=image_bytes,
                embedding=face_vector,
                is_primary=(index == primary_index),
            )
            session.add(sample)
            created_samples.append(sample)

        if not created_samples:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ни на одной из загруженных фотографий не удалось корректно выделить лицо",
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
            detail="Ошибка целостности данных при создании сотрудника",
        )
    except Exception:
        session.rollback()
        logger.exception("Не удалось создать сотрудника")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать сотрудника из-за внутренней ошибки",
        )


@router.patch(
    "/{employee_id}",
    response_model=EmployeeDetail,
    dependencies=[Depends(require_permissions(EMPLOYEES_WRITE))],
)
async def update_employee(
    employee_id: int,
    last_name: str | None = Form(None),
    first_name: str | None = Form(None),
    middle_name: str | None = Form(None),
    position: str | None = Form(None),
    department_id: int | None = Form(None),
    is_active: bool | None = Form(None),
    primary_photo: str | None = Form(None),
    delete_sample_ids: str | None = Form(None),
    photos: list[UploadFile] | None = File(None),
    session: Session = Depends(get_session),
):
    """Обновить карточку сотрудника и при необходимости добавить новые фото лица.

    Endpoint принимает multipart-форму, потому что редактирование может включать
    текстовые поля и новые изображения. Поле `primary_photo` — это договор между
    frontend и backend: значение `existing:<id>` означает, что основной нужно
    сделать уже сохранённый образец, а `new:<index>` — одну из новых фотографий,
    переданных в текущем запросе.

    Удаление фотографий сейчас намеренно отключено: история биометрических
    образцов важна для стабильности распознавания, поэтому на этом этапе можно
    добавлять новые образцы и менять основной, но нельзя случайно удалить старые.
    """
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")

    if department_id is not None:
        department = session.get(Department, department_id)
        if not department:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Отдел с id={department_id} не найден")

    delete_ids = parse_delete_sample_ids(delete_sample_ids)
    if delete_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Удаление фотографий отключено на текущем этапе",
        )

    new_photos = photos or []
    existing_samples = session.exec(select(EmployeeFaceSample).where(EmployeeFaceSample.employee_id == employee.id)).all()
    existing_by_id = {sample.id: sample for sample in existing_samples}

    primary_existing_id: int | None = None
    primary_new_index: int | None = None

    if primary_photo:
        if primary_photo.startswith("existing:"):
            try:
                primary_existing_id = int(primary_photo.split(":", 1)[1])
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный формат primary_photo")
            if primary_existing_id not in existing_by_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Указанная основная фотография не найдена")
        elif primary_photo.startswith("new:"):
            try:
                primary_new_index = int(primary_photo.split(":", 1)[1])
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный формат primary_photo")
            if primary_new_index < 0 or primary_new_index >= len(new_photos):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Некорректный индекс новой основной фотографии",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="primary_photo должен быть в формате existing: или new:",
            )

    if last_name is not None:
        employee.last_name = _normalize_required_text(last_name, "last_name")
    if first_name is not None:
        employee.first_name = _normalize_required_text(first_name, "first_name")
    if middle_name is not None:
        employee.middle_name = _normalize_optional_text(middle_name)
    if position is not None:
        employee.position = _normalize_optional_text(position)
    if department_id is not None:
        employee.department_id = department_id
    if is_active is not None:
        employee.is_active = is_active

    try:
        session.add(employee)
        session.flush()

        old_primary_id = next(
            (sample.id for sample in existing_samples if sample.is_primary),
            None,
        )

        remaining_existing_samples = list(existing_samples)
        new_samples: list[EmployeeFaceSample] = []

        for index, photo in enumerate(new_photos):
            image_bytes = await photo.read()
            if not image_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Файл новой фотографии #{index + 1} пустой",
                )

            try:
                face_vector = extract_face_encoding(image_bytes)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Не удалось выделить лицо на новой фотографии #{index + 1}",
                )

            sample = EmployeeFaceSample(
                employee_id=employee.id,
                mime_type=photo.content_type or "image/jpeg",
                photo_data=image_bytes,
                embedding=face_vector,
                is_primary=False,
            )
            session.add(sample)
            new_samples.append(sample)

        session.flush()

        final_samples = remaining_existing_samples + new_samples
        if employee.is_active and len(final_samples) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="У активного сотрудника должна быть хотя бы одна фотография лица",
            )

        for sample in final_samples:
            sample.is_primary = False

        target_primary = None
        if primary_existing_id is not None:
            target_primary = next((sample for sample in final_samples if sample.id == primary_existing_id), None)
        elif primary_new_index is not None:
            if 0 <= primary_new_index < len(new_samples):
                target_primary = new_samples[primary_new_index]
        elif old_primary_id is not None:
            target_primary = next((sample for sample in final_samples if sample.id == old_primary_id), None)
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
            detail="Ошибка целостности данных при обновлении сотрудника",
        )
    except Exception:
        session.rollback()
        logger.exception("Не удалось обновить сотрудника %s", employee_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось обновить сотрудника из-за внутренней ошибки",
        )
