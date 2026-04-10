from __future__ import annotations

import threading
import time
from typing import Optional

import cv2
from sqlmodel import Session, select

from app.core.database import engine
from app.models.cameras import Camera
from app.models.logs import AccessLog
from app.services.recognition_service import find_matching_employee
from app.services.video_readers import BaseFrameReader, create_frame_reader

ml_lock = threading.Lock()

class CameraStreamWorker:
    def __init__(self, camera_id: int, rtsp_url: str, direction: str):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.direction = direction
        self.is_running = False
        self.capture_thread: Optional[threading.Thread] = None
        self.recognition_thread: Optional[threading.Thread] = None

        self.latest_frame: bytes | None = None
        self.latest_frame_for_recognition: bytes | None = None
        self.last_frame_at: float = 0.0

        self.frame_lock = threading.Lock()
        self.recognition_frame_lock = threading.Lock()
        self.reader_lock = threading.Lock()
        self.reader: Optional[BaseFrameReader] = None

        self.cooldowns: dict[str, float] = {}
        self.backend_name: str | None = None
        self.recognition_interval = 0.8
        self.jpeg_quality = 95

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.recognition_thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self.capture_thread.start()
        self.recognition_thread.start()

    def stop(self):
        self.is_running = False
        self._set_latest_frame(None)
        self._set_recognition_frame(None)
        self._release_reader()
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.5)
        if self.recognition_thread and self.recognition_thread.is_alive():
            self.recognition_thread.join(timeout=1.5)

    def _set_latest_frame(self, frame_bytes: bytes | None):
        with self.frame_lock:
            self.latest_frame = frame_bytes
            self.last_frame_at = time.time() if frame_bytes else 0.0

    def _set_recognition_frame(self, frame_bytes: bytes | None):
        with self.recognition_frame_lock:
            self.latest_frame_for_recognition = frame_bytes

    def _get_recognition_frame(self) -> bytes | None:
        with self.recognition_frame_lock:
            return self.latest_frame_for_recognition

    def get_latest_frame(self, max_age_sec: float = 3.0) -> bytes | None:
        with self.frame_lock:
            if not self.latest_frame:
                return None
            if time.time() - self.last_frame_at > max_age_sec:
                return None
            return self.latest_frame

    def _release_reader(self):
        with self.reader_lock:
            reader = self.reader
            self.reader = None
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass

    def _open_reader(self) -> BaseFrameReader | None:
        self._release_reader()
        try:
            reader = create_frame_reader(self.rtsp_url, is_live=True)
        except Exception as exc:
            print(f"[Камера {self.camera_id}] Ошибка открытия источника: {exc}")
            return None

        with self.reader_lock:
            self.reader = reader
            self.backend_name = reader.backend_name
        return reader

    def _handle_access(self, image_bytes: bytes):
        with Session(engine) as session:
            with ml_lock:
                person, person_type, distance, decision = find_matching_employee(image_bytes, session)

            person, person_type, distance, decision = find_matching_employee(image_bytes, session)
            current_time = time.time()

            if person and decision == "auto_allow":
                cooldown_key = f"{person_type}_{person.id}"
                last_seen = self.cooldowns.get(cooldown_key, 0)
                if current_time - last_seen > 60:
                    self.cooldowns[cooldown_key] = current_time
                    log = AccessLog(camera_id=self.camera_id, status="granted")
                    if person_type == "employee":
                        log.employee_id = person.id
                    else:
                        log.guest_id = person.id
                    session.add(log)
                    session.commit()
                    badge = "[ГОСТЬ]" if person_type == "guest" else "[СОТРУДНИК]"
                    print(f"[Камера {self.camera_id}] Проход: {badge} {person.last_name} {person.first_name}")
            elif person is None and distance is not None:
                last_seen = self.cooldowns.get("unknown", 0)
                if current_time - last_seen > 10:
                    self.cooldowns["unknown"] = current_time
                    log = AccessLog(
                        employee_id=None,
                        camera_id=self.camera_id,
                        status="denied",
                    )
                    session.add(log)
                    session.commit()
                    print(f"[Камера {self.camera_id}] Тревога: Неизвестное лицо!")

    def _capture_loop(self):
        reconnect_delay = 1
        stale_timeout = 3.0
        frame_index = 0
        
        target_fps = 12
        frame_interval = 1.0 / target_fps
        last_encode_time = 0

        while self.is_running:
            try:
                with self.reader_lock:
                    reader = self.reader

                if reader is None:
                    reader = self._open_reader()
                    if not self.is_running:
                        break
                    if reader is None:
                        self._set_latest_frame(None)
                        self._set_recognition_frame(None)
                        print(f"[Камера {self.camera_id}] Не удалось открыть поток, повтор через {reconnect_delay} сек")
                        time.sleep(reconnect_delay)
                        continue
                    print(f"[Камера {self.camera_id}] Поток подключен через {reader.backend_name}")

                result = reader.read()
                if not self.is_running:
                    break

                if result is None:
                    self._set_latest_frame(None)
                    self._set_recognition_frame(None)
                    self._release_reader()
                    if self.is_running:
                        print(f"[Камера {self.camera_id}] Поток недоступен, переподключение...")
                        time.sleep(reconnect_delay)
                    continue

                current_time = time.time()
                if current_time - last_encode_time < frame_interval:
                    continue 

                frame, _timestamp_sec = result
                frame_index += 1

                ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if not ok:
                    continue
                
                image_bytes = buffer.tobytes()
                self._set_latest_frame(image_bytes)
                last_encode_time = current_time

                if frame_index % 2 == 0:
                    self._set_recognition_frame(image_bytes)

                if self.last_frame_at and time.time() - self.last_frame_at > stale_timeout:
                    self._set_latest_frame(None)
                    self._set_recognition_frame(None)
                    self._release_reader()
                    if self.is_running:
                        print(f"[Камера {self.camera_id}] Поток завис, принудительное переподключение...")
                        time.sleep(reconnect_delay)

            except Exception as e:
                print(f"[Камера {self.camera_id}] Ошибка воркера захвата: {e}")
                self._set_latest_frame(None)
                self._set_recognition_frame(None)
                self._release_reader()
                if self.is_running:
                    time.sleep(reconnect_delay)

        self._set_latest_frame(None)
        self._set_recognition_frame(None)
        self._release_reader()

    def _recognition_loop(self):
        while self.is_running:
            try:
                frame_bytes = self._get_recognition_frame()
                if frame_bytes:
                    self._handle_access(frame_bytes)
                time.sleep(self.recognition_interval)
            except Exception as recog_error:
                print(f"[Камера {self.camera_id}] Ошибка распознавания: {recog_error}")
                time.sleep(0.2)


