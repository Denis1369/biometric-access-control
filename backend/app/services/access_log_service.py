"""Сервис подготовки и публикации событий журнала проходов.

AccessLog создаётся разными частями системы: онлайн-анализом камеры, анализом
загруженного видео или демонстрационными данными. Интерфейсу при этом нужен
единый формат строки журнала: id, время, статус, имя человека и камера. Этот
сервис собирает такой payload и публикует новые события в WebSocket-topic, чтобы
проходная обновлялась без перезагрузки страницы.
"""

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
    """Формат события AccessLog, который отдаётся frontend-у."""

    id: int
    timestamp: datetime
    status: str
    employee_name: str | None
    camera_name: str | None


def build_person_name(employee: Employee | None, guest: Guest | None) -> str:
    """Собрать отображаемое имя человека для журнала проходов.

    AccessLog может ссылаться либо на сотрудника, либо на гостя, либо не иметь
    найденного человека вообще. Эта функция приводит все варианты к одной строке
    для интерфейса: ФИО сотрудника, `[Гость] Фамилия Имя` или «Неизвестное
    лицо».
    """

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
    """Преобразовать AccessLog и связанные модели в payload для UI/WebSocket.

    Параметры:
        access_log: Событие прохода из БД.
        employee: Связанный сотрудник, если событие относится к сотруднику.
        guest: Связанный гость, если событие относится к гостю.
        camera: Камера, зафиксировавшая событие.

    Возвращает:
        Словарь, который можно отдать в REST API или отправить по WebSocket.
        Если камера уже удалена, frontend увидит «Удаленная камера», а событие
        останется читаемым в истории.
    """

    return {
        "id": access_log.id or 0,
        "timestamp": access_log.timestamp,
        "status": access_log.status,
        "employee_name": build_person_name(employee, guest),
        "camera_name": camera.name if camera else "Удаленная камера",
    }


def get_recent_access_logs(session: Session, *, skip: int = 0, limit: int = 100) -> list[AccessLogPayload]:
    """Получить последние события проходов в готовом для интерфейса формате.

    limit ограничивается сверху, чтобы случайный запрос не заставил backend
    вернуть слишком большой журнал. Запрос использует outer join, потому что
    историческое событие должно отображаться даже если связанная камера, гость
    или сотрудник позже были удалены.
    """

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
    """Получить один AccessLog для WebSocket-публикации.

    Функция вызывается сразу после создания события. Она повторно читает запись
    из БД вместе со связанными сущностями, чтобы отправить клиентам полный
    человекочитаемый payload, а не только id.
    """

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
    """Опубликовать новое событие прохода в WebSocket-topic.

    Сервис потоков камер может работать в отдельном потоке, поэтому здесь
    открывается короткая новая сессия БД, собирается payload и отправляется в
    TopicWebSocketManager. Если id отсутствует или запись не найдена, публикация
    просто пропускается: это безопаснее, чем ронять поток анализа.
    """

    if access_log_id is None:
        return

    with Session(engine) as session:
        payload = get_access_log_payload(session, access_log_id)

    if payload is not None:
        topic_ws_manager.publish(access_logs_topic(), {"type": "created", "log": payload})
