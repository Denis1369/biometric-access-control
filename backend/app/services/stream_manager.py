import os
import threading
import time
from typing import Optional

import cv2
from sqlmodel import Session, select

from app.core.database import engine
from app.models.cameras import Camera
from app.models.logs import AccessLog
from app.services.recognition_service import find_matching_employee


class CameraStreamWorker:
    def __init__(self, camera_id: int, rtsp_url: str, direction: str):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.direction = direction

        self.is_running = False
        self.thread: Optional[threading.Thread] = None

        self.latest_frame: bytes | None = None
        self.last_frame_at: float = 0.0
        self.last_recognition_at: float = 0.0

        self.frame_lock = threading.Lock()
        self.cap_lock = threading.Lock()
        self.cap: Optional[cv2.VideoCapture] = None

        self.cooldowns: dict[str, float] = {}

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self._set_latest_frame(None)
        self._release_capture()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)

    def _set_latest_frame(self, frame_bytes: bytes | None):
        with self.frame_lock:
            self.latest_frame = frame_bytes
            self.last_frame_at = time.time() if frame_bytes else 0.0

    def get_latest_frame(self, max_age_sec: float = 3.0) -> bytes | None:
        with self.frame_lock:
            if not self.latest_frame:
                return None
            if time.time() - self.last_frame_at > max_age_sec:
                return None
            return self.latest_frame

    def _release_capture(self):
        with self.cap_lock:
            cap = self.cap
            self.cap = None

        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    def _open_capture(self):
        self._release_capture()

        if self.rtsp_url.startswith("rtsp://"):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|stimeout;2000000|rw_timeout;2000000|max_delay;500000"
            )

        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        if not cap or not cap.isOpened():
            try:
                if cap:
                    cap.release()
            except Exception:
                pass
            return None

        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        with self.cap_lock:
            self.cap = cap
        return cap

    def _handle_access(self, image_bytes: bytes):
        with Session(engine) as session:
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

    def _process_loop(self):
        reconnect_delay = 1
        recognition_interval = 0.8

        while self.is_running:
            try:
                with self.cap_lock:
                    cap = self.cap

                if cap is None or not cap.isOpened():
                    cap = self._open_capture()

                    if not self.is_running:
                        break

                    if cap is None or not cap.isOpened():
                        self._set_latest_frame(None)
                        print(f"[Камера {self.camera_id}] Не удалось открыть поток, повтор через {reconnect_delay} сек")
                        time.sleep(reconnect_delay)
                        continue

                    print(f"[Камера {self.camera_id}] Поток подключен")

                ret, frame = cap.read()

                if not self.is_running:
                    break

                if not ret or frame is None:
                    self._set_latest_frame(None)
                    self._release_capture()

                    if self.is_running:
                        print(f"[Камера {self.camera_id}] Поток недоступен, переподключение...")
                        time.sleep(reconnect_delay)
                    continue

                ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok:
                    continue

                image_bytes = buffer.tobytes()
                self._set_latest_frame(image_bytes)

                now = time.time()
                if now - self.last_recognition_at >= recognition_interval:
                    self.last_recognition_at = now
                    try:
                        self._handle_access(image_bytes)
                    except Exception as recog_error:
                        print(f"[Камера {self.camera_id}] Ошибка распознавания: {recog_error}")

            except Exception as e:
                print(f"[Камера {self.camera_id}] Ошибка воркера: {e}")
                self._set_latest_frame(None)
                self._release_capture()

                if self.is_running:
                    time.sleep(reconnect_delay)

        self._set_latest_frame(None)
        self._release_capture()


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

            if worker.thread and worker.thread.is_alive():
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
