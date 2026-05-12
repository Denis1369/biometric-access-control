from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from sqlmodel import Session, select

from app.core.database import engine
from app.models.cameras import Camera
from app.models.employees import Employee
from app.models.guests import Guest
from app.models.logs import AccessLog
from app.services.websocket_manager import access_logs_topic, topic_ws_manager


class AccessLogPayload(TypedDict):
    id: int
    timestamp: datetime
    status: str
    employee_name: str | None
    camera_name: str | None


def build_person_name(employee: Employee | None, guest: Guest | None) -> str:
    if employee:
        return " ".join(
            part
            for part in (employee.last_name, employee.first_name, employee.middle_name)
            if part
        )
    if guest:
        return f"[Гость] {guest.last_name} {guest.first_name}"
    return "Неизвестное лицо"


def build_access_log_payload(
    access_log: AccessLog,
    employee: Employee | None = None,
    guest: Guest | None = None,
    camera: Camera | None = None,
) -> AccessLogPayload:
    return {
        "id": access_log.id or 0,
        "timestamp": access_log.timestamp,
        "status": access_log.status,
        "employee_name": build_person_name(employee, guest),
        "camera_name": camera.name if camera else "Удаленная камера",
    }


def get_recent_access_logs(session: Session, *, skip: int = 0, limit: int = 100) -> list[AccessLogPayload]:
    safe_limit = max(1, min(limit, 200))
    statement = (
        select(AccessLog, Employee, Guest, Camera)
        .join(Employee, AccessLog.employee_id == Employee.id, isouter=True)
        .join(Guest, AccessLog.guest_id == Guest.id, isouter=True)
        .join(Camera, AccessLog.camera_id == Camera.id, isouter=True)
        .order_by(AccessLog.timestamp.desc())
        .offset(max(0, skip))
        .limit(safe_limit)
    )
    return [
        build_access_log_payload(access_log, employee, guest, camera)
        for access_log, employee, guest, camera in session.exec(statement).all()
    ]


def get_access_log_payload(session: Session, access_log_id: int) -> AccessLogPayload | None:
    statement = (
        select(AccessLog, Employee, Guest, Camera)
        .join(Employee, AccessLog.employee_id == Employee.id, isouter=True)
        .join(Guest, AccessLog.guest_id == Guest.id, isouter=True)
        .join(Camera, AccessLog.camera_id == Camera.id, isouter=True)
        .where(AccessLog.id == access_log_id)
    )
    row = session.exec(statement).first()
    if not row:
        return None

    access_log, employee, guest, camera = row
    return build_access_log_payload(access_log, employee, guest, camera)


def publish_access_log_created(access_log_id: int | None) -> None:
    if access_log_id is None:
        return

    with Session(engine) as session:
        payload = get_access_log_payload(session, access_log_id)

    if payload is not None:
        topic_ws_manager.publish(access_logs_topic(), {"type": "created", "log": payload})
