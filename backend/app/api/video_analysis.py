"""API для анализа загруженных видеофайлов.

Этот router относится к отдельному демонстрационному сценарию: пользователь
загружает видео, backend создаёт фоновую задачу анализа, сохраняет исходный файл
в storage, постепенно обрабатывает кадры и записывает события распознавания.
Frontend через эти endpoint-ы показывает список задач, прогресс, найденные
события и preview-кадры.

Важно не путать этот модуль с offline-анализом маршрута гостя. Здесь анализ
идёт по загруженному пользователем файлу как самостоятельной задаче. Маршрутный
offline job берёт видео из уже настроенных камер этажа и пишет события гостя в
TrackingLog.
"""

from __future__ import annotations

import logging
import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import get_current_user, require_permissions
from app.core.permissions import VIDEO_ANALYSIS_READ, VIDEO_ANALYSIS_WRITE
from app.models.user import User
from app.models.video_analysis import VideoAnalysisEvent, VideoAnalysisJob
from app.services.video_analysis_service import (
    BASE_STORAGE_DIR,
    build_video_analysis_job_payload,
    reset_video_analysis_job,
    schedule_video_analysis,
)

router = APIRouter(prefix="/api/video-analysis", tags=["Анализ видео"])
logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class VideoAnalysisJobRead(SQLModel):
    """DTO задачи анализа видео для отображения в интерфейсе.

    В объект включены поля, которые нужны не только backend-у, но и пользователю:
    статус обработки, выбранный backend чтения видео, общее и обработанное
    количество кадров, длительность ролика, количество разрешённых и запрещённых
    событий, а также сообщение об ошибке. Такой формат позволяет frontend
    перерисовывать карточку задачи без знания внутренней структуры таблицы.
    """

    id: int
    original_filename: str
    status: str
    reader_backend: str | None = None
    total_frames: int | None = None
    analyzed_frames: int
    duration_sec: float | None = None
    granted_count: int
    denied_count: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class VideoAnalysisEventRead(SQLModel):
    """DTO отдельного события, найденного при анализе видео.

    Событие описывает кадр или момент видео, где система смогла принять решение:
    человек распознан как сотрудник/гость или доступ должен быть запрещён.
    Preview-изображение отдаётся отдельным endpoint-ом, поэтому здесь хранится
    только информация, которую удобно показывать в таблице событий.
    """

    id: int
    job_id: int
    frame_index: int
    timestamp_sec: float
    status: str
    person_type: str | None = None
    person_id: int | None = None
    person_name: str | None = None
    decision: str | None = None
    confidence: float | None = None
    distance: float | None = None
    created_at: datetime


def _job_read(job: VideoAnalysisJob) -> VideoAnalysisJobRead:
    """Преобразовать модель БД задачи в DTO ответа API.

    Сервис анализа видео уже умеет собирать payload для WebSocket-обновлений.
    Чтобы HTTP и WebSocket не расходились по формату, endpoint использует тот же
    helper, а затем оборачивает результат в типизированную схему FastAPI.

    Параметры:
        job: Запись VideoAnalysisJob из базы данных.

    Возвращает:
        DTO, безопасный для отдачи frontend-у.
    """

    return VideoAnalysisJobRead(**build_video_analysis_job_payload(job))


def _event_read(event: VideoAnalysisEvent) -> VideoAnalysisEventRead:
    """Преобразовать событие анализа видео в формат ответа.

    Параметры:
        event: Запись VideoAnalysisEvent. Она уже содержит только метаданные
            события; сам preview-кадр читается отдельно, чтобы не перегружать
            список событий бинарными данными.

    Возвращает:
        DTO события, который используется таблицей результатов анализа.
    """

    return VideoAnalysisEventRead(
        id=event.id,
        job_id=event.job_id,
        frame_index=event.frame_index,
        timestamp_sec=event.timestamp_sec,
        status=event.status,
        person_type=event.person_type,
        person_id=event.person_id,
        person_name=event.person_name,
        decision=event.decision,
        confidence=event.confidence,
        distance=event.distance,
        created_at=event.created_at,
    )


