"""Зоны видимости камер в виде четырёхточечных полигонов на плане этажа.

Зона видимости связывает камеру с областью на плане, где человек мог находиться,
если он был замечен этой камерой. Эти данные нужны не для видеоаналитики
напрямую, а для построения вероятного маршрута: зона пересекается с линиями
графа маршрутов, и система выбирает возможные участки движения.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlmodel import Field, SQLModel


class CameraVisibilityZone(SQLModel, table=True):
    """Одна редактируемая зона видимости одной камеры на одном этаже.

    points_json хранит ровно четыре точки в координатах исходного изображения
    плана, а не CSS-координат браузера. UniqueConstraint по camera_id гарантирует,
    что у камеры есть только одна актуальная зона. При удалении камеры или этажа
    зона удаляется каскадно, чтобы на плане не оставались «призраки» старых
    камер.
    """

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
