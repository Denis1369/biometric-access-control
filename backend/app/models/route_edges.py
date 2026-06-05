"""Модель линии ручного графа маршрутов на плане этажа.

Линия соединяет две route_nodes и описывает участок, по которому человек может
перемещаться. Именно по таким линиям сервис маршрутов строит путь Дейкстрой, а
зоны видимости камер пересекаются с этими линиями для выбора вероятных участков
появления гостя.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class RouteEdge(SQLModel, table=True):
    """Взвешенный участок движения между двумя точками графа.

    weight обычно равен геометрическому расстоянию между точками в пикселях
    плана. is_bidirectional показывает, можно ли двигаться по линии в обе
    стороны. В текущей ручной разметке большинство участков двусторонние, но
    поле оставлено для будущих сценариев с односторонним движением.
    """

    __tablename__ = "route_edges"

    id: int | None = Field(default=None, primary_key=True)
    floor_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("floors.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    from_node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("route_nodes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    to_node_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("route_nodes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    weight: float = Field(sa_column=Column(Float, nullable=False))
    is_bidirectional: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, default=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False),
    )
