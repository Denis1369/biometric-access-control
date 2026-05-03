from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from sqlmodel import Field, SQLModel


class RouteNode(SQLModel, table=True):
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
