from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from sqlmodel import Session, select

from app.core.config import PROJECT_ROOT, settings
from app.core.database import engine
from app.models.cameras import Camera
from app.models.guest_route_analysis_jobs import GuestRouteAnalysisJob
from app.models.guests import Guest
from app.models.logs import TrackingLog
from app.services.guest_route_service import build_guest_probable_route
from app.services.recognition_service import cosine_distance, find_matching_person_in_frame
from app.services.reid_service import extract_body_detections, update_guest_body_embedding
from app.services.websocket_manager import guest_route_analysis_job_topic, topic_ws_manager

logger = logging.getLogger(__name__)

VIDEO_FILE_PREFIX = "file://"
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^/[A-Za-z]:[\\/]")
DEFAULT_SAMPLE_INTERVAL_SEC = max(0.5, settings.route_analysis_sample_interval_sec)
TIME_WINDOW_PADDING_SEC = 5.0
RUNNING_JOB_STATUSES = ("queued", "processing")

_active_jobs: set[int] = set()
_active_jobs_lock = threading.Lock()


@dataclass(frozen=True)
class OfflineCameraSource:
    camera: Camera
    path: Path
    duration_sec: float


@dataclass(frozen=True)
class TargetBodyMatch:
    distance: float
    similarity: float
    embedding: list[float]


@dataclass(frozen=True)
class TargetAppearanceCandidate:
    timestamp_sec: float
    confidence: float
    body_match: TargetBodyMatch | None
    face_confirmed: bool


def _normalize_video_file_path(raw_path: str) -> Path:
    normalized = raw_path.strip()
    if WINDOWS_ABSOLUTE_PATH_RE.match(normalized):
        normalized = normalized[1:]

    path = Path(normalized).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve(strict=False)


def _resolve_camera_video_path(camera: Camera) -> Path | None:
    source = (camera.ip_address or "").strip()
    if not source.lower().startswith(VIDEO_FILE_PREFIX):
        return None

    return _normalize_video_file_path(source[len(VIDEO_FILE_PREFIX):])


@lru_cache(maxsize=1)
def _parse_camera_time_offsets() -> dict[str, float]:
    offsets: dict[str, float] = {}
    raw_value = settings.route_analysis_camera_time_offsets_raw
    if not raw_value:
        return offsets

    for item in raw_value.split(","):
        normalized = item.strip()
        if not normalized:
            continue

        separator = "=" if "=" in normalized else ":"
        if separator not in normalized:
            logger.warning("Некорректный time-offset камеры: %s", normalized)
            continue

        key, value = normalized.rsplit(separator, 1)
        key = key.strip()
        if not key:
            continue
        try:
            offsets[key] = float(value.strip())
        except ValueError:
            logger.warning("Некорректное значение time-offset камеры: %s", normalized)

    return offsets


def _camera_time_offset_sec(camera: Camera) -> float:
    offsets = _parse_camera_time_offsets()
    return offsets.get(str(camera.id), offsets.get(camera.name, 0.0))


def _read_video_duration(path: Path) -> float:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return 0.0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        if fps > 0 and frame_count > 0:
            return float(frame_count / fps)
        duration_ms = cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0
        return float(duration_ms / 1000.0)
    finally:
        cap.release()


def get_offline_camera_sources(session: Session, floor_id: int) -> tuple[list[OfflineCameraSource], list[str]]:
    cameras = session.exec(
        select(Camera)
        .where(Camera.floor_id == floor_id, Camera.is_active.is_(True))
        .order_by(Camera.name.asc(), Camera.id.asc())
    ).all()

    sources: list[OfflineCameraSource] = []
    warnings: list[str] = []
    for camera in cameras:
        path = _resolve_camera_video_path(camera)
        if path is None:
            continue
        if not path.exists():
            warnings.append(f"Видео камеры {camera.name} не найдено: {path}")
            continue

        duration_sec = _read_video_duration(path)
        if duration_sec <= 0:
            warnings.append(f"Не удалось определить длительность видео камеры {camera.name}")
            continue

        sources.append(OfflineCameraSource(camera=camera, path=path, duration_sec=duration_sec))

    return sources, warnings


