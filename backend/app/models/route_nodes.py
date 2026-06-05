"""Модель точки ручного графа маршрутов на плане этажа.

Оператор вручную ставит точки поверх изображения плана, а backend сохраняет их
как route_nodes. Эти точки не являются камерами, комнатами или дверями сами по
себе; это технические вершины графа, по которым затем строится кратчайший путь.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class RouteNode(SQLModel, table=True):
    """Техническая точка графа возможного движения.

    x и y хранятся в пикселях исходного изображения плана. Это важно: если
    сохранить экранные координаты после CSS-масштабирования, граф съедет при
    изменении размера окна. floor_id связывает точку с конкретным этажом.
    """

    __tablename__ = "route_nodes"

    id: int | None = Field(default=None, primary_key=True)
    floor_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("floors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    x: float = Field(sa_column=Column(Float, nullable=False))
    y: float = Field(sa_column=Column(Float, nullable=False))
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False),
    )
