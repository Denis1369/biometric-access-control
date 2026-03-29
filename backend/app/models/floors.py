from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, String, Integer, ForeignKey
from sqlalchemy.dialects.mysql import LONGBLOB


class Floor(SQLModel, table=True):
    __tablename__ = "floors"

    id: int | None = Field(default=None, primary_key=True)

    building_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("buildings.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
    )

    name: str
    floor_number: int

    plan_mime_type: str | None = Field(
        default=None,
        sa_column=Column(String(100), nullable=True)
    )
    plan_image: bytes | None = Field(
        default=None,
        sa_column=Column(LONGBLOB, nullable=True)
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False)
    )