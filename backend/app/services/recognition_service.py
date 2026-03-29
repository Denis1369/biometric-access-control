import numpy as np
from sqlmodel import Session, select

from app.models.employee_face_samples import EmployeeFaceSample
from app.models.employees import Employee
from app.models.logs import AccessLog
from app.services.photo_conversion import extract_face_encoding

INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW = 0.70
INSIGHTFACE_COSINE_DISTANCE_REVIEW = 0.72
INSIGHTFACE_REVIEW_HITS_REQUIRED = 2


def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 1.0

    vec_a = vec_a / norm_a
    vec_b = vec_b / norm_b
    return float(1.0 - np.dot(vec_a, vec_b))


def _get_active_employee_ids(session: Session) -> set[int]:
    return set(
        session.exec(
            select(Employee.id).where(Employee.is_active == True)
        ).all()
    )


def _find_best_match_for_vector(
    vector_a: np.ndarray,
    session: Session,
) -> tuple[Employee | None, float | None]:
    active_employee_ids = _get_active_employee_ids(session)
    if not active_employee_ids:
        return None, None

    samples = session.exec(select(EmployeeFaceSample)).all()

    best_employee_id = None
    best_distance = float("inf")

    for sample in samples:
        if sample.employee_id not in active_employee_ids:
            continue

        if not sample.embedding:
            continue

        vector_b = np.asarray(sample.embedding, dtype=np.float32)

        if vector_a.shape != vector_b.shape:
            continue

        distance = cosine_distance(vector_a, vector_b)

        if distance < best_distance:
            best_distance = distance
            best_employee_id = sample.employee_id

    if best_employee_id is None:
        return None, None

    employee = session.get(Employee, best_employee_id)
    if not employee or not employee.is_active:
        return None, best_distance if best_distance != float("inf") else None

    return employee, best_distance


def find_matching_employee(
    image_bytes: bytes,
    session: Session,
) -> tuple[Employee | None, float | None, str]:
    try:
        camera_face_vector = extract_face_encoding(image_bytes)
    except Exception:
        return None, None, "denied"

    vector_a = np.asarray(camera_face_vector, dtype=np.float32)
    employee, best_distance = _find_best_match_for_vector(vector_a, session)

    if employee is None:
        return None, best_distance, "denied"

    if best_distance is None:
        return None, None, "denied"

    if best_distance <= INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW:
        return employee, best_distance, "auto_allow"

    if best_distance <= INSIGHTFACE_COSINE_DISTANCE_REVIEW:
        return employee, best_distance, "review"

    return None, best_distance, "denied"


def find_matching_employee_multi_frame(
    images_bytes_list: list[bytes],
    session: Session,
    review_hits_required: int = INSIGHTFACE_REVIEW_HITS_REQUIRED,
) -> tuple[Employee | None, float | None, str, dict]:
    frame_results: list[dict] = []

    for image_bytes in images_bytes_list:
        employee, distance, decision = find_matching_employee(image_bytes, session)
        frame_results.append({
            "employee_id": employee.id if employee else None,
            "distance": distance,
            "decision": decision,
        })

    # 1) Если есть хотя бы один очень сильный кадр -> сразу пускаем
    auto_allow_candidates = [
        fr for fr in frame_results
        if fr["employee_id"] is not None
        and fr["distance"] is not None
        and fr["distance"] <= INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW
    ]

    if auto_allow_candidates:
        best = min(auto_allow_candidates, key=lambda x: x["distance"])
        employee = session.get(Employee, best["employee_id"])
        return employee, best["distance"], "auto_allow", {
            "frames_total": len(images_bytes_list),
            "review_hits_required": review_hits_required,
            "frame_results": frame_results,
        }

    review_hits_by_employee: dict[int, list[float]] = {}

    for fr in frame_results:
        employee_id = fr["employee_id"]
        distance = fr["distance"]

        if employee_id is None or distance is None:
            continue

        if distance <= INSIGHTFACE_COSINE_DISTANCE_REVIEW:
            review_hits_by_employee.setdefault(employee_id, []).append(distance)

    confirmed_employee_id = None
    confirmed_best_distance = None
    confirmed_hits = 0

    for employee_id, distances in review_hits_by_employee.items():
        hits = len(distances)
        if hits >= review_hits_required:
            best_distance = min(distances)

            if (
                confirmed_employee_id is None
                or hits > confirmed_hits
                or (hits == confirmed_hits and best_distance < confirmed_best_distance)
            ):
                confirmed_employee_id = employee_id
                confirmed_best_distance = best_distance
                confirmed_hits = hits

    if confirmed_employee_id is not None:
        employee = session.get(Employee, confirmed_employee_id)
        if employee and employee.is_active:
            return employee, confirmed_best_distance, "review_confirmed", {
                "frames_total": len(images_bytes_list),
                "review_hits_required": review_hits_required,
                "confirmed_hits": confirmed_hits,
                "frame_results": frame_results,
            }

    valid_distances = [fr["distance"] for fr in frame_results if fr["distance"] is not None]
    best_distance = min(valid_distances) if valid_distances else None

    return None, best_distance, "denied", {
        "frames_total": len(images_bytes_list),
        "review_hits_required": review_hits_required,
        "frame_results": frame_results,
    }


def process_access_request(image_bytes: bytes, camera_id: int, session: Session) -> dict:
    """
    Однокадровая логика:
    пропуск только по auto_allow.
    review на одном кадре НЕ пускает.
    """
    employee, distance, decision = find_matching_employee(image_bytes, session)

    if employee and decision == "auto_allow":
        status = "granted"
        message = f"Доступ разрешен: {employee.last_name} {employee.first_name}"
        employee_id = employee.id
    elif employee and decision == "review":
        status = "denied"
        message = "Недостаточно уверенности по одному кадру, требуется подтверждение несколькими кадрами"
        employee_id = None
    else:
        status = "denied"
        message = "Доступ запрещен: Лицо не распознано"
        employee_id = None

    access_log = AccessLog(
        employee_id=employee_id,
        camera_id=camera_id,
        status=status
    )
    session.add(access_log)
    session.commit()

    return {
        "status": status,
        "message": message,
        "employee_id": employee_id,
        "distance": distance,
        "decision": decision,
    }


def process_access_request_multi_frame(
    images_bytes_list: list[bytes],
    camera_id: int,
    session: Session,
    review_hits_required: int = INSIGHTFACE_REVIEW_HITS_REQUIRED,
) -> dict:
    """
    Многокадровая логика:
    <= 0.70 на любом кадре -> пропуск
    <= 0.72 на нескольких кадрах одного сотрудника -> пропуск
    """
    employee, distance, decision, details = find_matching_employee_multi_frame(
        images_bytes_list=images_bytes_list,
        session=session,
        review_hits_required=review_hits_required,
    )

    if employee and decision in {"auto_allow", "review_confirmed"}:
        status = "granted"
        message = f"Доступ разрешен: {employee.last_name} {employee.first_name}"
        employee_id = employee.id
    else:
        status = "denied"
        message = "Доступ запрещен: Лицо не распознано"
        employee_id = None

    access_log = AccessLog(
        employee_id=employee_id,
        camera_id=camera_id,
        status=status
    )
    session.add(access_log)
    session.commit()

    return {
        "status": status,
        "message": message,
        "employee_id": employee_id,
        "distance": distance,
        "decision": decision,
        "details": details,
    }