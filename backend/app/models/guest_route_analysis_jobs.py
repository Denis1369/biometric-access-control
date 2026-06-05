"""Состояние фонового задания офлайн-анализа маршрута гостя.

Когда оператор нажимает «Проанализировать видео и построить», backend не может
обработать несколько MP4-файлов внутри одного HTTP-запроса. Поэтому создаётся
задание, его прогресс сохраняется в этой таблице, а frontend отслеживает статус
через WebSocket.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import JSON
from sqlmodel import Field, SQLModel


class GuestRouteAnalysisJob(SQLModel, table=True):
    """Одна попытка найти выбранного гостя на file-камерах этажа.

    Запись хранит период анализа, количество обработанных камер, число событий,
    записанных в ``TrackingLog``, предупреждения и ошибку. Благодаря этому можно
    показать оператору, что именно произошло: обработка ещё идёт, завершилась
    успешно, не нашла гостя или упала из-за проблем с видео/моделью.
    """

    __tablename__ = "guest_route_analysis_jobs"

    id: int | None = Field(default=None, primary_key=True)
    guest_id: int = Field(
        sa_column=Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    floor_id: int = Field(
        sa_column=Column(Integer, ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    status: str = Field(default="queued", sa_column=Column(String(32), nullable=False, index=True))
    time_from: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    time_to: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    processed_cameras: int = Field(default=0)
    events_written: int = Field(default=0)
    warnings_json: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    error_message: str | None = Field(default=None, sa_column=Column(String(1000), nullable=True))
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime, nullable=True))
