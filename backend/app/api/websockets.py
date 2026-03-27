import asyncio
import base64
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sqlmodel import Session
from app.core.database import engine
from app.models.cameras import Camera

router = APIRouter(prefix="/ws", tags=["Реальное время"])

class ConnectionManager:
    """
    Класс для управления активными WebSocket-соединениями.
    Позволяет подключать клиентов, отключать их и массово рассылать JSON-события.
    """
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_event(self, event_data: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(event_data)
            except Exception:
                pass

event_manager = ConnectionManager()

@router.websocket("/events")
async def websocket_events(websocket: WebSocket):
    """
    Эндпоинт для подключения фронтенда к шине событий.
    Через этот канал интерфейс будет получать уведомления о распознанных лицах.
    """
    await event_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_manager.disconnect(websocket)

@router.websocket("/video/{camera_id}")
async def websocket_video(websocket: WebSocket, camera_id: int):
    await websocket.accept()

    cap = None
    try:
        with Session(engine) as session:
            camera = session.get(Camera, camera_id)

        if not camera:
            await websocket.close(code=4404, reason="Camera not found")
            return

        video_source = camera.ip_address
        cap = cv2.VideoCapture(video_source)

        if not cap.isOpened():
            await websocket.close(code=1011, reason=f"Cannot open video source: {video_source}")
            return

        while True:
            success, frame = cap.read()
            if not success:
                await asyncio.sleep(0.1)
                continue

            frame = cv2.resize(frame, (640, 480))
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                await asyncio.sleep(0.03)
                continue

            # frame_base64 = base64.b64encode(buffer).decode("utf-8")
            # await websocket.send_text(frame_base64)
            
            await websocket.send_bytes(buffer.tobytes())

            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[ws/video/{camera_id}] error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal video stream error")
        except Exception:
            pass
    finally:
        if cap is not None:
            cap.release()