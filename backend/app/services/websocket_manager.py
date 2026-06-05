"""Внутрипроцессный менеджер WebSocket-подписок по topic-ам.

Фоновые задачи компьютерного зрения часто выполняются не в основном event loop,
а в worker-потоках. При этом отправлять сообщения WebSocket можно только через
asyncio loop FastAPI. Этот сервис является мостом: код из любого потока вызывает
`publish(topic, message)`, а менеджер безопасно планирует async broadcast в
основном loop.
"""

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
    """Вернуть имя topic-а для конкретного задания маршрута гостя."""

    return f"guest_route_analysis_job:{job_id}"


def video_analysis_job_topic(job_id: int) -> str:
    """Вернуть имя topic-а для конкретной задачи анализа загруженного видео."""

    return f"video_analysis_job:{job_id}"


def access_logs_topic() -> str:
    """Вернуть общий topic новых событий журнала проходов."""

    return "access_logs"


class TopicWebSocketManager:
    """Небольшой in-process pub/sub для WebSocket-клиентов.

    Менеджер хранит набор подключений по строковому topic-у. Один topic может
    представлять конкретную задачу анализа или общий журнал проходов. Когда
    сервис публикует сообщение, оно отправляется всем клиентам, подписанным на
    этот topic. Если отправка в какое-то соединение падает, соединение считается
    устаревшим и удаляется из списка.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        """Запомнить event loop FastAPI для публикаций из фоновых потоков."""

        with self._lock:
            self._loop = loop

    def connect(self, topic: str, websocket: WebSocket) -> None:
        """Добавить WebSocket-клиента в список подписчиков topic-а."""

        with self._lock:
            self._connections[topic].add(websocket)

    def disconnect(self, topic: str, websocket: WebSocket) -> None:
        """Удалить WebSocket-клиента из topic-а после закрытия соединения."""

        with self._lock:
            connections = self._connections.get(topic)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(topic, None)

    async def broadcast(self, topic: str, message: Any) -> None:
        """Асинхронно отправить сообщение всем подписчикам topic-а.

        Сообщение проходит через jsonable_encoder, потому что payload может
        содержать datetime, SQLModel-совместимые структуры или другие объекты,
        которые обычный JSON не сериализует напрямую.
        """

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
        """Опубликовать сообщение из любого потока приложения.

        Если event loop ещё не зарегистрирован или уже закрыт, публикация
        пропускается. Это важно при старте и остановке приложения: фоновые
        сервисы не должны падать только потому, что WebSocket-инфраструктура
        временно недоступна.
        """

        with self._lock:
            loop = self._loop

        if loop is None or loop.is_closed():
            logger.debug("WebSocket event loop is not ready; skipped topic=%s", topic)
            return

        future = asyncio.run_coroutine_threadsafe(self.broadcast(topic, message), loop)
        future.add_done_callback(self._log_publish_error)

    @staticmethod
    def _log_publish_error(future) -> None:
        """Записать ошибку, если coroutine broadcast завершилась исключением."""

        try:
            future.result()
        except Exception:
            logger.exception("Не удалось отправить WebSocket-обновление")


topic_ws_manager = TopicWebSocketManager()
