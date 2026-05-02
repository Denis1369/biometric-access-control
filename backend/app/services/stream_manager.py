from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
import re
import threading
import time
from io import BytesIO

import numpy as np
from PIL import Image
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.models.cameras import Camera
from app.models.logs import AccessLog, TrackingLog
from app.services.recognition_service import find_matching_person_in_frame
from app.services.reid_service import (
    detect_person_presence,
    match_guest_by_body,
    update_guest_body_embedding_from_frame,
)
from app.services.video_readers import BaseFrameReader, create_frame_reader

logger = logging.getLogger(__name__)
ml_lock = threading.Lock()
try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = Image.LANCZOS

VIDEO_FILE_PREFIX = "file://"
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^/[A-Za-z]:[\\/]")
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class StreamSourceConfig:
    raw_value: str
    resolved_value: str
    source_kind: str

    @property
    def is_live(self) -> bool:
        return self.source_kind == "live"

    @property
    def should_loop(self) -> bool:
        return self.source_kind == "video_file"


def _normalize_video_file_path(raw_path: str) -> str:
    normalized = raw_path.strip()
    if WINDOWS_ABSOLUTE_PATH_RE.match(normalized):
        normalized = normalized[1:]

    path = Path(normalized).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return str(path.resolve(strict=False))


def _parse_stream_source(source_value: str) -> StreamSourceConfig:
    normalized = source_value.strip()
    if normalized.lower().startswith(VIDEO_FILE_PREFIX):
        raw_path = normalized[len(VIDEO_FILE_PREFIX):]
        return StreamSourceConfig(
            raw_value=normalized,
            resolved_value=_normalize_video_file_path(raw_path),
            source_kind="video_file",
        )

    return StreamSourceConfig(
        raw_value=normalized,
        resolved_value=normalized,
        source_kind="live",
    )


def _encode_frame_to_jpeg(
    frame,
    quality: int = 72,
    max_width: int | None = None,
    max_height: int | None = None,
) -> bytes | None:
    try:
        image = Image.fromarray(frame[:, :, ::-1].copy(), mode="RGB")
        if max_width or max_height:
            limit = (
                max_width if max_width is not None else image.width,
                max_height if max_height is not None else image.height,
            )
            image.thumbnail(limit, RESAMPLE_LANCZOS)
        buffer = BytesIO()
        image.save(
            buffer,
            format="JPEG",
            quality=quality,
            subsampling=1,
            optimize=False,
            progressive=False,
        )
        return buffer.getvalue()
    except Exception:
        return None


