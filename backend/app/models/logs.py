"""Журналы событий доступа и отслеживания.

AccessLog фиксирует решение системы в контрольной точке: доступ разрешён или
запрещён. TrackingLog фиксирует более мягкое событие: человек был замечен на
камере с определённой уверенностью. Эти таблицы используются аналитикой,
журналом проходной и построением вероятного маршрута гостя.
"""

from sqlmodel import SQLModel, Field
from datetime import datetime

class AccessLog(SQLModel, table=True):
    """Событие прохода через контрольную точку.

    Запись может относиться либо к сотруднику, либо к гостю. camera_id показывает,
    какая камера или контрольная точка зафиксировала событие. status хранит
    решение `granted` или `denied`, confidence показывает уверенность
    распознавания, а timestamp нужен для отчётов и восстановления истории
    перемещений.
    """

    __tablename__ = "access_logs"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: int | None = Field(default=None, foreign_key="employees.id")
    guest_id: int | None = Field(default=None, foreign_key="guests.id")
    camera_id: int | None = Field(default=None, foreign_key="cameras.id")
    timestamp: datetime = Field(default_factory=datetime.now)
    status: str 
    confidence: float | None = None

class TrackingLog(SQLModel, table=True):
    """Событие появления человека на камере.

    TrackingLog не означает, что человек прошёл через турникет. Это факт
    наблюдения на камере, который может быть получен из онлайн-потока или
    offline-анализа file-видео. Для маршрута гостя именно эта таблица даёт
    последовательность камер по времени: Camera02 -> Camera03 -> Camera05.
    """

    __tablename__ = "tracking_logs"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: int | None = Field(default=None, foreign_key="employees.id")
    guest_id: int | None = Field(default=None, foreign_key="guests.id")
    camera_id: int | None = Field(default=None, foreign_key="cameras.id")
    timestamp: datetime = Field(default_factory=datetime.now)
    confidence: float
