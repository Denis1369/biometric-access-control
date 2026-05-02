from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from app.core.database import get_session
from app.core.deps import require_roles
from app.models.cameras import Camera
from app.models.buildings import Building
from app.models.departments import Department
from app.models.employees import Employee
from app.models.floors import Floor
from app.models.guests import Guest
from app.models.logs import AccessLog, TrackingLog
from app.models.user import UserRole
from app.services.camera_topology_service import infer_camera_transitions

router = APIRouter(prefix="/api/analytics", tags=["Аналитика и Журналы"])


BASIC_ANALYTICS_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
)
FULL_ANALYTICS_ROLES = (
    UserRole.SUPER_ADMIN,
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


class RoutePathPointResponse(BaseModel):
    x: float
    y: float


class GuestRoutePointResponse(BaseModel):
    id: int
    timestamp: datetime
    guest_id: int
    guest_name: str
    camera_id: int | None
    camera_name: str | None
    building_id: int | None
    building_name: str | None
    floor_id: int | None
    floor_name: str | None
    floor_number: int | None
    plan_x: float | None
    plan_y: float | None
    path_to_next: list[RoutePathPointResponse] = Field(default_factory=list)
    confidence: float


class CameraTransitionResponse(BaseModel):
    from_camera_id: int
    from_camera_name: str
    to_camera_id: int
    to_camera_name: str
    transition_count: int
    unique_person_count: int
    avg_travel_seconds: float
    median_travel_seconds: float
    min_travel_seconds: float
    max_travel_seconds: float
    confidence: float


class DashboardStatsResponse(BaseModel):
    total_employees: int
    active_cameras: int
    accesses_today: int


def _parse_target_date(target_date: str | None) -> date:
    if not target_date:
        return date.today()

    try:
        return datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Параметр target_date должен быть в формате YYYY-MM-DD",
        ) from exc


def _build_person_name(employee: Employee | None, guest: Guest | None) -> str:
    if employee:
        return " ".join(
            part
            for part in (employee.last_name, employee.first_name, employee.middle_name)
            if part
        )
    if guest:
        return f"[Гость] {guest.last_name} {guest.first_name}"
    return "Неизвестное лицо"


