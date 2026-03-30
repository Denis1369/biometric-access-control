import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.stream_manager import stream_manager

router = APIRouter()

@router.websocket("/ws/video/{camera_id}")
async def video_endpoint(websocket: WebSocket, camera_id: int):
    await websocket.accept()
    try:
        while True:
            frame_bytes = stream_manager.get_latest_frame(camera_id)
            
            if frame_bytes:
                await websocket.send_bytes(frame_bytes)
            else:
                await asyncio.sleep(0.5)
                
            await asyncio.sleep(0.02) 
            
    except WebSocketDisconnect:
        pass