"""Модель этажа здания и изображения плана.

Этаж является центральной сущностью для визуальной части системы: к нему
привязываются план помещения, камеры, зоны видимости камер и ручной граф
маршрутов. Координаты всех объектов на плане считаются относительно исходного
изображения, поэтому важно хранить сам план вместе с этажом.
"""

from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import LONGBLOB


class Floor(SQLModel, table=True):
    """Этаж здания, на котором оператор размещает камеры и маршруты.

    Помимо номера и названия, модель может хранить бинарное изображение плана.
    Это позволяет frontend получать план прямо из backend и поверх него рисовать
    SVG-слой с камерами, зонами видимости и точками графа маршрутов.
    """

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
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column=Column(DateTime, nullable=False)
    )
