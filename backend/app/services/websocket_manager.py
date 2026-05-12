from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


def guest_route_analysis_job_topic(job_id: int) -> str:
    return f"guest_route_analysis_job:{job_id}"


def video_analysis_job_topic(job_id: int) -> str:
    return f"video_analysis_job:{job_id}"


def access_logs_topic() -> str:
    return "access_logs"


class TopicWebSocketManager:
    """Small in-process pub/sub for WebSocket clients.

    Background CV jobs run in worker threads, while WebSocket sends must happen
    on the FastAPI event loop. `publish()` bridges that boundary safely.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        with self._lock:
            self._loop = loop

    def connect(self, topic: str, websocket: WebSocket) -> None:
        with self._lock:
            self._connections[topic].add(websocket)

    def disconnect(self, topic: str, websocket: WebSocket) -> None:
        with self._lock:
            connections = self._connections.get(topic)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(topic, None)

    async def broadcast(self, topic: str, message: Any) -> None:
        with self._lock:
            connections = list(self._connections.get(topic, set()))

        if not connections:
            return

        payload = jsonable_encoder(message)
        stale_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(topic, websocket)

    def publish(self, topic: str, message: Any) -> None:
        with self._lock:
            loop = self._loop

        if loop is None or loop.is_closed():
            logger.debug("WebSocket event loop is not ready; skipped topic=%s", topic)
            return

        future = asyncio.run_coroutine_threadsafe(self.broadcast(topic, message), loop)
        future.add_done_callback(self._log_publish_error)

    @staticmethod
    def _log_publish_error(future) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Не удалось отправить WebSocket-обновление")


topic_ws_manager = TopicWebSocketManager()
