import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from app.core.database import engine
from app.core.security import decode_access_token_subject
from app.models.guest_route_analysis_jobs import GuestRouteAnalysisJob
from app.models.user import User, UserRole
from app.models.video_analysis import VideoAnalysisJob
from app.services.access_log_service import get_recent_access_logs
from app.services.guest_route_analysis_service import build_job_payload
from app.services.stream_manager import stream_manager
from app.services.video_analysis_service import build_video_analysis_job_payload
from app.services.websocket_manager import (
    access_logs_topic,
    guest_route_analysis_job_topic,
    topic_ws_manager,
    video_analysis_job_topic,
)

router = APIRouter()
logger = logging.getLogger(__name__)


ALLOWED_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
}


def _get_user_from_token(token: str | None) -> User | None:
    if not token:
        return None

    user_id = decode_access_token_subject(token)
    if user_id is None:
        return None

    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user or not user.is_active:
            return None
        return user


async def _reject_unauthorized(websocket: WebSocket) -> bool:
    token = websocket.query_params.get("token")
    user = _get_user_from_token(token)
    if not user or user.role not in ALLOWED_ROLES:
        await websocket.close(code=1008)
        return True
    return False


async def _keep_subscription_alive(websocket: WebSocket, topic: str, initial_payload: dict) -> None:
    await websocket.accept()
    topic_ws_manager.connect(topic, websocket)
    try:
        await websocket.send_json(jsonable_encoder(initial_payload))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket подписка %s завершилась с ошибкой", topic)
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        topic_ws_manager.disconnect(topic, websocket)


@router.websocket("/ws/video/{camera_id}")
async def video_endpoint(websocket: WebSocket, camera_id: int):
    if await _reject_unauthorized(websocket):
        return

    await websocket.accept()
    stream_manager.set_demo_recognition_enabled(camera_id, True)
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
        logger.exception("WebSocket видеопотока камеры %s завершился с ошибкой", camera_id)
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        stream_manager.set_demo_recognition_enabled(camera_id, False)


@router.websocket("/ws/guest-route-analysis-jobs/{job_id}")
async def guest_route_analysis_job_endpoint(websocket: WebSocket, job_id: int):
    if await _reject_unauthorized(websocket):
        return

    with Session(engine) as session:
        job = session.get(GuestRouteAnalysisJob, job_id)
        if not job:
            await websocket.close(code=1008)
            return
        initial_payload = build_job_payload(session, job)

    await _keep_subscription_alive(
        websocket,
        guest_route_analysis_job_topic(job_id),
        initial_payload,
    )


@router.websocket("/ws/video-analysis/jobs/{job_id}")
async def video_analysis_job_endpoint(websocket: WebSocket, job_id: int):
    if await _reject_unauthorized(websocket):
        return

    with Session(engine) as session:
        job = session.get(VideoAnalysisJob, job_id)
        if not job:
            await websocket.close(code=1008)
            return
        initial_payload = build_video_analysis_job_payload(job)

    await _keep_subscription_alive(
        websocket,
        video_analysis_job_topic(job_id),
        initial_payload,
    )


@router.websocket("/ws/access-logs")
async def access_logs_endpoint(websocket: WebSocket):
    if await _reject_unauthorized(websocket):
        return

    with Session(engine) as session:
        initial_payload = {
            "type": "snapshot",
            "logs": get_recent_access_logs(session, limit=50),
        }

    await _keep_subscription_alive(
        websocket,
        access_logs_topic(),
        initial_payload,
    )
