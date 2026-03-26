from sqlmodel import SQLModel, Field
from datetime import datetime

class AccessLog(SQLModel, table=True):
    __tablename__ = "access_logs"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: int | None = Field(default=None, foreign_key="employees.id", index=True)
    camera_id: int | None = Field(default=None, foreign_key="cameras.id", index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    status: str = Field(default="denied")

class TrackingLog(SQLModel, table=True):
    __tablename__ = "tracking_logs"

    id: int | None = Field(default=None, primary_key=True)
    employee_id: int | None = Field(default=None, foreign_key="employees.id", index=True)
    camera_id: int | None = Field(default=None, foreign_key="cameras.id", index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    confidence: float = Field(default=0.0)