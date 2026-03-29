import asyncio
import base64
import time
import os
from collections import deque

import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from app.core.database import engine
from app.models.cameras import Camera
from app.services.recognition_service import process_access_request_multi_frame

router = APIRouter(prefix="/ws", tags=["Реальное время"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_event(self, event_data: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(event_data)
            except Exception:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(connection)

event_manager = ConnectionManager()

@router.websocket("/events")
async def websocket_events(websocket: WebSocket):
    await event_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_manager.disconnect(websocket)

def run_recognition_sync(frames_batch: list[bytes], camera_id: int):
    with Session(engine) as session:
        return process_access_request_multi_frame(frames_batch, camera_id, session)

def open_camera(ip_address: str):
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|timeout;3000|stimeout;3000000"
    return cv2.VideoCapture(ip_address)

def release_camera(cap):
    if cap is not None:
        cap.release()

@router.websocket("/video/{camera_id}")
async def websocket_video(websocket: WebSocket, camera_id: int):
    await websocket.accept()

    with Session(engine) as session:
        camera = session.get(Camera, camera_id)
        if not camera or not camera.is_active:
            await websocket.close(code=1008, reason="Camera not found or inactive")
            return
        ip_address = camera.ip_address

    cap = await asyncio.to_thread(open_camera, ip_address)

    last_decision_time = 0.0
    cooldown_seconds = 2.0
    frame_buffer = deque(maxlen=5)
    recognition_in_progress = False

    disconnect_task = asyncio.create_task(websocket.receive())

    try:
        is_opened = await asyncio.to_thread(cap.isOpened)
        
        while is_opened:
            if disconnect_task.done():
                break

            success, frame = await asyncio.to_thread(cap.read)

            if not success:
                await asyncio.sleep(0.05)
                is_opened = await asyncio.to_thread(cap.isOpened)
                continue

            frame = cv2.resize(frame, (640, 480))
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_bytes = buffer.tobytes()
            frame_base64 = base64.b64encode(frame_bytes).decode('utf-8')

            try:
                await websocket.send_text(frame_base64)
            except Exception:
                break

            frame_buffer.append(frame_bytes)

            current_time = time.time()
            if (
                len(frame_buffer) == frame_buffer.maxlen
                and not recognition_in_progress
                and current_time - last_decision_time >= cooldown_seconds
            ):
                recognition_in_progress = True
                frames_for_check = list(frame_buffer)
                frame_buffer.clear()

                async def run_recognition_task(frames_batch: list[bytes]):
                    nonlocal recognition_in_progress, last_decision_time
                    try:
                        result = await asyncio.to_thread(
                            run_recognition_sync,
                            frames_batch,
                            camera_id
                        )
                        last_decision_time = time.time()
                        if result:
                            await event_manager.broadcast_event(result)
                    except Exception:
                        pass
                    finally:
                        recognition_in_progress = False

                asyncio.create_task(run_recognition_task(frames_for_check))

            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        disconnect_task.cancel()
        await asyncio.to_thread(release_camera, cap)