def _clamp01(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _camera_route_anchor(camera: Camera | None) -> tuple[float | None, float | None]:
    if camera is None:
        return None, None

    polygon = camera.visibility_polygon if isinstance(camera.visibility_polygon, list) else None
    if polygon and len(polygon) >= 3:
        points: list[tuple[float, float]] = []
        for raw_point in polygon:
            if not isinstance(raw_point, dict):
                continue
            x = _clamp01(raw_point.get("x"))
            y = _clamp01(raw_point.get("y"))
            if x is not None and y is not None:
                points.append((x, y))
        if len(points) >= 3:
            return (
                sum(point[0] for point in points) / len(points),
                sum(point[1] for point in points) / len(points),
            )

    return _clamp01(camera.plan_x), _clamp01(camera.plan_y)


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
        response_data.append(
            AccessLogResponse(
                id=access_log.id,
                timestamp=access_log.timestamp,
                status=access_log.status,
                employee_name=_build_person_name(employee, guest),
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
        response_data.append(
            TrackingLogResponse(
                id=tracking_log.id,
                timestamp=tracking_log.timestamp,
                confidence=tracking_log.confidence,
                employee_name=_build_person_name(employee, guest),
                camera_name=camera.name if camera else "Неизвестно",
            )
        )
    return response_data


@router.get(
    "/guest-route",
    response_model=List[GuestRoutePointResponse],
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_guest_route(
    guest_id: int | None = None,
    target_date: str | None = None,
    building_id: int | None = None,
    floor_id: int | None = None,
    limit: int = 200,
    session: Session = Depends(get_session),
):
    query_date = _parse_target_date(target_date)
    start_of_day = datetime.combine(query_date, datetime.min.time())
    end_of_day = datetime.combine(query_date, datetime.max.time())

    statement = (
        select(TrackingLog, Guest, Camera, Building, Floor)
        .join(Guest, TrackingLog.guest_id == Guest.id)
        .join(Camera, TrackingLog.camera_id == Camera.id, isouter=True)
        .join(Building, Camera.building_id == Building.id, isouter=True)
        .join(Floor, Camera.floor_id == Floor.id, isouter=True)
        .where(TrackingLog.timestamp >= start_of_day)
        .where(TrackingLog.timestamp <= end_of_day)
        .order_by(TrackingLog.timestamp.asc())
        .limit(min(max(limit, 1), 500))
    )

    if guest_id is not None:
        statement = statement.where(TrackingLog.guest_id == guest_id)
    if building_id is not None:
        statement = statement.where(Camera.building_id == building_id)
    if floor_id is not None:
        statement = statement.where(Camera.floor_id == floor_id)

    rows = session.exec(statement).all()
    result_items: list[dict] = []
    for tracking_log, guest, camera, building, floor in rows:
        anchor_x, anchor_y = _camera_route_anchor(camera)
        result_items.append(
            {
                "id": tracking_log.id,
                "timestamp": tracking_log.timestamp,
                "guest_id": guest.id,
                "guest_name": f"{guest.last_name} {guest.first_name}",
                "camera_id": camera.id if camera else None,
                "camera_name": camera.name if camera else None,
                "building_id": building.id if building else None,
                "building_name": building.name if building else None,
                "floor_id": floor.id if floor else None,
                "floor_name": floor.name if floor else None,
                "floor_number": floor.floor_number if floor else None,
                "plan_x": anchor_x,
                "plan_y": anchor_y,
                "path_to_next": [],
                "confidence": tracking_log.confidence,
            }
        )

    for index, current_item in enumerate(result_items[:-1]):
        next_item = result_items[index + 1]
        same_guest = current_item["guest_id"] == next_item["guest_id"]
        same_floor = (
            current_item["floor_id"] is not None
            and current_item["floor_id"] == next_item["floor_id"]
        )
        if not same_guest or not same_floor:
            continue

        if (
            current_item["plan_x"] is not None
            and current_item["plan_y"] is not None
            and next_item["plan_x"] is not None
            and next_item["plan_y"] is not None
        ):
            current_item["path_to_next"] = [
                {"x": current_item["plan_x"], "y": current_item["plan_y"]},
                {"x": next_item["plan_x"], "y": next_item["plan_y"]},
            ]

    return [GuestRoutePointResponse(**item) for item in result_items]


@router.get(
    "/camera-transitions",
    response_model=List[CameraTransitionResponse],
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_camera_transitions(
    target_date: str | None = None,
    days: int = 30,
    building_id: int | None = None,
    floor_id: int | None = None,
    person_type: str = "all",
    max_gap_minutes: int = 30,
    min_count: int = 1,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    if person_type not in {"all", "employee", "guest"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Параметр person_type должен быть all, employee или guest",
        )

    query_date = _parse_target_date(target_date)
    safe_days = min(max(days, 1), 365)
    safe_gap_minutes = min(max(max_gap_minutes, 1), 24 * 60)
    safe_min_count = min(max(min_count, 1), 1000)
    safe_limit = min(max(limit, 1), 500)

    start_at = datetime.combine(
        query_date - timedelta(days=safe_days - 1),
        datetime.min.time(),
    )
    end_at = datetime.combine(query_date, datetime.max.time())

    transitions = infer_camera_transitions(
        session,
        start_at=start_at,
        end_at=end_at,
        person_type=person_type,  # type: ignore[arg-type]
        building_id=building_id,
        floor_id=floor_id,
        max_transition_gap=timedelta(minutes=safe_gap_minutes),
        min_transition_count=safe_min_count,
        limit=safe_limit,
    )

    return [CameraTransitionResponse(**transition.__dict__) for transition in transitions]


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    dependencies=[Depends(require_roles(*BASIC_ANALYTICS_ROLES))],
)
def get_dashboard_stats(target_date: str | None = None, session: Session = Depends(get_session)):
    total_employees = session.exec(select(func.count(Employee.id))).one()
    active_cameras = session.exec(
        select(func.count(Camera.id)).where(Camera.is_active.is_(True))
    ).one()
    query_date = _parse_target_date(target_date)

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
    query_date = _parse_target_date(target_date)

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
    query_date = _parse_target_date(target_date)
    total_active = session.exec(
        select(func.count(Employee.id)).where(Employee.is_active.is_(True))
    ).one()

    present_employees = session.exec(
        select(func.count(func.distinct(AccessLog.employee_id)))
        .where(func.date(AccessLog.timestamp) == query_date)
        .where(AccessLog.status == "granted")
        .where(AccessLog.employee_id.is_not(None))
    ).one()

    present_guests = session.exec(
        select(func.count(func.distinct(AccessLog.guest_id)))
        .where(func.date(AccessLog.timestamp) == query_date)
        .where(AccessLog.status == "granted")
        .where(AccessLog.guest_id.is_not(None))
    ).one()

    percentage = int((present_employees / total_active * 100)) if total_active > 0 else 0
    return {
        "present": present_employees,
        "total": total_active,
        "percentage": percentage,
        "guest_count": present_guests,
    }


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
def get_daily_attendance(target_date: date, session: Session = Depends(get_session)):
    employees = session.exec(
        select(Employee, Department)
        .join(Department, isouter=True)
        .where(Employee.is_active.is_(True))
    ).all()
    
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    logs = session.exec(
        select(AccessLog, Camera)
        .join(Camera)
        .where(AccessLog.timestamp >= start_of_day)
        .where(AccessLog.timestamp <= end_of_day)
        .where(AccessLog.status == "granted")
        .where(AccessLog.employee_id.is_not(None))
        .order_by(AccessLog.timestamp)
    ).all()

    emp_logs = {}
    for log, cam in logs:
        emp_logs.setdefault(log.employee_id, []).append((log, cam))

    result = []
    for emp, dept in employees:
        e_logs = emp_logs.get(emp.id, [])
        
        in_logs = [l for l, c in e_logs if c.direction == "in"]
        out_logs = [l for l, c in e_logs if c.direction == "out"]
        
        time_in_obj = in_logs[0].timestamp if in_logs else None
        time_out_obj = out_logs[-1].timestamp if out_logs else None

        status = "absent"
        if time_in_obj and not time_out_obj:
            status = "working"
        elif time_in_obj and time_out_obj:
            status = "left"

        is_late = False
        left_early = False
        
        if dept:
            if time_in_obj and time_in_obj.time() > dept.work_start:
                is_late = True
            if time_out_obj and time_out_obj.time() < dept.work_end:
                left_early = True

        result.append({
            "id": emp.id,
            "name": f"{emp.last_name} {emp.first_name}",
            "department_id": emp.department_id,
            "date": str(target_date),
            "time_in": time_in_obj.strftime("%H:%M") if time_in_obj else None,
            "time_out": time_out_obj.strftime("%H:%M") if time_out_obj else None,
            "status": status,
            "is_late": is_late,
            "left_early": left_early
        })
        
    return result


@router.get(
    "/daily-guests",
    dependencies=[Depends(require_roles(*FULL_ANALYTICS_ROLES))],
)
def get_daily_guests(target_date: date, session: Session = Depends(get_session)):
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    logs = session.exec(
        select(AccessLog, Camera, Guest, Employee)
        .join(Camera, AccessLog.camera_id == Camera.id)
        .join(Guest, AccessLog.guest_id == Guest.id)
        .join(Employee, Guest.employee_id == Employee.id)
        .where(AccessLog.timestamp >= start_of_day)
        .where(AccessLog.timestamp <= end_of_day)
        .where(AccessLog.status == "granted")
        .where(AccessLog.guest_id.is_not(None))
        .order_by(AccessLog.timestamp)
    ).all()

    guest_data = {}
    for log, cam, guest, emp in logs:
        if guest.id not in guest_data:
            guest_data[guest.id] = {"guest": guest, "emp": emp, "logs": []}
        guest_data[guest.id]["logs"].append((log, cam))
        
    result = []
    for gid, data in guest_data.items():
        guest = data["guest"]
        emp = data["emp"]
        g_logs = data["logs"]
        
        current_in_time = None
        visit_counter = 1
        
        for log, cam in g_logs:
            if cam.direction == "in":
                if current_in_time is None:
                    current_in_time = log.timestamp
            
            elif cam.direction == "out":
                if current_in_time is not None:
                    diff = log.timestamp - current_in_time
                    hours, rem = divmod(diff.seconds, 3600)
                    minutes = rem // 60
                    duration = f"{hours} ч {minutes} мин" if hours > 0 else f"{minutes} мин"
                    
                    result.append({
                        "id": f"{guest.id}_{visit_counter}",
                        "name": f"{guest.last_name} {guest.first_name}",
                        "visited_employee": f"{emp.last_name} {emp.first_name}",
                        "date": str(target_date),
                        "time_in": current_in_time.strftime("%H:%M"),
                        "time_out": log.timestamp.strftime("%H:%M"),
                        "duration": duration
                    })
                    current_in_time = None
                    visit_counter += 1
                else:
                    result.append({
                        "id": f"{guest.id}_{visit_counter}",
                        "name": f"{guest.last_name} {guest.first_name}",
                        "visited_employee": f"{emp.last_name} {emp.first_name}",
                        "date": str(target_date),
                        "time_in": None,
                        "time_out": log.timestamp.strftime("%H:%M"),
                        "duration": None
                    })
                    visit_counter += 1
        
        if current_in_time is not None:
            result.append({
                "id": f"{guest.id}_{visit_counter}",
                "name": f"{guest.last_name} {guest.first_name}",
                "visited_employee": f"{emp.last_name} {emp.first_name}",
                "date": str(target_date),
                "time_in": current_in_time.strftime("%H:%M"),
                "time_out": None,
                "duration": None
            })
            
    return result


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
            AccessLog.employee_id.is_not(None),
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