def count_configured_offline_cameras(session: Session, floor_id: int) -> int:
    cameras = session.exec(
        select(Camera).where(Camera.floor_id == floor_id, Camera.is_active.is_(True))
    ).all()
    return sum(
        1
        for camera in cameras
        if (camera.ip_address or "").strip().lower().startswith(VIDEO_FILE_PREFIX)
    )


def create_guest_route_analysis_job(session: Session, guest_id: int, floor_id: int) -> GuestRouteAnalysisJob:
    expire_stale_route_analysis_jobs(session)

    guest = session.get(Guest, guest_id)
    if not guest:
        raise ValueError("Гость не найден")
    if not guest.body_embedding:
        raise ValueError("Для построения маршрута нужно добавить фото полного роста для Re-ID")

    sources, warnings = get_offline_camera_sources(session, floor_id)
    if not sources:
        detail = "На выбранном этаже нет активных камер с источником file://"
        if warnings:
            detail = f"{detail}. {'; '.join(warnings)}"
        raise ValueError(detail)

    job = GuestRouteAnalysisJob(
        guest_id=guest_id,
        floor_id=floor_id,
        status="queued",
        warnings_json=warnings,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _update_job(job_id: int, **updates) -> None:
    with Session(engine) as session:
        job = session.get(GuestRouteAnalysisJob, job_id)
        if not job:
            return
        for key, value in updates.items():
            setattr(job, key, value)
        session.add(job)
        session.commit()
        session.refresh(job)
        _publish_job_update(session, job)


def _append_job_warning(job: GuestRouteAnalysisJob, warning: str) -> None:
    warnings = list(job.warnings_json or [])
    warnings.append(warning)
    job.warnings_json = warnings


def _fail_job(
    session: Session,
    job: GuestRouteAnalysisJob,
    *,
    error_message: str,
    finished_at: datetime | None = None,
) -> None:
    job.status = "failed"
    job.finished_at = finished_at or datetime.now()
    job.error_message = error_message
    session.add(job)
    session.commit()
    session.refresh(job)
    _publish_job_update(session, job)


def expire_stale_route_analysis_jobs(session: Session) -> int:
    """Fail jobs that are still marked as running after the configured timeout."""
    timeout_sec = max(60.0, float(settings.route_analysis_job_timeout_sec))
    now = datetime.now()
    stale_jobs = session.exec(
        select(GuestRouteAnalysisJob).where(
            GuestRouteAnalysisJob.status.in_(RUNNING_JOB_STATUSES)
        )
    ).all()

    expired_count = 0
    for job in stale_jobs:
        reference_time = job.started_at or job.created_at
        if (now - reference_time).total_seconds() <= timeout_sec:
            continue

        _fail_job(
            session,
            job,
            error_message=(
                "Офлайн-анализ маршрута не завершился за допустимое время. "
                "Запустите анализ заново; если повторяется, уменьшите число активных "
                "file:// камер или увеличьте ROUTE_ANALYSIS_JOB_TIMEOUT_SEC."
            ),
            finished_at=now,
        )
        expired_count += 1

    return expired_count


def fail_interrupted_route_analysis_jobs() -> int:
    """Fail jobs left in running states after backend restart/reload."""
    with Session(engine) as session:
        interrupted_jobs = session.exec(
            select(GuestRouteAnalysisJob).where(
                GuestRouteAnalysisJob.status.in_(RUNNING_JOB_STATUSES)
            )
        ).all()
        now = datetime.now()
        for job in interrupted_jobs:
            _fail_job(
                session,
                job,
                error_message=(
                    "Офлайн-анализ маршрута был прерван при перезапуске backend. "
                    "Запустите построение маршрута заново."
                ),
                finished_at=now,
            )
        return len(interrupted_jobs)


def _target_body_match(
    frame_bgr: np.ndarray,
    guest_vector: np.ndarray,
    *,
    max_distance: float,
) -> TargetBodyMatch | None:
    detections = extract_body_detections(frame_bgr)
    best_match: TargetBodyMatch | None = None

    for detection in detections:
        detection_vector = np.asarray(detection.embedding, dtype=np.float32)
        if detection_vector.shape != guest_vector.shape:
            continue

        distance = cosine_distance(detection_vector, guest_vector)
        if distance > max_distance:
            continue

        similarity = max(0.0, min(1.0, 1.0 - float(distance)))
        match = TargetBodyMatch(distance=float(distance), similarity=similarity, embedding=detection.embedding)
        if best_match is None or match.distance < best_match.distance:
            best_match = match

    return best_match


def _is_better_candidate(
    candidate: TargetAppearanceCandidate,
    current_best: TargetAppearanceCandidate | None,
) -> bool:
    if current_best is None:
        return True
    if candidate.face_confirmed != current_best.face_confirmed:
        return candidate.face_confirmed
    return candidate.confidence > current_best.confidence


def _face_confirms_guest(frame_bgr: np.ndarray, session: Session, guest: Guest) -> bool:
    face_match = find_matching_person_in_frame(frame_bgr, session)
    return bool(
        face_match.person_type == "guest"
        and face_match.person is not None
        and face_match.person.id == guest.id
        and face_match.decision == "auto_allow"
    )


def _write_tracking_log(
    session: Session,
    *,
    guest_id: int,
    camera_id: int,
    timestamp: datetime,
    confidence: float,
) -> None:
    session.add(
        TrackingLog(
            guest_id=guest_id,
            camera_id=camera_id,
            timestamp=timestamp,
            confidence=confidence,
        )
    )


def _process_camera_video(
    *,
    session: Session,
    job: GuestRouteAnalysisJob,
    source: OfflineCameraSource,
    guest: Guest,
    guest_vector: np.ndarray,
    time_from: datetime,
    sample_interval_sec: float,
) -> int:
    cap = cv2.VideoCapture(str(source.path))
    if not cap.isOpened():
        _append_job_warning(job, f"Не удалось открыть видео камеры {source.camera.name}")
        return 0

    best_candidate: TargetAppearanceCandidate | None = None
    first_reliable_candidate: TargetAppearanceCandidate | None = None
    timestamp_sec = 0.0

    try:
        while timestamp_sec <= source.duration_sec:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                timestamp_sec += sample_interval_sec
                continue

            body_match = _target_body_match(
                frame,
                guest_vector,
                max_distance=settings.route_analysis_body_match_distance,
            )
            face_confirmed = False
            if body_match is None:
                face_confirmed = _face_confirms_guest(frame, session, guest)
            elif body_match.similarity < 0.72:
                face_confirmed = _face_confirms_guest(frame, session, guest)

            if body_match is None and not face_confirmed:
                timestamp_sec += sample_interval_sec
                continue

            confidence = body_match.similarity if body_match else 0.95
            if face_confirmed and body_match is not None:
                confidence = max(confidence, 0.97)
            elif body_match and body_match.distance > settings.reid_match_distance:
                # Offline route reconstruction is softer than live access control:
                # we pick the best appearance on each known camera instead of
                # requiring the strict real-time Re-ID threshold on every frame.
                confidence = max(0.45, min(0.85, confidence))

            candidate = TargetAppearanceCandidate(
                timestamp_sec=float(timestamp_sec),
                confidence=float(confidence),
                body_match=body_match,
                face_confirmed=face_confirmed,
            )
            if _is_better_candidate(candidate, best_candidate):
                best_candidate = candidate
            if (
                first_reliable_candidate is None
                and (
                    candidate.face_confirmed
                    or candidate.confidence >= settings.route_analysis_event_min_similarity
                )
            ):
                first_reliable_candidate = candidate

            timestamp_sec += sample_interval_sec
    finally:
        cap.release()

    selected_candidate = first_reliable_candidate or best_candidate
    if selected_candidate is None:
        return 0

    event_time = time_from + timedelta(
        seconds=selected_candidate.timestamp_sec + _camera_time_offset_sec(source.camera)
    )
    if best_candidate and best_candidate.face_confirmed and best_candidate.body_match is not None:
        update_guest_body_embedding(session, guest, best_candidate.body_match.embedding)

    _write_tracking_log(
        session,
        guest_id=guest.id,
        camera_id=source.camera.id,
        timestamp=event_time,
        confidence=selected_candidate.confidence,
    )
    session.commit()
    return 1


def _run_job(job_id: int) -> None:
    _update_job(job_id, status="processing", started_at=datetime.now(), error_message=None)

    try:
        with Session(engine) as session:
            job = session.get(GuestRouteAnalysisJob, job_id)
            if not job:
                return

            guest = session.get(Guest, job.guest_id)
            if not guest or not guest.body_embedding:
                raise ValueError("Гость не найден или у него нет body_embedding")

            sources, source_warnings = get_offline_camera_sources(session, job.floor_id)
            if not sources:
                raise ValueError("На выбранном этаже нет доступных file:// видео для анализа")

            for warning in source_warnings:
                _append_job_warning(job, warning)

            max_duration = max(source.duration_sec for source in sources)
            camera_offsets = [_camera_time_offset_sec(source.camera) for source in sources]
            min_offset = min(camera_offsets, default=0.0)
            max_offset = max(camera_offsets, default=0.0)
            video_base_time = datetime.now() - timedelta(seconds=max_duration + TIME_WINDOW_PADDING_SEC)
            job.time_from = video_base_time + timedelta(seconds=min(0.0, min_offset))
            job.time_to = video_base_time + timedelta(
                seconds=max_duration + TIME_WINDOW_PADDING_SEC + max(0.0, max_offset)
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            _publish_job_update(session, job)

            guest_vector = np.asarray(guest.body_embedding, dtype=np.float32)
            processed_cameras = 0
            events_written = 0

            for source in sources:
                try:
                    events_written += _process_camera_video(
                        session=session,
                        job=job,
                        source=source,
                        guest=guest,
                        guest_vector=guest_vector,
                        time_from=video_base_time,
                        sample_interval_sec=DEFAULT_SAMPLE_INTERVAL_SEC,
                    )
                except Exception:
                    logger.exception("Ошибка офлайн-анализа камеры %s", source.camera.id)
                    _append_job_warning(job, f"Ошибка анализа камеры {source.camera.name}")

                processed_cameras += 1
                job.processed_cameras = processed_cameras
                job.events_written = events_written
                session.add(job)
                session.commit()
                session.refresh(job)
                _publish_job_update(session, job)

            if events_written == 0:
                _append_job_warning(job, "Гость не найден на видео выбранного этажа")

            job.status = "completed"
            job.finished_at = datetime.now()
            job.events_written = events_written
            session.add(job)
            session.commit()
            session.refresh(job)
            _publish_job_update(session, job)
    except Exception as exc:
        logger.exception("Ошибка офлайн-построения маршрута гостя для job_id=%s", job_id)
        _update_job(
            job_id,
            status="failed",
            finished_at=datetime.now(),
            error_message=str(exc),
        )


def _process_job(job_id: int) -> None:
    with _active_jobs_lock:
        if job_id in _active_jobs:
            return
        _active_jobs.add(job_id)

    try:
        _run_job(job_id)
    finally:
        with _active_jobs_lock:
            _active_jobs.discard(job_id)


def schedule_guest_route_analysis(job_id: int) -> None:
    thread = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
    thread.start()


def build_job_payload(session: Session, job: GuestRouteAnalysisJob) -> dict:
    if job.status in RUNNING_JOB_STATUSES:
        expire_stale_route_analysis_jobs(session)
        session.refresh(job)

    probable_route = None
    route_warnings: list[str] = []
    if job.status == "completed" and job.time_from and job.time_to:
        try:
            probable_route = build_guest_probable_route(
                session=session,
                guest_id=job.guest_id,
                floor_id=job.floor_id,
                time_from=job.time_from,
                time_to=job.time_to,
            )
            route_warnings = probable_route.get("warnings") or []
        except Exception as exc:
            route_warnings = [f"Не удалось построить вероятный маршрут: {exc}"]

    warnings = list(job.warnings_json or [])
    for warning in route_warnings:
        if warning not in warnings:
            warnings.append(warning)

    return {
        "id": job.id,
        "guest_id": job.guest_id,
        "floor_id": job.floor_id,
        "status": job.status,
        "time_from": job.time_from,
        "time_to": job.time_to,
        "processed_cameras": job.processed_cameras,
        "total_cameras": count_configured_offline_cameras(session, job.floor_id),
        "events_written": job.events_written,
        "warnings": warnings,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "probable_route": probable_route,
    }


def _publish_job_update(session: Session, job: GuestRouteAnalysisJob) -> None:
    if job.id is None:
        return
    topic_ws_manager.publish(
        guest_route_analysis_job_topic(job.id),
        build_job_payload(session, job),
    )
