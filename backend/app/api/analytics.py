from datetime import datetime, date
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from pydantic import BaseModel
from typing import List

from app.core.database import get_session
from app.models.employees import Employee
from app.models.cameras import Camera
from app.models.events import AccessLog, TrackingLog

router = APIRouter(prefix="/api/analytics", tags=["Аналитика и Журналы"])

class AccessLogResponse(BaseModel):
    """
    Схема ответа для журнала проходов.
    Объединяет данные из таблиц событий, сотрудников и камер.
    """
    id: int
    timestamp: datetime
    status: str
    employee_name: str | None
    camera_name: str | None

class TrackingLogResponse(BaseModel):
    """
    Схема ответа для журнала отслеживания маршрутов.
    """
    id: int
    timestamp: datetime
    confidence: float
    employee_name: str | None
    camera_name: str | None

class DashboardStatsResponse(BaseModel):
    """
    Схема ответа для сводной статистики на главном дашборде.
    """
    total_employees: int
    active_cameras: int
    accesses_today: int

@router.get(
    "/access-logs", 
    response_model=List[AccessLogResponse],
    summary="Получить журнал проходов",
    description="Возвращает историю запросов на доступ с именами сотрудников и названиями камер. Отсортировано по времени (сначала новые)."
)
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
        full_name = f"{employee.last_name} {employee.first_name}" if employee else "Неизвестный"
        if employee and getattr(employee, "middle_name", None):
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

@router.get(
    "/tracking-logs", 
    response_model=List[TrackingLogResponse],
    summary="Получить журнал отслеживания",
    description="Возвращает точки фиксации лиц на камерах для построения маршрутов перемещения."
)
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

@router.get(
    "/stats", 
    response_model=DashboardStatsResponse,
    summary="Получить сводную статистику",
    description="Возвращает агрегированные данные для виджетов (карточек) на главном экране интерфейса."
)
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