import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlmodel import Session

from app.core.database import engine
from app.core.security import ALGORITHM, SECRET_KEY
from app.models.user import User, UserRole
from app.services.stream_manager import stream_manager

router = APIRouter()


ALLOWED_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
}


def _get_user_from_token(token: str | None) -> User | None:
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        user_id = int(sub)
    except (JWTError, ValueError, TypeError):
        return None

    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user or not user.is_active:
            return None
        return user


@router.websocket("/ws/video/{camera_id}")
async def video_endpoint(websocket: WebSocket, camera_id: int):
    token = websocket.query_params.get("token")
    user = _get_user_from_token(token)
    if not user or user.role not in ALLOWED_ROLES:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    try:
        last_frame_version = 0
        while True:
            payload = stream_manager.get_latest_frame_payload(camera_id, max_age_sec=2.0)

            if payload is None:
                await asyncio.sleep(0.03)
                continue

            frame_bytes, frame_version = payload
            if frame_version == last_frame_version:
                await asyncio.sleep(0.01)
                continue

            last_frame_version = frame_version
            await websocket.send_bytes(frame_bytes)
            await asyncio.sleep(0)

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
