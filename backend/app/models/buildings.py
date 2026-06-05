"""Модель здания, объединяющего этажи, планы и камеры.

Здание является верхним уровнем структуры объекта. Через него пользователь
выбирает нужный корпус или площадку, а дальше работает с этажами, планами,
камерами, зонами видимости и графом маршрутов.
"""

from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime


class Building(SQLModel, table=True):
    """Физическое здание, отображаемое в редакторе планов этажей.

    name уникален, чтобы в интерфейсе не было двух одинаковых зданий. address
    используется как справочная информация, а created_at помогает сортировать и
    показывать историю настройки объекта.
    """

    __tablename__ = "buildings"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    address: str | None = Field(default=None)

    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False)
    )
