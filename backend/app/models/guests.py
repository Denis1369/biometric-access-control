"""Модели гостевых пропусков, фото лица и Re-ID признаков тела.

Гость в системе — это временный посетитель, которому оператор КПП оформляет
пропуск к конкретному сотруднику. Основная таблица guests хранит ФИО, срок
действия и body_embedding для поиска человека на разных камерах. Фотографии
лица и face embedding вынесены в отдельную таблицу GuestFaceSample, потому что
для одного гостя можно хранить несколько образцов лица.
"""

from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.mysql import MEDIUMBLOB, JSON


class Guest(SQLModel, table=True):
    """Гостевой пропуск, связанный с принимающим сотрудником.

    valid_until определяет срок действия пропуска, is_active позволяет закрыть
    пропуск вручную, employee_id указывает сотрудника, к которому пришёл гость.
    body_embedding хранит числовой вектор внешности человека в полный рост,
    который используется offline-анализом маршрута по видео камер.
    """

    __tablename__ = "guests"

    id: int | None = Field(default=None, primary_key=True)
    last_name: str
    first_name: str
    middle_name: str | None = None
    employee_id: int | None = Field(default=None, foreign_key="employees.id", index=True)
    valid_until: datetime
    is_active: bool = Field(default=True)
    body_embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    body_embedding_updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime, nullable=True),
    )


class GuestFaceSample(SQLModel, table=True):
    """Фотография лица гостя и embedding InsightFace.

    Эта таблица используется при распознавании гостя на проходной. photo_data
    хранит исходное изображение, mime_type нужен для корректной отдачи фото в
    браузер, а embedding содержит числовой вектор лица, с которым сравниваются
    лица из кадра камеры.
    """

    __tablename__ = "guest_face_samples"

    id: int | None = Field(default=None, primary_key=True)

    guest_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("guests.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )
    )

    mime_type: str = Field(sa_column=Column(String(100), nullable=False))
    photo_data: bytes = Field(sa_column=Column(MEDIUMBLOB, nullable=False))
    embedding: list[float] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=datetime.now)
