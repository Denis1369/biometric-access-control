from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class RouteEdge(SQLModel, table=True):
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
