"""Модели задач анализа загруженных видео и найденных событий.

Эти таблицы обслуживают страницу «Анализ видео», где пользователь загружает
один ролик, а backend обрабатывает его в фоне. VideoAnalysisJob хранит состояние
долгой операции, а VideoAnalysisEvent — отдельные моменты, где система нашла
человека и приняла решение о распознавании.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class VideoAnalysisJob(SQLModel, table=True):
    """Фоновая задача обработки одного загруженного видеофайла.

    source_path указывает на файл в storage, status показывает жизненный цикл
    queued/processing/completed/failed, analyzed_frames нужен для прогресса,
    granted_count и denied_count показывают итоговые решения системы, а
    error_message хранит понятную причину сбоя для интерфейса.
    """

    __tablename__ = "video_analysis_jobs"

    id: int | None = Field(default=None, primary_key=True)
    original_filename: str
    source_path: str
    status: str = Field(default="queued", index=True)
    created_by_user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    reader_backend: str | None = None
    total_frames: int | None = None
    analyzed_frames: int = Field(default=0)
    duration_sec: float | None = None
    granted_count: int = Field(default=0)
    denied_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class VideoAnalysisEvent(SQLModel, table=True):
    """Одно событие, найденное в процессе анализа видео.

    frame_index и timestamp_sec связывают событие с конкретным моментом ролика.
    person_type/person_id/person_name описывают распознанного человека, status и
    decision показывают решение системы, confidence/distance помогают оценить
    качество совпадения, а preview_path ведёт к кадру-превью для визуальной
    проверки результата.
    """

    __tablename__ = "video_analysis_events"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="video_analysis_jobs.id", index=True)
    frame_index: int = Field(default=0)
    timestamp_sec: float = Field(default=0.0)
    status: str = Field(default="denied", index=True)
    person_type: str | None = None
    person_id: int | None = None
    person_name: str | None = None
    decision: str | None = None
    confidence: float | None = None
    distance: float | None = None
    preview_path: str | None = None
    created_at: datetime = Field(default_factory=datetime.now, index=True)
