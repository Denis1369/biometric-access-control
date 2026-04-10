from sqlmodel import SQLModel, Field
from datetime import datetime

class AccessLog(SQLModel, table=True):
    __tablename__ = "access_logs"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: int | None = Field(default=None, foreign_key="employees.id")
    guest_id: int | None = Field(default=None, foreign_key="guests.id")
    camera_id: int | None = Field(default=None, foreign_key="cameras.id")
    timestamp: datetime = Field(default_factory=datetime.now)
    status: str 
    confidence: float | None = None

class TrackingLog(SQLModel, table=True):
    __tablename__ = "tracking_logs"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: int | None = Field(default=None, foreign_key="employees.id")
    guest_id: int | None = Field(default=None, foreign_key="guests.id")
    camera_id: int | None = Field(default=None, foreign_key="cameras.id")
    timestamp: datetime = Field(default_factory=datetime.now)
    confidence: float