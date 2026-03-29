from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON, DateTime, String, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.mysql import MEDIUMBLOB


class EmployeeFaceSample(SQLModel, table=True):
    __tablename__ = "employee_face_samples"

    id: Optional[int] = Field(default=None, primary_key=True)

    employee_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
    )

    mime_type: str = Field(sa_column=Column(String(100), nullable=False))
    photo_data: bytes = Field(sa_column=Column(MEDIUMBLOB, nullable=False))
    embedding: list[float] = Field(sa_column=Column(JSON, nullable=False))

    is_primary: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False)
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False)
    )