@router.get(
    "/jobs",
    response_model=List[VideoAnalysisJobRead],
    dependencies=[Depends(require_permissions(VIDEO_ANALYSIS_READ))],
)
def get_jobs(session: Session = Depends(get_session)):
    """Вернуть список задач анализа видео.

    Пользователь видит этот список на странице анализа видео. Задачи сортируются
    от новых к старым, чтобы последняя загруженная проверка была первой.

    Параметры:
        session: Сессия БД, через которую читаются записи VideoAnalysisJob.

    Возвращает:
        Список задач в формате, пригодном для карточек frontend-а.
    """

    jobs = session.exec(select(VideoAnalysisJob).order_by(VideoAnalysisJob.created_at.desc())).all()
    return [_job_read(job) for job in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=VideoAnalysisJobRead,
    dependencies=[Depends(require_permissions(VIDEO_ANALYSIS_READ))],
)
def get_job(job_id: int, session: Session = Depends(get_session)):
    """Вернуть одну задачу анализа видео по идентификатору.

    Endpoint используется при открытии деталей задачи и как fallback, если
    WebSocket-обновление было пропущено. Если задача не найдена, frontend
    получает понятную 404-ошибку.

    Параметры:
        job_id: Идентификатор задачи анализа.
        session: Сессия БД.

    Возвращает:
        Текущее состояние задачи.

    Ошибки:
        HTTPException: 404, если задачи с таким идентификатором нет.
    """

    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")
    return _job_read(job)


@router.get(
    "/jobs/{job_id}/events",
    response_model=List[VideoAnalysisEventRead],
    dependencies=[Depends(require_permissions(VIDEO_ANALYSIS_READ))],
)
def get_job_events(job_id: int, session: Session = Depends(get_session)):
    """Вернуть события, найденные в рамках конкретной задачи анализа.

    События сортируются по времени внутри видео, чтобы пользователь видел их в
    том же порядке, в котором они происходили на записи.

    Параметры:
        job_id: Идентификатор задачи, для которой нужны события.
        session: Сессия БД.

    Возвращает:
        Список событий распознавания и решений системы.

    Ошибки:
        HTTPException: 404, если задача не существует.
    """

    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")
    events = session.exec(
        select(VideoAnalysisEvent)
        .where(VideoAnalysisEvent.job_id == job_id)
        .order_by(VideoAnalysisEvent.timestamp_sec.asc())
    ).all()
    return [_event_read(event) for event in events]


@router.get(
    "/jobs/{job_id}/source-video",
    dependencies=[Depends(require_permissions(VIDEO_ANALYSIS_READ))],
)
def get_job_source_video(job_id: int, session: Session = Depends(get_session)):
    """Отдать исходный видеофайл, загруженный для задачи анализа.

    Файл хранится на диске, а не в базе данных, потому что видео может быть
    крупным. Endpoint проверяет, что задача существует и путь действительно
    указывает на файл, после чего отдаёт его через FileResponse.

    Параметры:
        job_id: Идентификатор задачи анализа видео.
        session: Сессия БД.

    Возвращает:
        Поток исходного видеофайла с подходящим media_type.

    Ошибки:
        HTTPException: 404, если задача или файл на диске не найдены.
    """

    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")

    video_path = Path(job.source_path)
    if not job.source_path or not video_path.exists() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="Исходное видео задачи не найдено")

    return FileResponse(
        path=video_path,
        media_type=mimetypes.guess_type(video_path.name)[0] or "application/octet-stream",
        filename=job.original_filename,
    )


