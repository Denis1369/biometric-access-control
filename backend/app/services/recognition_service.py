import numpy as np
from datetime import datetime
from sqlmodel import Session, select

from app.models.employee_face_samples import EmployeeFaceSample
from app.models.employees import Employee
from app.models.guests import GuestFaceSample, Guest
from app.services.photo_conversion import extract_face_encoding

INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW = 0.78
INSIGHTFACE_COSINE_DISTANCE_REVIEW = 0.82

def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0: return 1.0
    return float(1.0 - np.dot(vec_a / norm_a, vec_b / norm_b))

def _find_best_match_for_vector(vector_a: np.ndarray, session: Session):
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
        if sample.employee_id not in active_emp or not sample.embedding: continue
        vector_b = np.asarray(sample.embedding, dtype=np.float32)
        if vector_a.shape != vector_b.shape: continue
        dist = cosine_distance(vector_a, vector_b)
        if dist < best_distance:
            best_distance = dist
            best_person_id = sample.employee_id
            best_person_type = "employee"

    guest_samples = session.exec(select(GuestFaceSample)).all()
    for sample in guest_samples:
        if sample.guest_id not in active_guests or not sample.embedding: continue
        vector_b = np.asarray(sample.embedding, dtype=np.float32)
        if vector_a.shape != vector_b.shape: continue
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

def find_matching_employee(image_bytes: bytes, session: Session):
    try:
        camera_face_vector = extract_face_encoding(image_bytes)
    except Exception:
        return None, None, None, "denied"

    vector_a = np.asarray(camera_face_vector, dtype=np.float32)
    person, person_type, best_distance = _find_best_match_for_vector(vector_a, session)

    if person is None or best_distance is None:
        return None, None, best_distance, "denied"

    if best_distance <= INSIGHTFACE_COSINE_DISTANCE_AUTO_ALLOW:
        return person, person_type, best_distance, "auto_allow"

    if best_distance <= INSIGHTFACE_COSINE_DISTANCE_REVIEW:
        return person, person_type, best_distance, "review"

    return None, None, best_distance, "denied"
