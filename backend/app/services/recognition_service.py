"""Сервис распознавания человека по лицу.

Этот модуль получает embedding лица из кадра камеры или загруженной фотографии и
сравнивает его с сохранёнными embedding-ами сотрудников и активных гостей. Он не
решает вопросы маршрута и не читает видео сам по себе; его задача — сказать,
есть ли в базе подходящий человек, насколько близкое совпадение найдено и какое
решение принять: разрешить автоматически, отправить на проверку или отказать.

Сравнение выполняется через cosine distance: чем меньше расстояние, тем ближе
два биометрических вектора. Пороги подобраны для демонстрационного сценария и
могут настраиваться при дальнейшем развитии системы.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from sqlmodel import Session, select

from app.models.employee_face_samples import EmployeeFaceSample
from app.models.employees import Employee
from app.models.guests import Guest, GuestFaceSample
from app.services.photo_conversion import (
    extract_face_encoding,
    extract_face_encoding_with_bbox_from_bgr,
)

INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW = 0.78
INSIGHTFACE_COSINE_DISTANCE_REVIEW = 0.82


@dataclass(frozen=True)
class FaceRecognitionMatch:
    """Результат сопоставления лица из кадра с базой.

    person хранит найденного сотрудника или гостя, person_type сообщает тип
    найденной сущности, distance показывает близость embedding-ов, decision
    описывает итоговое решение, а face_bbox используется для preview-кадров и
    визуальной проверки распознавания.
    """

    person: Employee | Guest | None
    person_type: str | None
    distance: float | None
    decision: str
    face_bbox: tuple[int, int, int, int] | None = None


def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Рассчитать cosine distance между двумя embedding-векторами.

    Векторы лица сравниваются по направлению, а не по абсолютной длине. Если
    один из векторов нулевой, расстояние считается максимальным, потому что
    сравнить такой embedding корректно нельзя.

    Параметры:
        vec_a: Вектор лица из текущего кадра или фотографии.
        vec_b: Вектор лица из базы данных.

    Возвращает:
        Число от 0 и выше: чем меньше значение, тем выше сходство.
    """

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - np.dot(vec_a / norm_a, vec_b / norm_b))


def _find_best_match_for_vector(vector_a: np.ndarray, session: Session):
    """Найти ближайшего активного сотрудника или гостя для face embedding.

    Сервис сравнивает лицо только с активными сотрудниками и гостями с
    действующим пропуском. Это важно: если гость уже просрочен или сотрудник
    деактивирован, его биометрические данные могут храниться в истории, но не
    должны давать доступ на КПП.

    Параметры:
        vector_a: Embedding лица из текущего кадра.
        session: Сессия БД для чтения образцов лиц и карточек людей.

    Возвращает:
        Кортеж из найденной модели, типа человека и минимального расстояния.
        Если подходящих образцов нет, модель и тип будут None.
    """

    active_emp = set(
        session.exec(select(Employee.id).where(Employee.is_active.is_(True))).all()
    )
    active_guests = set(
        session.exec(
            select(Guest.id).where(
                Guest.is_active.is_(True),
                Guest.valid_until > datetime.now(),
            )
        ).all()
    )

    best_person_id = None
    best_person_type = None
    best_distance = float("inf")

    emp_samples = session.exec(select(EmployeeFaceSample)).all()
    for sample in emp_samples:
        if sample.employee_id not in active_emp or not sample.embedding:
            continue
        vector_b = np.asarray(sample.embedding, dtype=np.float32)
        if vector_a.shape != vector_b.shape:
            continue
        dist = cosine_distance(vector_a, vector_b)
        if dist < best_distance:
            best_distance = dist
            best_person_id = sample.employee_id
            best_person_type = "employee"

    guest_samples = session.exec(select(GuestFaceSample)).all()
    for sample in guest_samples:
        if sample.guest_id not in active_guests or not sample.embedding:
            continue
        vector_b = np.asarray(sample.embedding, dtype=np.float32)
        if vector_a.shape != vector_b.shape:
            continue
        dist = cosine_distance(vector_a, vector_b)
        if dist < best_distance:
            best_distance = dist
            best_person_id = sample.guest_id
            best_person_type = "guest"

    if best_person_id is None:
        return None, None, best_distance if best_distance != float("inf") else None

    if best_person_type == "employee":
        person = session.get(Employee, best_person_id)
    else:
        person = session.get(Guest, best_person_id)

    return person, best_person_type, best_distance


