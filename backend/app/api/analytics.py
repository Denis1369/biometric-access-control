from calendar import monthrange
from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.cameras import Camera
from app.models.departments import Department
from app.models.employees import Employee
from app.models.guests import Guest
from app.models.logs import AccessLog, TrackingLog
from app.models.user import UserRole

router = APIRouter(prefix="/api/analytics", tags=["Аналитика и Журналы"])

BASIC_ANALYTICS_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
    UserRole.MANAGER_ANALYST,
)
FULL_ANALYTICS_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.MANAGER_ANALYST,
)


class AccessLogResponse(BaseModel):
    id: int
    timestamp: datetime
    status: str
    employee_name: str | None
    camera_name: str | None


class TrackingLogResponse(BaseModel):
    id: int
    timestamp: datetime
    confidence: float
    employee_name: str | None
    camera_name: str | None


class DashboardStatsResponse(BaseModel):
    total_employees: int
    active_cameras: int
    accesses_today: int


@router.get(
    "/access-logs",
    response_model=List[AccessLogResponse],
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_access_logs(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = (
        select(AccessLog, Employee, Guest, Camera)
        .join(Employee, AccessLog.employee_id == Employee.id, isouter=True)
        .join(Guest, AccessLog.guest_id == Guest.id, isouter=True)
        .join(Camera, AccessLog.camera_id == Camera.id, isouter=True)
        .order_by(AccessLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )

    results = session.exec(statement).all()

    response_data = []
    for access_log, employee, guest, camera in results:
        if employee:
            full_name = f"{employee.last_name} {employee.first_name}"
            if employee.middle_name:
                full_name += f" {employee.middle_name}"
        elif guest:
            full_name = f"[Гость] {guest.last_name} {guest.first_name}"
        else:
            full_name = "Неизвестное лицо"

        response_data.append(
            AccessLogResponse(
                id=access_log.id,
                timestamp=access_log.timestamp,
                status=access_log.status,
                employee_name=full_name,
                camera_name=camera.name if camera else "Удаленная камера",
            )
        )
    return response_data


@router.get(
    "/tracking-logs",
    response_model=List[TrackingLogResponse],
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_tracking_logs(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = (
        select(TrackingLog, Employee, Guest, Camera)
        .join(Employee, TrackingLog.employee_id == Employee.id, isouter=True)
        .join(Guest, TrackingLog.guest_id == Guest.id, isouter=True)
        .join(Camera, TrackingLog.camera_id == Camera.id, isouter=True)
        .order_by(TrackingLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )

    results = session.exec(statement).all()
    response_data = []
    for tracking_log, employee, guest, camera in results:
        if employee:
            full_name = f"{employee.last_name} {employee.first_name}"
        elif guest:
            full_name = f"[Гость] {guest.last_name} {guest.first_name}"
        else:
            full_name = "Неизвестное лицо"

        response_data.append(
            TrackingLogResponse(
                id=tracking_log.id,
                timestamp=tracking_log.timestamp,
                confidence=tracking_log.confidence,
                employee_name=full_name,
                camera_name=camera.name if camera else "Неизвестно",
            )
        )
    return response_data


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_dashboard_stats(target_date: str | None = None, session: Session = Depends(get_session)):
    total_employees = session.exec(select(func.count(Employee.id))).one()
    active_cameras = session.exec(select(func.count(Camera.id)).where(Camera.is_active == True)).one()

    if target_date:
        try:
            query_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    accesses_today = session.exec(
        select(func.count(AccessLog.id)).where(func.date(AccessLog.timestamp) == query_date)
    ).one()

    return DashboardStatsResponse(
        total_employees=total_employees,
        active_cameras=active_cameras,
        accesses_today=accesses_today,
    )


@router.get(
    "/daily-chart",
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_daily_chart(target_date: str | None = None, session: Session = Depends(get_session)):
    if target_date:
        try:
            query_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    statement = (
        select(
            func.extract("hour", AccessLog.timestamp).label("hour"),
            func.count(AccessLog.id).label("count"),
        )
        .where(func.date(AccessLog.timestamp) == query_date)
        .group_by(func.extract("hour", AccessLog.timestamp))
        .order_by(func.extract("hour", AccessLog.timestamp))
    )
    results = session.exec(statement).all()

    data_dict = {f"{i:02d}:00": 0 for i in range(24)}
    for row in results:
        hour = int(row.hour)
        data_dict[f"{hour:02d}:00"] = row.count

    return {"labels": list(data_dict.keys()), "data": list(data_dict.values())}


@router.get(
    "/monthly-department-chart",
    dependencies=[Depends(require_roles(*FULL_ANALYTICS_ROLES))],
)
def get_monthly_department_chart(session: Session = Depends(get_session)):
    today = date.today()
    statement = (
        select(Department.name, func.count(AccessLog.id).label("count"))
        .join(Employee, AccessLog.employee_id == Employee.id)
        .join(Department, Employee.department_id == Department.id)
        .where(func.extract("month", AccessLog.timestamp) == today.month)
        .where(func.extract("year", AccessLog.timestamp) == today.year)
        .group_by(Department.name)
    )
    results = session.exec(statement).all()
    return {"labels": [r.name for r in results], "data": [r.count for r in results]}


@router.get(
    "/monthly-days-chart",
    dependencies=[Depends(require_roles(*FULL_ANALYTICS_ROLES))],
)
def get_monthly_days_chart(session: Session = Depends(get_session)):
    today = date.today()
    _, num_days = monthrange(today.year, today.month)
    statement = (
        select(
            func.extract("day", AccessLog.timestamp).label("day"),
            func.count(AccessLog.id).label("count"),
        )
        .where(func.extract("month", AccessLog.timestamp) == today.month)
        .where(func.extract("year", AccessLog.timestamp) == today.year)
        .group_by(func.extract("day", AccessLog.timestamp))
        .order_by(func.extract("day", AccessLog.timestamp))
    )
    results = session.exec(statement).all()
    data_dict = {str(i): 0 for i in range(1, num_days + 1)}
    for row in results:
        data_dict[str(int(row.day))] = row.count
    return {"labels": list(data_dict.keys()), "data": list(data_dict.values())}


@router.get(
    "/presence",
    dependencies=[Depends(require_roles(*FULL_ANALYTICS_ROLES))],
)
def get_presence(target_date: str | None = None, session: Session = Depends(get_session)):
    if target_date:
        try:
            query_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    total_active = session.exec(select(func.count(Employee.id)).where(Employee.is_active == True)).one()

    present_employees = session.exec(
        select(func.count(func.distinct(AccessLog.employee_id)))
        .where(func.date(AccessLog.timestamp) == query_date)
        .where(AccessLog.status == "granted")
        .where(AccessLog.employee_id != None)
    ).one()

    present_guests = session.exec(
        select(func.count(func.distinct(AccessLog.guest_id)))
        .where(func.date(AccessLog.timestamp) == query_date)
        .where(AccessLog.status == "granted")
        .where(AccessLog.guest_id != None)
    ).one()

    present = present_employees + present_guests
    percentage = int((present / total_active * 100)) if total_active > 0 else 0
    return {"present": present, "total": total_active, "percentage": percentage}


@router.get(
    "/camera-traffic",
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_camera_traffic(session: Session = Depends(get_session)):
    today = date.today()
    statement = (
        select(Camera.name, func.count(AccessLog.id))
        .join(AccessLog, AccessLog.camera_id == Camera.id)
        .where(func.extract("month", AccessLog.timestamp) == today.month)
        .where(func.extract("year", AccessLog.timestamp) == today.year)
        .group_by(Camera.name)
    )
    results = session.exec(statement).all()
    return {"labels": [r[0] for r in results], "data": [r[1] for r in results]}


@router.get(
    "/daily-attendance",
    dependencies=[Depends(require_roles(*FULL_ANALYTICS_ROLES))],
)
def get_daily_attendance(target_date: str | None = None, session: Session = Depends(get_session)):
    if target_date:
        try:
            query_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            query_date = date.today()
    else:
        latest_log = session.exec(
            select(AccessLog)
            .where(AccessLog.employee_id != None)
            .order_by(AccessLog.timestamp.desc())
        ).first()

        if not latest_log:
            return {"date": date.today().strftime("%Y-%m-%d"), "data": []}

        query_date = latest_log.timestamp.date()

    statement = (
        select(AccessLog, Employee, Department, Camera)
        .join(Employee, AccessLog.employee_id == Employee.id)
        .join(Department, Employee.department_id == Department.id)
        .join(Camera, AccessLog.camera_id == Camera.id)
        .where(func.date(AccessLog.timestamp) == query_date)
        .where(AccessLog.status == "granted")
    )
    logs = session.exec(statement).all()

    emp_data = {}
    for log, emp, dept, cam in logs:
        if emp.id not in emp_data:
            emp_data[emp.id] = {
                "name": f"{emp.last_name} {emp.first_name[0]}.",
                "dept_name": dept.name,
                "work_start": dept.work_start,
                "work_end": dept.work_end,
                "arrival": None,
                "departure": None,
                "any_seen": log.timestamp,
            }

        if cam.direction in ["in", "both"]:
            if emp_data[emp.id]["arrival"] is None or log.timestamp < emp_data[emp.id]["arrival"]:
                emp_data[emp.id]["arrival"] = log.timestamp

        if cam.direction in ["out", "both"]:
            if emp_data[emp.id]["departure"] is None or log.timestamp > emp_data[emp.id]["departure"]:
                emp_data[emp.id]["departure"] = log.timestamp

        if log.timestamp < emp_data[emp.id]["any_seen"]:
            emp_data[emp.id]["any_seen"] = log.timestamp

    result = []
    for _, data in emp_data.items():
        arr = data["arrival"] or data["departure"] or data["any_seen"]
        dep = data["departure"] or data["arrival"] or data["any_seen"]

        first_time = arr.time()
        last_time = dep.time()

        is_late = first_time > data["work_start"]
        is_left_early = last_time < data["work_end"]

        result.append(
            {
                "employee": data["name"],
                "department": data["dept_name"],
                "arrival": arr.strftime("%H:%M"),
                "departure": dep.strftime("%H:%M"),
                "arrival_dec": first_time.hour + first_time.minute / 60.0,
                "departure_dec": last_time.hour + last_time.minute / 60.0,
                "is_late": is_late,
                "is_left_early": is_left_early,
                "work_start": data["work_start"].strftime("%H:%M"),
                "work_end": data["work_end"].strftime("%H:%M"),
            }
        )

    result.sort(key=lambda x: x["arrival_dec"])

    return {
        "date": query_date.strftime("%Y-%m-%d"),
        "data": result,
    }


@router.get(
    "/discipline",
    dependencies=[Depends(require_roles(*FULL_ANALYTICS_ROLES))],
)
def get_discipline_stats(session: Session = Depends(get_session)):
    today = date.today()

    employees_data = session.exec(select(Employee, Department).join(Department)).all()

    dept_stats = {}
    for emp, dept in employees_data:
        if dept.id not in dept_stats:
            dept_stats[dept.id] = {
                "department_id": dept.id,
                "department_name": dept.name,
                "on_time": 0,
                "late": 0,
                "employees": {},
            }
        dept_stats[dept.id]["employees"][emp.id] = {
            "employee_id": emp.id,
            "employee_name": f"{emp.last_name} {emp.first_name}",
            "on_time": 0,
            "late": 0,
            "work_start": dept.work_start,
        }

    statement = (
        select(AccessLog, Camera)
        .join(Camera, AccessLog.camera_id == Camera.id)
        .where(
            func.extract("month", AccessLog.timestamp) == today.month,
            func.extract("year", AccessLog.timestamp) == today.year,
            AccessLog.status == "granted",
            Camera.direction.in_(["in", "both"]),
            AccessLog.employee_id != None,
        )
    )
    logs = session.exec(statement).all()

    first_arrivals = {}
    for log, _cam in logs:
        if log.employee_id is None:
            continue
        log_date = log.timestamp.date()
        key = (log.employee_id, log_date)
        if key not in first_arrivals or log.timestamp < first_arrivals[key]:
            first_arrivals[key] = log.timestamp

    for (emp_id, _log_date), arrival_time in first_arrivals.items():
        for _, d_data in dept_stats.items():
            if emp_id in d_data["employees"]:
                emp_data = d_data["employees"][emp_id]

                if arrival_time.time() > emp_data["work_start"]:
                    emp_data["late"] += 1
                    d_data["late"] += 1
                else:
                    emp_data["on_time"] += 1
                    d_data["on_time"] += 1
                break

    result = []
    for _, d_data in dept_stats.items():
        d_data["employees"] = list(d_data["employees"].values())
        result.append(d_data)

    return result
