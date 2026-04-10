from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

import cv2
from sqlmodel import Session, select

from app.core.database import engine
from app.models.employees import Employee
from app.models.guests import Guest
from app.models.video_analysis import VideoAnalysisEvent, VideoAnalysisJob
from app.services.recognition_service import find_matching_employee
from app.services.video_readers import create_frame_reader
from PIL import Image, ImageDraw, ImageFont
import numpy as np

BASE_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "video_analysis"
BASE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

_active_jobs: set[int] = set()
_active_jobs_lock = threading.Lock()


def _job_dir(job_id: int) -> Path:
    path = BASE_STORAGE_DIR / f"job_{job_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path




def _cleanup_job_artifacts(job_id: int):
    job_dir = _job_dir(job_id)
    for preview_path in job_dir.glob("event_*.jpg"):
        try:
            preview_path.unlink()
        except Exception:
            pass


def reset_video_analysis_job(job_id: int) -> bool:
    with _active_jobs_lock:
        if job_id in _active_jobs:
            return False

    _cleanup_job_artifacts(job_id)

    with Session(engine) as session:
        job = session.get(VideoAnalysisJob, job_id)
        if not job:
            return False

        events = session.exec(select(VideoAnalysisEvent).where(VideoAnalysisEvent.job_id == job_id)).all()
        for event in events:
            session.delete(event)

        job.status = "queued"
        job.reader_backend = None
        job.total_frames = None
        job.analyzed_frames = 0
        job.duration_sec = None
        job.granted_count = 0
        job.denied_count = 0
        job.started_at = None
        job.finished_at = None
        job.error_message = None
        session.add(job)
        session.commit()

    return True

def _person_name(person) -> str | None:
    if not person:
        return None
    return " ".join(
        part for part in [person.last_name, person.first_name, getattr(person, "middle_name", None)] if part
    ).strip() or None


FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
]

def _get_font(size: int = 28):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

def _draw_preview(frame, lines: list[str]):
    preview = frame.copy()
    overlay = preview.copy()
    cv2.rectangle(overlay, (12, 12), (min(preview.shape[1] - 12, 920), 140), (15, 23, 42), -1)
    preview = cv2.addWeighted(overlay, 0.35, preview, 0.65, 0)

    rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    font = _get_font(28)

    y = 24
    for line in lines:
        draw.text((24, y), line, font=font, fill=(255, 255, 255))
        y += 34

    result = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return result


def _save_event_preview(job_id: int, frame_index: int, frame, status_label: str, detail_label: str, timestamp_sec: float) -> str:
    preview = _draw_preview(
        frame,
        [
            f"Статус: {status_label}",
            detail_label,
            f"Время в видео: {timestamp_sec:.2f} сек",
        ],
    )
    preview_path = _job_dir(job_id) / f"event_{frame_index}.jpg"
    cv2.imwrite(str(preview_path), preview, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    return str(preview_path)


def _build_similarity(distance: float | None) -> float | None:
    if distance is None:
        return None
    value = 1.0 - float(distance)
    return max(0.0, min(1.0, value))


def _update_job_status(job_id: int, status: str, **extra):
    with Session(engine) as session:
        job = session.get(VideoAnalysisJob, job_id)
        if not job:
            return
        job.status = status
        for key, value in extra.items():
            setattr(job, key, value)
        session.add(job)
        session.commit()


def _process_job(job_id: int):
    with _active_jobs_lock:
        if job_id in _active_jobs:
            return
        _active_jobs.add(job_id)

    try:
        _run_job(job_id)
    finally:
        with _active_jobs_lock:
            _active_jobs.discard(job_id)


def _run_job(job_id: int):
    _update_job_status(job_id, "processing", started_at=datetime.now(), error_message=None)

    with Session(engine) as session:
        job = session.get(VideoAnalysisJob, job_id)
        if not job:
            return
        source_path = job.source_path

    reader = None
    try:
        reader = create_frame_reader(source_path, is_live=False)
        _update_job_status(job_id, "processing", reader_backend=reader.backend_name, total_frames=reader.frame_count)

        frame_index = 0
        analyzed_frames = 0
        granted_count = 0
        denied_count = 0
        next_sample_at = 0.0
        sample_interval_sec = 0.75
        event_cooldown_sec = 1.5
        event_seen_at: dict[str, float] = {}
        inferred_fps = reader.fps or 25.0
        last_timestamp_sec = 0.0

        while True:
            result = reader.read()
            if result is None:
                break

            frame, timestamp_sec = result
            frame_index += 1

            if timestamp_sec is None:
                timestamp_sec = frame_index / inferred_fps
            last_timestamp_sec = max(last_timestamp_sec, float(timestamp_sec))

            if timestamp_sec < next_sample_at:
                continue
            next_sample_at = float(timestamp_sec) + sample_interval_sec

            ok, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            if not ok:
                continue

            analyzed_frames += 1
            image_bytes = buffer.tobytes()

            with Session(engine) as session:
                person, person_type, distance, decision = find_matching_employee(image_bytes, session)

                if person is None and distance is None:
                    continue

                status = 'granted' if person is not None and decision == 'auto_allow' else 'denied'
                if status == 'granted':
                    granted_count += 1
                else:
                    denied_count += 1

                person_name = _person_name(person)
                entity_id = getattr(person, 'id', None) if person is not None else None
                dedup_key = f"{status}:{person_type or 'unknown'}:{entity_id or 0}"
                last_seen_at = event_seen_at.get(dedup_key, -9999.0)
                if float(timestamp_sec) - last_seen_at < event_cooldown_sec:
                    continue
                event_seen_at[dedup_key] = float(timestamp_sec)

                similarity = _build_similarity(distance)
                status_label = 'ДОСТУП РАЗРЕШЕН' if status == 'granted' else 'ДОСТУП ЗАПРЕЩЕН'
                detail_label = person_name or 'Неизвестное лицо'
                preview_path = _save_event_preview(job_id, frame_index, frame, status_label, detail_label, float(timestamp_sec))

                event = VideoAnalysisEvent(
                    job_id=job_id,
                    frame_index=frame_index,
                    timestamp_sec=float(timestamp_sec),
                    status=status,
                    person_type=person_type,
                    person_id=entity_id,
                    person_name=person_name,
                    decision=decision,
                    confidence=similarity,
                    distance=float(distance) if distance is not None else None,
                    preview_path=preview_path,
                )
                session.add(event)

                job = session.get(VideoAnalysisJob, job_id)
                if job:
                    job.analyzed_frames = analyzed_frames
                    job.granted_count = granted_count
                    job.denied_count = denied_count
                    job.duration_sec = last_timestamp_sec
                    job.total_frames = reader.frame_count or frame_index
                    job.reader_backend = reader.backend_name
                    session.add(job)
                session.commit()

        _update_job_status(
            job_id,
            'completed',
            analyzed_frames=analyzed_frames,
            granted_count=granted_count,
            denied_count=denied_count,
            duration_sec=last_timestamp_sec,
            total_frames=reader.frame_count or frame_index,
            finished_at=datetime.now(),
        )
    except Exception as exc:
        _update_job_status(
            job_id,
            'failed',
            finished_at=datetime.now(),
            error_message=str(exc),
        )
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass


def schedule_video_analysis(job_id: int):
    thread = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
    thread.start()
