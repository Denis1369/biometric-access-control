from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime


class Building(SQLModel, table=True):
    __tablename__ = "buildings"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    address: str | None = Field(default=None)

    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False)
    )