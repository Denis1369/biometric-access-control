import threading
import time
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
        self.thread = None
        self.latest_frame = None
        
        self.cooldowns = {} 

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)

    def _process_loop(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        frame_skip = 5
        frame_count = 0

        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                cap = cv2.VideoCapture(self.rtsp_url) 
                continue
                
            _, buffer = cv2.imencode('.jpg', frame)
            image_bytes = buffer.tobytes()
            
            self.latest_frame = image_bytes

            frame_count += 1
            if frame_count % frame_skip == 0:
                with Session(engine) as session:
                    employee, distance, decision = find_matching_employee(image_bytes, session)
                    
                    current_time = time.time()
                    
                    if employee and decision == "auto_allow":
                        last_seen = self.cooldowns.get(employee.id, 0)
                        if current_time - last_seen > 60: 
                            self.cooldowns[employee.id] = current_time
                            log = AccessLog(
                                employee_id=employee.id, 
                                camera_id=self.camera_id, 
                                status="granted"
                            )
                            session.add(log)
                            session.commit()
                            print(f"[Камера {self.camera_id}] Проход: {employee.last_name} {employee.first_name}")

                    elif employee is None and distance is not None:
                        last_seen = self.cooldowns.get('unknown', 0)
                        if current_time - last_seen > 10:
                            self.cooldowns['unknown'] = current_time
                            log = AccessLog(
                                employee_id=None, 
                                camera_id=self.camera_id, 
                                status="denied"
                            )
                            session.add(log)
                            session.commit()
                            print(f"[Камера {self.camera_id}] Тревога: Неизвестное лицо!")
        cap.release()

class StreamManager:
    def __init__(self):
        self.workers = {} 

    def start_all(self):
        with Session(engine) as session:
            cameras = session.exec(select(Camera).where(Camera.is_active == True)).all()
            for cam in cameras:
                self.add_camera(cam.id, cam.ip_address, cam.direction)

    def add_camera(self, camera_id: int, rtsp_url: str, direction: str):
        if camera_id in self.workers:
            self.remove_camera(camera_id) 
            
        worker = CameraStreamWorker(camera_id, rtsp_url, direction)
        self.workers[camera_id] = worker
        worker.start()
        print(f"[StreamManager] Запущен поток для камеры {camera_id}")

    def remove_camera(self, camera_id: int):
        if camera_id in self.workers:
            self.workers[camera_id].stop()
            del self.workers[camera_id]
            print(f"[StreamManager] Остановлен поток для камеры {camera_id}")
            
    def get_latest_frame(self, camera_id: int):
        worker = self.workers.get(camera_id)
        if worker:
            return worker.latest_frame
        return None

stream_manager = StreamManager()