"""API для офлайн-построения маршрута гостя по видео камер этажа.

Этот router обслуживает сценарий из карточки гостя: оператор выбирает этаж и
нажимает действие «Проанализировать видео и построить маршрут». Backend не
строит маршрут сразу в HTTP-запросе, потому что анализ нескольких видеофайлов
через Re-ID может занимать заметное время. Вместо этого создаётся запись
фонового задания, оно запускается отдельно, а frontend получает состояние
задания через этот API и WebSocket.

Важная идея модуля: сами найденные появления гостя не хранятся в отдельной
таблице задания. Они записываются в общий TrackingLog, потому что дальше
вероятный маршрут строится тем же механизмом, что и маршрут по уже имеющемуся
журналу событий.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel, Session

from app.core.database import get_session
from app.core.deps import require_permissions
from app.core.permissions import GUEST_ROUTES_ANALYZE_VIDEO
from app.models.floors import Floor
from app.models.guest_route_analysis_jobs import GuestRouteAnalysisJob
from app.services.guest_route_analysis_service import (
    build_job_payload,
    create_guest_route_analysis_job,
    schedule_guest_route_analysis,
)

router = APIRouter(prefix="/api", tags=["Офлайн-маршруты гостей"])

class GuestRouteAnalysisJobRead(SQLModel):
    """DTO статуса фонового анализа маршрута гостя.

    Объект возвращается сразу после создания задания и при последующих запросах
    статуса. Он содержит не только технический статус queued/processing/completed,
    но и человекочитаемые предупреждения, количество обработанных камер,
    количество записанных событий TrackingLog и готовый probable_route после
    завершения анализа. Благодаря этому frontend может показывать оператору
    прогресс и итог без дополнительных запросов в несколько разных endpoint-ов.
    """

    id: int
    guest_id: int
    floor_id: int
    status: str
    processed_cameras: int
    total_cameras: int
    events_written: int
    warnings: list[str]
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    probable_route: dict[str, Any] | None = None


@router.post(
    "/floors/{floor_id}/guests/{guest_id}/route-analysis-jobs",
    response_model=GuestRouteAnalysisJobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить офлайн-анализ маршрута гостя по video-file камерам этажа",
    dependencies=[Depends(require_permissions(GUEST_ROUTES_ANALYZE_VIDEO))],
)
def create_route_analysis_job(
    floor_id: int,
    guest_id: int,
    session: Session = Depends(get_session),
):
    """Создать и запустить фоновое задание анализа маршрута гостя.

    Endpoint вызывается из модального окна маршрута гостя, когда оператор хочет
    не просто построить маршрут по уже записанному журналу, а сначала прогнать
    file-видео камер выбранного этажа. Перед созданием задания проверяется, что
    этаж существует. Остальные предметные проверки выполняет сервис: гость
    должен существовать, быть активным и иметь body_embedding, а на этаже должны
    быть активные камеры с источником file:// или локальным путём к видео.

    Параметры:
        floor_id: Идентификатор этажа, камеры которого нужно проанализировать.
            Он приходит из выбранного этажа в интерфейсе.
        guest_id: Идентификатор гостя, для которого ищутся появления на видео.
            Система сравнивает найденных людей только с body_embedding этого
            гостя, а не со всей базой.
        session: Сессия БД FastAPI dependency. Через неё создаётся запись
            GuestRouteAnalysisJob и выполняются проверки.

    Возвращает:
        DTO созданной задачи с начальным статусом и прогрессом. После этого
        frontend обычно открывает WebSocket-подписку на эту задачу.

    Ошибки:
        HTTPException: Возвращает 404, если этаж не найден, и 400, если сервис
        не смог создать задание из-за предметных ограничений: нет гостя, нет
        Re-ID признаков или нет подходящих камер.
    """

    floor = session.get(Floor, floor_id)
    if not floor:
        raise HTTPException(status_code=404, detail="Этаж не найден")

    try:
        job = create_guest_route_analysis_job(session, guest_id=guest_id, floor_id=floor_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    schedule_guest_route_analysis(job.id)
    return build_job_payload(session, job)


@router.get(
    "/guest-route-analysis-jobs/{job_id}",
    response_model=GuestRouteAnalysisJobRead,
    summary="Получить статус офлайн-анализа маршрута гостя",
    dependencies=[Depends(require_permissions(GUEST_ROUTES_ANALYZE_VIDEO))],
)
def get_route_analysis_job(
    job_id: int,
    session: Session = Depends(get_session),
):
    """Вернуть актуальное состояние фонового задания маршрута гостя.

    Endpoint нужен как безопасный fallback к WebSocket и для первичной загрузки
    состояния, если пользователь открыл страницу позже. Он собирает payload
    через сервис, чтобы формат ответа был одинаковым и для HTTP, и для
    WebSocket-рассылки.

    Параметры:
        job_id: Идентификатор задания, созданного endpoint-ом запуска анализа.
        session: Сессия БД, из которой читается запись задания и связанные
            данные вероятного маршрута.

    Возвращает:
        Полное состояние задания: статус, прогресс, предупреждения, количество
        найденных событий и вероятный маршрут после завершения.

    Ошибки:
        HTTPException: Возвращает 404, если запись задания уже удалена или
        идентификатор передан неверно.
    """

    job = session.get(GuestRouteAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа маршрута не найдена")

    return build_job_payload(session, job)
