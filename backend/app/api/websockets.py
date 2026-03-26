import asyncio
import base64
import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
    """
    Эндпоинт для потоковой передачи видео.
    Захватывает кадры через OpenCV, сжимает их в JPEG и отправляет в формате Base64.
    """
    await websocket.accept()
    
    video_source = 0
    cap = cv2.VideoCapture(video_source)

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                await asyncio.sleep(0.1)
                continue

            frame = cv2.resize(frame, (640, 480))
            
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')

            await websocket.send_text(frame_base64)
            
            await asyncio.sleep(0.03)
            
    except WebSocketDisconnect:
        pass
    finally:
        cap.release()