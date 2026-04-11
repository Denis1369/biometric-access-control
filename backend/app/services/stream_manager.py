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
        
        self.capture_thread = None
        self.recognition_thread = None
        
        self.reader: BaseFrameReader | None = None
        self.reader_lock = threading.Lock()
        
        self.latest_frame = None
        self.latest_frame_for_recognition = None
        self.frame_lock = threading.Lock()
        self.recognition_frame_lock = threading.Lock()
        
        self.last_frame_at = 0.0
        self.cooldowns = {}
        self.recognition_interval = 0.2 # 5 FPS для распознавания

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
            # Твой PyAV ридер! Он сам применит 2-секундный таймаут, если ты добавил options в video_readers.py
            reader = create_frame_reader(self.rtsp_url, is_live=True)
            with self.reader_lock:
                self.reader = reader
            return reader
        except Exception as exc:
            print(f"[Камера {self.camera_id}] Ошибка открытия источника: {exc}")
            return None

    def _set_latest_frame(self, frame_bytes: bytes | None):
        with self.frame_lock:
            self.latest_frame = frame_bytes
            self.last_frame_at = time.time() if frame_bytes else 0.0

    def _set_recognition_frame(self, frame_bytes: bytes | None):
        with self.recognition_frame_lock:
            self.latest_frame_for_recognition = frame_bytes

    def get_latest_frame(self, max_age_sec: float = 3.0) -> bytes | None:
        with self.frame_lock:
            if not self.latest_frame or (time.time() - self.last_frame_at > max_age_sec):
                return None
            return self.latest_frame

    def _capture_loop(self):
        reconnect_delay = 2.0
        target_fps = 15
        frame_interval = 1.0 / target_fps
        last_encode_time = 0
        frame_index = 0

        while self.is_running:
            try:
                with self.reader_lock:
                    reader = self.reader

                if reader is None:
                    reader = self._open_reader()
                    if reader is None:
                        time.sleep(reconnect_delay)
                        continue
                    print(f"[Камера {self.camera_id}] Поток подключен (PyAV)!")

                # Если таймаут сработает, read() вернет None
                result = reader.read()

                if result is None:
                    print(f"[Камера {self.camera_id}] Поток недоступен, переподключение...")
                    self._set_latest_frame(None)
                    self._release_reader()
                    time.sleep(reconnect_delay)
                    continue

                current_time = time.time()
                if current_time - last_encode_time < frame_interval:
                    continue 

                frame, _ = result
                frame_index += 1

                # Конвертируем сырой кадр в JPG для передачи на фронтенд
                ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok:
                    image_bytes = buffer.tobytes()
                    self._set_latest_frame(image_bytes)
                    last_encode_time = current_time

                    # Отдаем каждый 3-й кадр в соседний поток для распознавания лица
                    if frame_index % 3 == 0:
                        self._set_recognition_frame(image_bytes)

            except Exception as e:
                print(f"[Камера {self.camera_id}] Ошибка захвата: {e}")
                self._release_reader()
                time.sleep(reconnect_delay)

    def _recognition_loop(self):
        while self.is_running:
            try:
                frame_bytes = None
                with self.recognition_frame_lock:
                    frame_bytes = self.latest_frame_for_recognition
                    self.latest_frame_for_recognition = None # Забрали кадр

                if frame_bytes:
                    self._handle_access(frame_bytes)
                
                time.sleep(self.recognition_interval)
            except Exception as e:
                print(f"[Камера {self.camera_id}] Ошибка распознавания: {e}")
                time.sleep(0.5)

    def _handle_access(self, image_bytes: bytes):
        with Session(engine) as session:
            with ml_lock:
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
                    log = AccessLog(employee_id=None, camera_id=self.camera_id, status="denied")
                    session.add(log)
                    session.commit()
                    print(f"[Камера {self.camera_id}] Тревога: Неизвестное лицо!")

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
            print(f"[StreamManager] Остановлен поток для камеры {camera_id}")

    def get_latest_frame(self, camera_id: int, max_age_sec: float = 3.0):
        with self.lock:
            worker = self.workers.get(camera_id)
        if worker:
            return worker.get_latest_frame(max_age_sec=max_age_sec)
        return None

stream_manager = StreamManager()