import asyncio
import time
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
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    finally:
        event_manager.disconnect(websocket)


def run_recognition_sync(images_bytes_list: list[bytes], camera_id: int):
    with Session(engine) as session:
        return process_access_request_multi_frame(
            images_bytes_list=images_bytes_list,
            camera_id=camera_id,
            session=session,
            review_hits_required=2,
        )


@router.websocket("/video/{camera_id}")
async def websocket_video(websocket: WebSocket, camera_id: int):
    await websocket.accept()

    cap = None
    last_decision_time = 0.0
    last_sample_time = 0.0
    cooldown_seconds = 3.0
    sample_interval_seconds = 0.40
    frame_buffer = deque(maxlen=3)
    recognition_in_progress = False

    try:
        with Session(engine) as session:
            camera = session.get(Camera, camera_id)

        if not camera:
            await websocket.close(code=4404, reason="Camera not found")
            return

        video_source = camera.ip_address

        if isinstance(video_source, str) and video_source.isdigit():
            video_source = int(video_source)

        cap = cv2.VideoCapture(video_source)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            await websocket.close(code=1011, reason=f"Cannot open video source: {camera.ip_address}")
            return

        while True:
            success, frame = cap.read()
            if not success:
                await asyncio.sleep(0.03)
                continue

            frame = cv2.resize(frame, (1280, 640))

            ok, buffer = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 55]
            )
            if not ok:
                await asyncio.sleep(0.02)
                continue

            frame_bytes = buffer.tobytes()
            await websocket.send_bytes(frame_bytes)

            current_time = time.time()

            if current_time - last_sample_time >= sample_interval_seconds:
                frame_buffer.append(frame_bytes)
                last_sample_time = current_time

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
                    except Exception as e:
                        print(f"[recognition] error: {e}")
                    finally:
                        recognition_in_progress = False

                asyncio.create_task(run_recognition_task(frames_for_check))

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