class CameraStreamWorker:
    def __init__(self, camera_id: int, source_value: str, direction: str):
        self.camera_id = camera_id
        self.source_config = _parse_stream_source(source_value)
        self.direction = direction
        self.is_running = False

        self.capture_thread = None
        self.recognition_thread = None

        self.reader: BaseFrameReader | None = None
        self.reader_lock = threading.Lock()

        self.latest_frame: bytes | None = None
        self.latest_frame_for_recognition: np.ndarray | None = None
        self.latest_frame_version = 0
        self.frame_lock = threading.Lock()
        self.recognition_frame_lock = threading.Lock()

        self.last_frame_at = 0.0
        self.cooldowns: dict[str, float] = {}
        self.recognition_interval = 0.75
        self.access_cooldown_sec = 60.0
        self.tracking_cooldown_sec = 15.0
        self.demo_recognition_ttl_sec = 8.0
        self.demo_recognition_enabled_until = 0.0
        self.recognition_state_lock = threading.Lock()
        self.restart_playback_requested = False
        self.stream_target_fps = 10
        self.jpeg_quality = 82
        self.preview_max_width = 1280
        self.preview_max_height = 720
        self.last_empty_trigger_log_at = 0.0
        self.trigger_unavailable_logged = False

    def start(self):
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.recognition_thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self.capture_thread.start()
        self.recognition_thread.start()

    def stop(self):
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.recognition_thread:
            self.recognition_thread.join(timeout=2)
        self._release_reader()

    def _release_reader(self):
        with self.reader_lock:
            if self.reader:
                try:
                    self.reader.close()
                except Exception:
                    pass
                self.reader = None

    def _open_reader(self) -> BaseFrameReader | None:
        self._release_reader()
        try:
            reader = create_frame_reader(
                self.source_config.resolved_value,
                is_live=self.source_config.is_live,
            )
            with self.reader_lock:
                self.reader = reader
            return reader
        except Exception as exc:
            logger.warning(
                "Камера %s: ошибка открытия источника %s",
                self.camera_id,
                exc,
            )
            return None

    def _wait_for_recorded_frame(
        self,
        reader: BaseFrameReader,
        frame_timestamp: float | None,
        playback_started_at: float | None,
        first_frame_timestamp: float | None,
        last_frame_sent_at: float | None,
    ) -> tuple[float, float | None, float | None, float | None]:
        now = time.time()

        if frame_timestamp is not None:
            if playback_started_at is None:
                playback_started_at = now
                first_frame_timestamp = frame_timestamp

            base_timestamp = first_frame_timestamp if first_frame_timestamp is not None else frame_timestamp
            target_time = playback_started_at + max(0.0, frame_timestamp - base_timestamp)
            sleep_for = target_time - now
            if sleep_for > 0:
                time.sleep(min(sleep_for, 1.0))
            now = time.time()
            return now, playback_started_at, first_frame_timestamp, now

        fps = reader.fps or self.stream_target_fps
        frame_interval = 1.0 / max(fps, 1.0)
        if last_frame_sent_at is not None:
            sleep_for = frame_interval - (now - last_frame_sent_at)
            if sleep_for > 0:
                time.sleep(min(sleep_for, 1.0))
            now = time.time()
        elif playback_started_at is None:
            playback_started_at = now

        return now, playback_started_at, first_frame_timestamp, now

    def _set_latest_frame(self, frame_bytes: bytes | None):
        with self.frame_lock:
            self.latest_frame = frame_bytes
            self.last_frame_at = time.time() if frame_bytes else 0.0
            if frame_bytes:
                self.latest_frame_version += 1

    def _set_recognition_frame(self, frame_bgr: np.ndarray | None):
        with self.recognition_frame_lock:
            self.latest_frame_for_recognition = None if frame_bgr is None else frame_bgr.copy()

    def is_demo_source(self) -> bool:
        return self.source_config.source_kind == "video_file"

    def is_recognition_enabled(self) -> bool:
        if self.source_config.is_live:
            return True

        with self.recognition_state_lock:
            return time.time() < self.demo_recognition_enabled_until

    def set_demo_recognition_enabled(self, enabled: bool) -> bool:
        if self.source_config.is_live:
            return True

        with self.recognition_state_lock:
            was_enabled = time.time() < self.demo_recognition_enabled_until
            if enabled:
                self.demo_recognition_enabled_until = time.time() + self.demo_recognition_ttl_sec
                if not was_enabled:
                    self.cooldowns.clear()
                    self.restart_playback_requested = True
            else:
                self.demo_recognition_enabled_until = 0.0
                self.cooldowns.clear()
                self.restart_playback_requested = False

        if not enabled:
            self._set_recognition_frame(None)

        return self.is_recognition_enabled()

    def get_latest_frame(self, max_age_sec: float = 3.0) -> bytes | None:
        payload = self.get_latest_frame_payload(max_age_sec=max_age_sec)
        if payload is None:
            return None
        return payload[0]

    def get_latest_frame_payload(self, max_age_sec: float = 3.0) -> tuple[bytes, int] | None:
        with self.frame_lock:
            if not self.latest_frame or (time.time() - self.last_frame_at > max_age_sec):
                return None
            return self.latest_frame, self.latest_frame_version

    def _capture_loop(self):
        reconnect_delay = 2.0
        frame_interval = 1.0 / self.stream_target_fps
        last_encode_time = 0.0
        playback_started_at: float | None = None
        first_frame_timestamp: float | None = None
        last_recorded_frame_at: float | None = None

        while self.is_running:
            try:
                if self.source_config.should_loop and self.restart_playback_requested:
                    self.restart_playback_requested = False
                    self._set_latest_frame(None)
                    self._set_recognition_frame(None)
                    self._release_reader()
                    playback_started_at = None
                    first_frame_timestamp = None
                    last_recorded_frame_at = None

                with self.reader_lock:
                    reader = self.reader

                if reader is None:
                    reader = self._open_reader()
                    if reader is None:
                        time.sleep(reconnect_delay)
                        continue
                    playback_started_at = None
                    first_frame_timestamp = None
                    last_recorded_frame_at = None
                    logger.info("Камера %s: поток подключен", self.camera_id)

                result = reader.read()
                if result is None:
                    if self.source_config.should_loop:
                        self.cooldowns.clear()
                        self._release_reader()
                        time.sleep(0.1)
                        playback_started_at = None
                        first_frame_timestamp = None
                        last_recorded_frame_at = None
                        continue

                    logger.warning(
                        "Камера %s: поток недоступен, переподключение",
                        self.camera_id,
                    )
                    self._set_latest_frame(None)
                    self._release_reader()
                    time.sleep(reconnect_delay)
                    continue

                frame, frame_timestamp = result
                if self.source_config.is_live:
                    current_time = time.time()
                    if current_time - last_encode_time < frame_interval:
                        continue
                else:
                    (
                        current_time,
                        playback_started_at,
                        first_frame_timestamp,
                        last_recorded_frame_at,
                    ) = self._wait_for_recorded_frame(
                        reader,
                        frame_timestamp,
                        playback_started_at,
                        first_frame_timestamp,
                        last_recorded_frame_at,
                    )

                image_bytes = _encode_frame_to_jpeg(
                    frame,
                    quality=self.jpeg_quality,
                    max_width=self.preview_max_width,
                    max_height=self.preview_max_height,
                )
                if image_bytes is None:
                    continue

                self._set_latest_frame(image_bytes)
                self._set_recognition_frame(frame)
                last_encode_time = current_time
            except Exception:
                logger.exception("Камера %s: ошибка захвата кадра", self.camera_id)
                self._release_reader()
                time.sleep(reconnect_delay)

    def _recognition_loop(self):
        while self.is_running:
            try:
                if not self.is_recognition_enabled():
                    with self.recognition_frame_lock:
                        self.latest_frame_for_recognition = None
                    time.sleep(0.2)
                    continue

                with self.recognition_frame_lock:
                    frame_bgr = self.latest_frame_for_recognition
                    self.latest_frame_for_recognition = None

                if frame_bgr is not None:
                    self._handle_access(frame_bgr)

                time.sleep(self.recognition_interval)
            except Exception:
                logger.exception("Камера %s: ошибка распознавания", self.camera_id)
                time.sleep(0.5)

    def _should_emit_event(self, cooldown_key: str, ttl_sec: float) -> bool:
        current_time = time.time()
        last_seen = self.cooldowns.get(cooldown_key, 0.0)
        if current_time - last_seen <= ttl_sec:
            return False
        self.cooldowns[cooldown_key] = current_time
        return True

    @staticmethod
    def _match_confidence(distance: float | None) -> float | None:
        if distance is None:
            return None
        return max(0.0, min(1.0, 1.0 - float(distance)))

    def _write_access_log(
        self,
        session: Session,
        *,
        employee_id: int | None = None,
        guest_id: int | None = None,
        status: str,
        confidence: float | None = None,
    ) -> None:
        session.add(
            AccessLog(
                employee_id=employee_id,
                guest_id=guest_id,
                camera_id=self.camera_id,
                status=status,
                confidence=confidence,
            )
        )

    def _write_tracking_log(
        self,
        session: Session,
        *,
        guest_id: int | None = None,
        employee_id: int | None = None,
        confidence: float,
    ) -> None:
        session.add(
            TrackingLog(
                guest_id=guest_id,
                employee_id=employee_id,
                camera_id=self.camera_id,
                confidence=confidence,
            )
        )

    def _handle_access(self, frame_bgr: np.ndarray):
        if settings.analysis_trigger_enabled:
            with ml_lock:
                presence_detections = detect_person_presence(frame_bgr)
            if presence_detections is None:
                if not self.trigger_unavailable_logged:
                    self.trigger_unavailable_logged = True
                    logger.warning(
                        "Камера %s: YOLO-триггер недоступен, анализ продолжается без фильтра пустых кадров",
                        self.camera_id,
                    )
            elif not presence_detections:
                current_time = time.time()
                if (
                    current_time - self.last_empty_trigger_log_at
                    >= settings.analysis_trigger_empty_log_interval_sec
                ):
                    self.last_empty_trigger_log_at = current_time
                    logger.debug(
                        "Камера %s: YOLO не нашел человека, тяжелый анализ пропущен",
                        self.camera_id,
                    )
                return

        with Session(engine) as session:
            with ml_lock:
                face_match = find_matching_person_in_frame(frame_bgr, session)

                tracked_body_match = None
                if face_match.face_bbox is None and self.direction == "internal":
                    tracked_body_match = match_guest_by_body(frame_bgr, session)

                updated_body_detection = None
                if (
                    face_match.person is not None
                    and face_match.person_type == "guest"
                    and face_match.decision == "auto_allow"
                    and face_match.face_bbox is not None
                ):
                    updated_body_detection = update_guest_body_embedding_from_frame(
                        session,
                        face_match.person,
                        frame_bgr,
                        face_match.face_bbox,
                    )

            if face_match.person is not None and face_match.decision == "auto_allow":
                cooldown_key = f"access_{face_match.person_type}_{face_match.person.id}"
                if self._should_emit_event(cooldown_key, self.access_cooldown_sec):
                    confidence = self._match_confidence(face_match.distance)
                    if face_match.person_type == "employee":
                        self._write_access_log(
                            session,
                            employee_id=face_match.person.id,
                            status="granted",
                            confidence=confidence,
                        )
                    else:
                        self._write_access_log(
                            session,
                            guest_id=face_match.person.id,
                            status="granted",
                            confidence=confidence,
                        )
                    session.commit()
                    badge = "[ГОСТЬ]" if face_match.person_type == "guest" else "[СОТРУДНИК]"
                    logger.info(
                        "Камера %s: проход %s %s %s",
                        self.camera_id,
                        badge,
                        face_match.person.last_name,
                        face_match.person.first_name,
                    )

                if (
                    face_match.person_type == "guest"
                    and self.direction == "internal"
                    and self._should_emit_event(
                        f"tracking_face_guest_{face_match.person.id}",
                        self.tracking_cooldown_sec,
                    )
                ):
                    confidence = self._match_confidence(face_match.distance) or 0.0
                    self._write_tracking_log(
                        session,
                        guest_id=face_match.person.id,
                        confidence=confidence,
                    )
                    session.commit()
                    if updated_body_detection is not None:
                        logger.info(
                            "Камера %s: обновлен body embedding гостя %s по face-confirmed кадру",
                            self.camera_id,
                            face_match.person.id,
                        )

            elif tracked_body_match is not None:
                cooldown_key = f"tracking_reid_guest_{tracked_body_match.guest.id}"
                if self._should_emit_event(cooldown_key, self.tracking_cooldown_sec):
                    self._write_tracking_log(
                        session,
                        guest_id=tracked_body_match.guest.id,
                        confidence=tracked_body_match.similarity,
                    )
                    session.commit()
                    logger.info(
                        "Камера %s: guest_id=%s найден по Re-ID (distance=%.3f, bbox=%s)",
                        self.camera_id,
                        tracked_body_match.guest.id,
                        tracked_body_match.distance,
                        tracked_body_match.detection.bbox,
                    )

            elif face_match.face_bbox is not None and face_match.distance is not None:
                if self._should_emit_event("unknown", 10.0):
                    self._write_access_log(session, status="denied", confidence=None)
                    session.commit()
                    logger.warning(
                        "Камера %s: тревога, обнаружено неизвестное лицо",
                        self.camera_id,
                    )

            if (
                updated_body_detection is not None
                and face_match.person is not None
                and session.is_modified(face_match.person, include_collections=False)
            ):
                session.commit()


