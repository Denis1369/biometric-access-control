import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.stream_manager import stream_manager

router = APIRouter()


@router.websocket("/ws/video/{camera_id}")
async def video_endpoint(websocket: WebSocket, camera_id: int):
    await websocket.accept()
    try:
        while True:
            frame_bytes = stream_manager.get_latest_frame(camera_id, max_age_sec=3.0)

            if frame_bytes is None:
                await asyncio.sleep(0.1)
                continue

            await websocket.send_bytes(frame_bytes)

            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass