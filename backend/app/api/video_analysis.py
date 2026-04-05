from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.models.video_analysis import VideoAnalysisEvent, VideoAnalysisJob
from app.services.video_analysis_service import BASE_STORAGE_DIR, reset_video_analysis_job, schedule_video_analysis

router = APIRouter(prefix="/api/video-analysis", tags=["Анализ видео"])

ALLOWED_ROLES = (
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class VideoAnalysisJobRead(SQLModel):
    id: int
    original_filename: str
    status: str
    reader_backend: str | None = None
    total_frames: int | None = None
    analyzed_frames: int
    duration_sec: float | None = None
    granted_count: int
    denied_count: int
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None


class VideoAnalysisEventRead(SQLModel):
    id: int
    job_id: int
    frame_index: int
    timestamp_sec: float
    status: str
    person_type: str | None = None
    person_id: int | None = None
    person_name: str | None = None
    decision: str | None = None
    confidence: float | None = None
    distance: float | None = None
    created_at: str


def _serialize_datetime(value):
    return value.isoformat() if value else None


def _job_read(job: VideoAnalysisJob) -> VideoAnalysisJobRead:
    return VideoAnalysisJobRead(
        id=job.id,
        original_filename=job.original_filename,
        status=job.status,
        reader_backend=job.reader_backend,
        total_frames=job.total_frames,
        analyzed_frames=job.analyzed_frames,
        duration_sec=job.duration_sec,
        granted_count=job.granted_count,
        denied_count=job.denied_count,
        created_at=job.created_at.isoformat(),
        started_at=_serialize_datetime(job.started_at),
        finished_at=_serialize_datetime(job.finished_at),
        error_message=job.error_message,
    )


def _event_read(event: VideoAnalysisEvent) -> VideoAnalysisEventRead:
    return VideoAnalysisEventRead(
        id=event.id,
        job_id=event.job_id,
        frame_index=event.frame_index,
        timestamp_sec=event.timestamp_sec,
        status=event.status,
        person_type=event.person_type,
        person_id=event.person_id,
        person_name=event.person_name,
        decision=event.decision,
        confidence=event.confidence,
        distance=event.distance,
        created_at=event.created_at.isoformat(),
    )


@router.get(
    "/jobs",
    response_model=List[VideoAnalysisJobRead],
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
def get_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(VideoAnalysisJob).order_by(VideoAnalysisJob.created_at.desc())).all()
    return [_job_read(job) for job in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=VideoAnalysisJobRead,
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")
    return _job_read(job)


@router.get(
    "/jobs/{job_id}/events",
    response_model=List[VideoAnalysisEventRead],
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
def get_job_events(job_id: int, session: Session = Depends(get_session)):
    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")
    events = session.exec(
        select(VideoAnalysisEvent)
        .where(VideoAnalysisEvent.job_id == job_id)
        .order_by(VideoAnalysisEvent.timestamp_sec.asc())
    ).all()
    return [_event_read(event) for event in events]


@router.post(
    "/jobs/{job_id}/rerun",
    response_model=VideoAnalysisJobRead,
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
def rerun_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")

    if job.status in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="Задача уже находится в обработке")

    if not reset_video_analysis_job(job_id):
        raise HTTPException(status_code=409, detail="Не удалось перезапустить анализ")

    session.expire_all()
    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")

    schedule_video_analysis(job_id)
    return _job_read(job)


@router.get(
    "/events/{event_id}/preview",
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
def get_event_preview(event_id: int, session: Session = Depends(get_session)):
    event = session.get(VideoAnalysisEvent, event_id)
    if not event or not event.preview_path:
        raise HTTPException(status_code=404, detail="Превью события не найдено")

    path = Path(event.preview_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл превью не найден")

    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.post(
    "/jobs",
    response_model=VideoAnalysisJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*ALLOWED_ROLES))],
)
async def create_job(
    video: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    suffix = Path(video.filename or "video").suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Поддерживаются только видеофайлы mp4/avi/mov/mkv/webm")

    temp_job = VideoAnalysisJob(
        original_filename=video.filename or "video",
        source_path="",
        status="queued",
        created_by_user_id=current_user.id,
    )
    session.add(temp_job)
    session.commit()
    session.refresh(temp_job)

    job_dir = BASE_STORAGE_DIR / f"job_{temp_job.id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / f"source{suffix}"

    with video_path.open("wb") as buffer:
        shutil.copyfileobj(video.file, buffer)

    temp_job.source_path = str(video_path)
    session.add(temp_job)
    session.commit()
    session.refresh(temp_job)

    schedule_video_analysis(temp_job.id)
    return _job_read(temp_job)