class StreamManager:
    def __init__(self):
        self.workers: dict[int, CameraStreamWorker] = {}
        self.lock = threading.Lock()

    def start_all(self):
        with Session(engine) as session:
            cameras = session.exec(select(Camera).where(Camera.is_active.is_(True))).all()
            for cam in cameras:
                self.add_camera(cam.id, cam.ip_address, cam.direction)

    def add_camera(self, camera_id: int, source_value: str, direction: str):
        self.remove_camera(camera_id)
        worker = CameraStreamWorker(camera_id, source_value, direction)
        with self.lock:
            self.workers[camera_id] = worker
        worker.start()
        logger.info("Запущен поток для камеры %s", camera_id)

    def remove_camera(self, camera_id: int):
        with self.lock:
            worker = self.workers.pop(camera_id, None)
        if worker:
            worker.stop()
            logger.info("Остановлен поток для камеры %s", camera_id)

    def get_latest_frame(self, camera_id: int, max_age_sec: float = 3.0):
        with self.lock:
            worker = self.workers.get(camera_id)
        if worker:
            return worker.get_latest_frame(max_age_sec=max_age_sec)
        return None

    def get_latest_frame_payload(self, camera_id: int, max_age_sec: float = 3.0):
        with self.lock:
            worker = self.workers.get(camera_id)
        if worker:
            return worker.get_latest_frame_payload(max_age_sec=max_age_sec)
        return None

    def set_demo_recognition_enabled(self, camera_id: int, enabled: bool):
        with self.lock:
            worker = self.workers.get(camera_id)
        if worker is None:
            return None

        recognition_enabled = worker.set_demo_recognition_enabled(enabled)
        return {
            "camera_id": camera_id,
            "recognition_enabled": recognition_enabled,
            "is_demo_source": worker.is_demo_source(),
        }


stream_manager = StreamManager()