@router.post(
    "/jobs/{job_id}/rerun",
    response_model=VideoAnalysisJobRead,
    dependencies=[Depends(require_permissions(VIDEO_ANALYSIS_WRITE))],
)
def rerun_job(job_id: int, session: Session = Depends(get_session)):
    """Повторно запустить ранее завершённую или упавшую задачу анализа.

    Перезапуск нужен, если пользователь поменял настройки распознавания,
    обновил модели или хочет повторить анализ после ошибки. Задачу нельзя
    перезапускать, пока она уже стоит в очереди или обрабатывается, иначе две
    фоновые операции начнут одновременно менять одни и те же поля прогресса.

    Параметры:
        job_id: Идентификатор задачи, которую нужно вернуть в очередь.
        session: Сессия БД.

    Возвращает:
        Обновлённое состояние задачи после постановки в очередь.

    Ошибки:
        HTTPException: 404, если задачи нет; 409, если задача уже обрабатывается
        или сервис не смог безопасно сбросить её состояние.
    """

    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")

    if job.status in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="Задача уже находится в обработке")

    if not reset_video_analysis_job(job_id):
        raise HTTPException(status_code=409, detail="Не удалось перезапустить анализ")

    session.expire_all()
    job = session.get(VideoAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача анализа не найдена")

    schedule_video_analysis(job_id)
    return _job_read(job)


@router.get(
    "/events/{event_id}/preview",
    dependencies=[Depends(require_permissions(VIDEO_ANALYSIS_READ))],
)
def get_event_preview(event_id: int, session: Session = Depends(get_session)):
    """Вернуть preview-кадр для события анализа видео.

    Preview помогает пользователю визуально проверить, почему система приняла
    конкретное решение. В таблице событий хранится только путь к файлу, а
    бинарные данные читаются здесь по запросу, чтобы список событий оставался
    лёгким.

    Параметры:
        event_id: Идентификатор события анализа.
        session: Сессия БД.

    Возвращает:
        JPEG-изображение preview-кадра.

    Ошибки:
        HTTPException: 404, если событие не содержит preview или файл удалён.
    """

    event = session.get(VideoAnalysisEvent, event_id)
    if not event or not event.preview_path:
        raise HTTPException(status_code=404, detail="Превью события не найдено")

    path = Path(event.preview_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл превью не найден")

    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.post(
    "/jobs",
    response_model=VideoAnalysisJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(VIDEO_ANALYSIS_WRITE))],
)
async def create_job(
    video: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Создать задачу анализа для загруженного видеофайла.

    Endpoint принимает multipart-файл от пользователя, проверяет расширение,
    создаёт запись задачи в БД, сохраняет видео в отдельную папку storage и
    запускает фоновую обработку. Запись в БД создаётся до сохранения файла,
    потому что идентификатор задачи используется в имени каталога `job_<id>`.

    Если сохранение файла или постановка в очередь падают, временные файлы и
    запись задачи удаляются, чтобы в интерфейсе не появлялись «битые» задачи.

    Параметры:
        video: Загруженный пользователем видеофайл. Поддерживаются только
            форматы из VIDEO_EXTENSIONS.
        session: Сессия БД, в которой создаётся VideoAnalysisJob.
        current_user: Пользователь, запустивший анализ. Его id сохраняется в
            задаче для аудита и отображения владельца операции.

    Возвращает:
        Созданная задача со статусом queued.

    Ошибки:
        HTTPException: 400 при неподдерживаемом формате или отсутствии имени
        файла; 500, если файл не удалось сохранить или задачу не удалось
        корректно создать.
    """

    if not video.filename:
        raise HTTPException(status_code=400, detail="Не удалось определить имя видеофайла")

    suffix = Path(video.filename or "video").suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Поддерживаются только видеофайлы mp4/avi/mov/mkv/webm")

    temp_job = VideoAnalysisJob(
        original_filename=video.filename or "video",
        source_path="",
        status="queued",
        created_by_user_id=current_user.id,
    )
    session.add(temp_job)
    session.commit()
    session.refresh(temp_job)

    job_dir = BASE_STORAGE_DIR / f"job_{temp_job.id}"
    video_path = job_dir / f"source{suffix}"

    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        with video_path.open("wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

        temp_job.source_path = str(video_path)
        session.add(temp_job)
        session.commit()
        session.refresh(temp_job)

        schedule_video_analysis(temp_job.id)
        return _job_read(temp_job)
    except Exception:
        logger.exception("Не удалось создать задачу анализа видео")

        if video_path.exists():
            video_path.unlink(missing_ok=True)
        if job_dir.exists() and not any(job_dir.iterdir()):
            job_dir.rmdir()

        session.delete(temp_job)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать задачу анализа видео",
        )