class StreamManager:
    def __init__(self):
        self.workers: dict[int, CameraStreamWorker] = {}
        self.lock = threading.Lock()

    def start_all(self):
        with Session(engine) as session:
            cameras = session.exec(select(Camera).where(Camera.is_active == True)).all()
            for cam in cameras:
                self.add_camera(cam.id, cam.ip_address, cam.direction)

    def add_camera(self, camera_id: int, rtsp_url: str, direction: str):
        self.remove_camera(camera_id)
        worker = CameraStreamWorker(camera_id, rtsp_url, direction)
        with self.lock:
            self.workers[camera_id] = worker
        worker.start()
        print(f"[StreamManager] Запущен поток для камеры {camera_id}")

    def remove_camera(self, camera_id: int):
        with self.lock:
            worker = self.workers.pop(camera_id, None)
        if worker:
            worker.stop()
            if worker.capture_thread and worker.capture_thread.is_alive():
                print(f"[StreamManager] Запрошена остановка потока для камеры {camera_id}")
            else:
                print(f"[StreamManager] Остановлен поток для камеры {camera_id}")

    def get_latest_frame(self, camera_id: int, max_age_sec: float = 3.0):
        with self.lock:
            worker = self.workers.get(camera_id)
        if worker:
            return worker.get_latest_frame(max_age_sec=max_age_sec)
        return None


stream_manager = StreamManager()