def _build_match(
    person,
    person_type: str | None,
    best_distance: float | None,
    face_bbox: tuple[int, int, int, int] | None = None,
) -> FaceRecognitionMatch:
    """Преобразовать минимальное расстояние в бизнес-решение.

    Если расстояние меньше строгого порога auto_allow, система может считать
    совпадение достаточно уверенным. Если расстояние попало в промежуточную
    зону review, человек найден, но решение лучше показать оператору как
    требующее проверки. Всё, что хуже review-порога, считается отказом.
    """

    if person is None or best_distance is None:
        return FaceRecognitionMatch(
            person=None,
            person_type=None,
            distance=best_distance,
            decision="denied",
            face_bbox=face_bbox,
        )

    if best_distance <= INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW:
        return FaceRecognitionMatch(
            person=person,
            person_type=person_type,
            distance=best_distance,
            decision="auto_allow",
            face_bbox=face_bbox,
        )

    if best_distance <= INSIGHTFACE_COSINE_DISTANCE_REVIEW:
        return FaceRecognitionMatch(
            person=person,
            person_type=person_type,
            distance=best_distance,
            decision="review",
            face_bbox=face_bbox,
        )

    return FaceRecognitionMatch(
        person=None,
        person_type=None,
        distance=best_distance,
        decision="denied",
        face_bbox=face_bbox,
    )


def find_matching_person_in_frame(
    frame_bgr: np.ndarray,
    session: Session,
) -> FaceRecognitionMatch:
    """Распознать человека на BGR-кадре камеры.

    Функция используется видеоанализом и потоками камер. Сначала из кадра
    извлекается лицо через photo_conversion, затем embedding сравнивается с
    базой сотрудников и активных гостей. Если лицо в кадре не найдено, функция
    возвращает denied без ошибки, потому что отсутствие лица — нормальная
    ситуация для видеопотока.

    Параметры:
        frame_bgr: Кадр OpenCV в формате BGR.
        session: Сессия БД с образцами лиц.

    Возвращает:
        FaceRecognitionMatch с найденным человеком, расстоянием, решением и bbox
        лица, если оно было обнаружено.
    """

    try:
        face_vector, face_bbox = extract_face_encoding_with_bbox_from_bgr(frame_bgr)
    except ValueError:
        return FaceRecognitionMatch(
            person=None,
            person_type=None,
            distance=None,
            decision="denied",
            face_bbox=None,
        )

    vector_a = np.asarray(face_vector, dtype=np.float32)
    person, person_type, best_distance = _find_best_match_for_vector(vector_a, session)
    return _build_match(person, person_type, best_distance, face_bbox=face_bbox)


def find_matching_employee(image_bytes: bytes, session: Session):
    """Распознать человека по загруженному изображению.

    Исторически функция называлась employee, но сейчас она может вернуть и
    сотрудника, и гостя. Она используется в сценариях, где на вход приходит не
    видеокадр, а файл изображения: например, проверка snapshot-а камеры.

    Параметры:
        image_bytes: Байты изображения.
        session: Сессия БД.

    Возвращает:
        Кортеж `(person, person_type, distance, decision)`. Если лицо не найдено
        или совпадение слишком слабое, person будет None, а decision — denied.
    """

    try:
        camera_face_vector = extract_face_encoding(image_bytes)
    except ValueError:
        return None, None, None, "denied"

    vector_a = np.asarray(camera_face_vector, dtype=np.float32)
    person, person_type, best_distance = _find_best_match_for_vector(vector_a, session)
    match = _build_match(person, person_type, best_distance)
    return match.person, match.person_type, match.distance, match.decision
