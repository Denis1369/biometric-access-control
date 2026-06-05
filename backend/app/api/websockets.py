"""WebSocket endpoint-ы для live-обновлений интерфейса.

В проекте есть операции, которые не удобно обновлять обычным polling-ом:
живой кадр камеры, прогресс анализа видео, прогресс построения маршрута гостя
и свежие события журнала проходов. Этот модуль даёт frontend-у постоянные
подписки, через которые backend отправляет данные сразу после изменения.

Так как стандартный OAuth2 Bearer-заголовок не всегда удобно передавать при
создании WebSocket из браузера, token передаётся в query-параметре. Перед
подключением каждый endpoint вручную проверяет пользователя и его permissions.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from app.core.database import engine
from app.core.permissions import (
    ACCESS_LOGS_READ,
    ACCESS_LOGS_READ_RECENT,
    CAMERA_SNAPSHOT_READ,
    GUEST_ROUTES_ANALYZE_VIDEO,
    VIDEO_ANALYSIS_READ,
    get_permissions_for_role,
)
from app.core.security import decode_access_token_subject
from app.models.guest_route_analysis_jobs import GuestRouteAnalysisJob
from app.models.user import User
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


def _get_user_from_token(token: str | None) -> User | None:
    """Получить активного пользователя из JWT-токена WebSocket-подключения.

    WebSocket endpoint-ы не используют обычную FastAPI dependency `get_current_user`,
    потому что WebSocket-запрос живёт иначе, чем HTTP-запрос. Поэтому здесь
    вручную декодируется subject токена, открывается короткая сессия БД и
    проверяется, что пользователь существует и не деактивирован.

    Параметры:
        token: JWT access token из query-параметра `token`.

    Возвращает:
        Модель активного пользователя или None, если токен отсутствует,
        недействителен, пользователь не найден или отключён.
    """

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


async def _reject_unauthorized(websocket: WebSocket, *allowed_permissions: str) -> bool:
    """Проверить доступ к WebSocket и закрыть соединение при отказе.

    Функция используется в начале каждого WebSocket endpoint-а. Она достаёт
    token из query-параметров, определяет роль пользователя, получает набор
    разрешений и проверяет, есть ли хотя бы одно из разрешений, подходящих для
    подписки. При отказе соединение закрывается кодом 1008, который означает
    нарушение политики доступа.

    Параметры:
        websocket: Подключение, которое пытается открыть frontend.
        allowed_permissions: Разрешения, любое из которых даёт право на
            подписку. Например, журнал проходов могут видеть разные роли с
            разным уровнем доступа.

    Возвращает:
        True, если соединение уже отклонено и endpoint должен завершиться;
        False, если пользователь допущен.
    """

    token = websocket.query_params.get("token")
    user = _get_user_from_token(token)
    permissions = get_permissions_for_role(user.role) if user else frozenset()
    if not user or not any(permission in permissions for permission in allowed_permissions):
        await websocket.close(code=1008)
        return True
    return False


async def _keep_subscription_alive(websocket: WebSocket, topic: str, initial_payload: dict) -> None:
    """Открыть topic-подписку и держать WebSocket активным.

    Большинство подписок устроены одинаково: принять соединение, привязать его
    к topic в topic_ws_manager, отправить начальный снимок состояния и дальше
    ждать любые входящие сообщения от клиента. Смысл входящих сообщений здесь
    не важен: они нужны, чтобы соединение не завершалось и чтобы мы могли
    корректно поймать отключение вкладки.

    Параметры:
        websocket: WebSocket-соединение пользователя.
        topic: Логический канал рассылки, например конкретная задача анализа
            видео или общий журнал проходов.
        initial_payload: Начальное состояние, которое клиент получает сразу
            после подключения, ещё до следующих изменений.
    """

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
    """Передавать live-кадры выбранной камеры в браузер.

    Endpoint используется компонентом просмотра камеры. Он не отправляет JSON:
    здесь по WebSocket идут JPEG-байты последнего кадра, чтобы canvas/video-view
    на frontend мог быстро перерисовываться. При подключении включается
    demo-recognition для камеры, а при отключении обязательно выключается, чтобы
    лишняя обработка не продолжалась после закрытия вкладки.

    Параметры:
        websocket: Подключение браузера.
        camera_id: Идентификатор камеры, кадры которой нужно отправлять.
    """

    if await _reject_unauthorized(websocket, CAMERA_SNAPSHOT_READ):
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
    """Подписать frontend на статус offline job маршрута гостя.

    После запуска анализа видео по камерам этажа модальное окно гостя открывает
    эту подписку. Backend отправляет начальный снимок задания, а сервис анализа
    позже публикует новые payload-ы через topic_ws_manager. Так оператор видит
    прогресс без ручного обновления страницы.

    Параметры:
        websocket: Подключение браузера.
        job_id: Идентификатор GuestRouteAnalysisJob.
    """

    if await _reject_unauthorized(websocket, GUEST_ROUTES_ANALYZE_VIDEO):
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
    """Подписать frontend на прогресс обычной задачи анализа видео.

    Endpoint похож на guest_route_analysis_job_endpoint, но работает с
    VideoAnalysisJob. Он нужен странице «Анализ видео», где пользователь
    загружает ролик и наблюдает, как меняются analyzed_frames, статус и
    количество найденных событий.

    Параметры:
        websocket: Подключение браузера.
        job_id: Идентификатор VideoAnalysisJob.
    """

    if await _reject_unauthorized(websocket, VIDEO_ANALYSIS_READ):
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
    """Отправлять новые события журнала проходов в реальном времени.

    При открытии подписки клиент сначала получает snapshot последних событий,
    чтобы интерфейс был заполнен сразу. После этого access_log_service публикует
    новые записи в общий topic, и список на проходной обновляется без polling-а.

    Параметры:
        websocket: Подключение браузера к журналу проходов.
    """

    if await _reject_unauthorized(websocket, ACCESS_LOGS_READ, ACCESS_LOGS_READ_RECENT):
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
