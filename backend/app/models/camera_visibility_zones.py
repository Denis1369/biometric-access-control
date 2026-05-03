from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlmodel import Field, SQLModel


class CameraVisibilityZone(SQLModel, table=True):
    __tablename__ = "camera_visibility_zones"
    __table_args__ = (
        UniqueConstraint("camera_id", name="uq_camera_visibility_zones_camera_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    camera_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("cameras.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    floor_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("floors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    points_json: list[dict[str, float]] = Field(
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False),
    )
