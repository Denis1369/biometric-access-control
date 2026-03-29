from datetime import datetime, date
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from pydantic import BaseModel
from typing import List
from calendar import monthrange

from app.core.database import get_session
from app.models.employees import Employee
from app.models.cameras import Camera
from app.models.departments import Department
from app.models.logs import AccessLog, TrackingLog

router = APIRouter(prefix="/api/analytics", tags=["Аналитика и Журналы"])

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

@router.get("/access-logs", response_model=List[AccessLogResponse])
def get_access_logs(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = (
        select(AccessLog, Employee, Camera)
        .join(Employee, AccessLog.employee_id == Employee.id, isouter=True)
        .join(Camera, AccessLog.camera_id == Camera.id, isouter=True)
        .order_by(AccessLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    
    results = session.exec(statement).all()
    
    response_data = []
    for access_log, employee, camera in results:
        full_name = "Неизвестный"
        if employee:
            full_name = f"{employee.last_name} {employee.first_name}"
            if employee.middle_name:
                full_name += f" {employee.middle_name}"
            
        response_data.append(
            AccessLogResponse(
                id=access_log.id,
                timestamp=access_log.timestamp,
                status=access_log.status,
                employee_name=full_name,
                camera_name=camera.name if camera else "Удаленная камера"
            )
        )
        
    return response_data

@router.get("/tracking-logs", response_model=List[TrackingLogResponse])
def get_tracking_logs(session: Session = Depends(get_session), skip: int = 0, limit: int = 100):
    statement = (
        select(TrackingLog, Employee, Camera)
        .join(Employee, TrackingLog.employee_id == Employee.id, isouter=True)
        .join(Camera, TrackingLog.camera_id == Camera.id, isouter=True)
        .order_by(TrackingLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    
    results = session.exec(statement).all()
    
    response_data = []
    for tracking_log, employee, camera in results:
        full_name = f"{employee.last_name} {employee.first_name}" if employee else "Неизвестный"
        
        response_data.append(
            TrackingLogResponse(
                id=tracking_log.id,
                timestamp=tracking_log.timestamp,
                confidence=tracking_log.confidence,
                employee_name=full_name,
                camera_name=camera.name if camera else "Неизвестно"
            )
        )
        
    return response_data

@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(session: Session = Depends(get_session)):
    total_employees = session.exec(select(func.count(Employee.id))).one()
    active_cameras = session.exec(select(func.count(Camera.id)).where(Camera.is_active == True)).one()
    
    today = date.today()
    accesses_today = session.exec(
        select(func.count(AccessLog.id))
        .where(func.date(AccessLog.timestamp) == today)
    ).one()
    
    return DashboardStatsResponse(
        total_employees=total_employees,
        active_cameras=active_cameras,
        accesses_today=accesses_today
    )

@router.get("/daily-chart")
def get_daily_chart(session: Session = Depends(get_session)):
    """График проходов за сегодня с группировкой по часам."""
    today = date.today()
    
    statement = (
        select(
            func.extract('hour', AccessLog.timestamp).label('hour'),
            func.count(AccessLog.id).label('count')
        )
        .where(func.date(AccessLog.timestamp) == today)
        .group_by(func.extract('hour', AccessLog.timestamp))
        .order_by(func.extract('hour', AccessLog.timestamp))
    )
    results = session.exec(statement).all()
    
    data_dict = {f"{i:02d}:00": 0 for i in range(24)}
    for row in results:
        hour = int(row.hour)
        data_dict[f"{hour:02d}:00"] = row.count
        
    return {"labels": list(data_dict.keys()), "data": list(data_dict.values())}

@router.get("/monthly-department-chart")
def get_monthly_department_chart(session: Session = Depends(get_session)):
    """График проходов за текущий месяц с группировкой по отделам."""
    today = date.today()
    
    statement = (
        select(
            Department.name,
            func.count(AccessLog.id).label('count')
        )
        .join(Employee, AccessLog.employee_id == Employee.id)
        .join(Department, Employee.department_id == Department.id)
        .where(func.extract('month', AccessLog.timestamp) == today.month)
        .where(func.extract('year', AccessLog.timestamp) == today.year)
        .group_by(Department.name)
    )
    results = session.exec(statement).all()
    
    labels = []
    data = []
    for row in results:
        labels.append(row.name)
        data.append(row.count)
        
    return {"labels": labels, "data": data}

@router.get("/monthly-days-chart")
def get_monthly_days_chart(session: Session = Depends(get_session)):
    """График проходов по дням за текущий месяц."""
    today = date.today()
    _, num_days = monthrange(today.year, today.month)
    
    statement = (
        select(
            func.extract('day', AccessLog.timestamp).label('day'),
            func.count(AccessLog.id).label('count')
        )
        .where(func.extract('month', AccessLog.timestamp) == today.month)
        .where(func.extract('year', AccessLog.timestamp) == today.year)
        .group_by(func.extract('day', AccessLog.timestamp))
        .order_by(func.extract('day', AccessLog.timestamp))
    )
    results = session.exec(statement).all()
    
    data_dict = {str(i): 0 for i in range(1, num_days + 1)}
    for row in results:
        day = int(row.day)
        data_dict[str(day)] = row.count
        
    return {"labels": list(data_dict.keys()), "data": list(data_dict.values())}

@router.get("/presence")
def get_presence(session: Session = Depends(get_session)):
    """Процент присутствия сотрудников на рабочем месте сегодня."""
    today = date.today()
    total_active = session.exec(select(func.count(Employee.id)).where(Employee.is_active == True)).one()
    
    statement = (
        select(func.count(func.distinct(AccessLog.employee_id)))
        .where(func.date(AccessLog.timestamp) == today)
        .where(AccessLog.status == 'granted')
        .where(AccessLog.employee_id != None)
    )
    present = session.exec(statement).one()
    
    percentage = int((present / total_active * 100)) if total_active > 0 else 0
    return {"present": present, "total": total_active, "percentage": percentage}

@router.get("/camera-traffic")
def get_camera_traffic(session: Session = Depends(get_session)):
    """Загруженность точек прохода (камер) за текущий месяц."""
    today = date.today()
    statement = (
        select(Camera.name, func.count(AccessLog.id))
        .join(AccessLog, AccessLog.camera_id == Camera.id)
        .where(func.extract('month', AccessLog.timestamp) == today.month)
        .where(func.extract('year', AccessLog.timestamp) == today.year)
        .group_by(Camera.name)
    )
    results = session.exec(statement).all()
    return {
        "labels": [r[0] for r in results],
        "data": [r[1] for r in results]
    }

@router.get("/discipline")
def get_discipline_stats(session: Session = Depends(get_session)):
    """Статистика опозданий по отделам с детализацией по сотрудникам (Drill-down)."""
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
                "employees": {}
            }
        dept_stats[dept.id]["employees"][emp.id] = {
            "employee_id": emp.id,
            "employee_name": f"{emp.last_name} {emp.first_name}",
            "on_time": 0,
            "late": 0,
            "work_start": dept.work_start
        }
        
    statement = select(AccessLog).where(
        func.extract('month', AccessLog.timestamp) == today.month,
        func.extract('year', AccessLog.timestamp) == today.year,
        AccessLog.status == 'granted'
    )
    logs = session.exec(statement).all()
    
    first_arrivals = {}
    for log in logs:
        if log.employee_id is None: continue
        log_date = log.timestamp.date()
        key = (log.employee_id, log_date)
        if key not in first_arrivals or log.timestamp < first_arrivals[key]:
            first_arrivals[key] = log.timestamp
            
    for (emp_id, log_date), arrival_time in first_arrivals.items():
        for d_id, d_data in dept_stats.items():
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
    for d_id, d_data in dept_stats.items():
        d_data["employees"] = list(d_data["employees"].values())
        result.append(d_data)
        
    return result