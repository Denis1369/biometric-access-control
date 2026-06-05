"""Настройки backend-приложения.

В этом файле собраны параметры, которые нельзя жёстко зашивать в бизнес-логику:
подключение к MySQL, CORS-адреса frontend-а, JWT-секрет, пути к ML-моделям,
пороги распознавания и ограничения анализа маршрутов. Все значения читаются из
переменных окружения или backend/.env, поэтому один и тот же код можно запускать
локально, на защите диплома и на сервере с разными настройками.

Если в системе странно работает распознавание или маршрут гостя, этот файл
часто является первой точкой проверки: здесь задаются пороги Re-ID, интервал
сэмплирования видео и фильтры правдоподобности маршрута.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"

load_dotenv(BACKEND_ROOT / ".env")
load_dotenv()


def _split_csv(value: str) -> list[str]:
    """Разобрать строку вида `a,b,c` в список непустых значений.

    Используется для CORS-адресов. Значения очищаются от пробелов, чтобы в .env
    можно было писать список удобно и без риска получить origin с лишним
    пробелом.
    """

    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_backend_path(value: str) -> Path:
    """Преобразовать путь из настроек в абсолютный путь backend-а.

    Некоторые пути, например MODELS_DIR или REID_TORCH_CACHE_DIR, удобно хранить
    относительными. Эта функция делает их абсолютными относительно папки
    backend, а уже абсолютные пути оставляет как есть. Так запуск из разных
    рабочих директорий не ломает поиск моделей.
    """

    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return BACKEND_ROOT / path


@dataclass(frozen=True)
class Settings:
    """Единый объект настроек приложения.

    Класс намеренно заморожен: после запуска приложения настройки не должны
    незаметно меняться в рантайме. Поля сгруппированы по смыслу:
    подключение к базе данных, JWT и CORS, параметры ML-пайплайна Re-ID,
    настройки offline-анализа маршрута гостя и фильтры вероятного маршрута.

    Большинство числовых параметров являются компромиссом между качеством
    распознавания и скоростью демо. Например, route_analysis_sample_interval_sec
    определяет, как часто брать кадры из видео, а reid_match_distance влияет на
    строгость сопоставления силуэта человека с body_embedding гостя.
    """

    database_url_override: str = os.getenv("DATABASE_URL", "").strip()
    db_user: str = os.getenv("DB_USER", "").strip()
    db_password: str = os.getenv("DB_PASSWORD", "").strip()
    db_host: str = os.getenv("DB_HOST", "").strip()
    db_port: str = os.getenv("DB_PORT", "").strip()
    db_name: str = os.getenv("DB_NAME", "").strip()

    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_ENV").strip()
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    cors_allow_origins_raw: str = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).strip()
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    ml_thread_count: int = int(os.getenv("ML_THREAD_COUNT", "4"))
    models_dir: str = os.getenv("MODELS_DIR", "models").strip()
    reid_enabled: bool = os.getenv("REID_ENABLED", "true").strip().lower() == "true"
    reid_detector_weights: str = os.getenv(
        "REID_DETECTOR_WEIGHTS",
        "yolo26n-pose.pt",
    ).strip()
    reid_detector_url: str = os.getenv(
        "REID_DETECTOR_URL",
        "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-pose.pt",
    ).strip()
    reid_model_name: str = os.getenv("REID_MODEL_NAME", "osnet_x1_0").strip()
    reid_model_path: str = os.getenv("REID_MODEL_PATH", "").strip()
    reid_model_url: str = os.getenv("REID_MODEL_URL", "").strip()
    reid_torch_cache_dir: str = os.getenv("REID_TORCH_CACHE_DIR", "").strip()
    reid_device: str = os.getenv("REID_DEVICE", "auto").strip().lower()
    reid_person_confidence: float = float(os.getenv("REID_PERSON_CONFIDENCE", "0.35"))
    reid_match_distance: float = float(os.getenv("REID_MATCH_DISTANCE", "0.42"))
    reid_min_crop_width: int = int(os.getenv("REID_MIN_CROP_WIDTH", "48"))
    reid_min_crop_height: int = int(os.getenv("REID_MIN_CROP_HEIGHT", "96"))
    reid_min_area_ratio: float = float(os.getenv("REID_MIN_AREA_RATIO", "0.015"))
    reid_min_body_aspect_ratio: float = float(
        os.getenv("REID_MIN_BODY_ASPECT_RATIO", "1.55")
    )
    reid_blur_threshold: float = float(os.getenv("REID_BLUR_THRESHOLD", "30.0"))
    reid_update_alpha: float = float(os.getenv("REID_UPDATE_ALPHA", "0.65"))
    route_analysis_sample_interval_sec: float = float(
        os.getenv("ROUTE_ANALYSIS_SAMPLE_INTERVAL_SEC", "2.0")
    )
    route_analysis_body_match_distance: float = float(
        os.getenv("ROUTE_ANALYSIS_BODY_MATCH_DISTANCE", "0.56")
    )
    route_analysis_event_min_similarity: float = float(
        os.getenv("ROUTE_ANALYSIS_EVENT_MIN_SIMILARITY", "0.68")
    )
    route_analysis_camera_time_offsets_raw: str = os.getenv(
        "ROUTE_ANALYSIS_CAMERA_TIME_OFFSETS",
        "UKSIVT Camera02=-25",
    ).strip()
    route_analysis_job_timeout_sec: float = float(
        os.getenv("ROUTE_ANALYSIS_JOB_TIMEOUT_SEC", "1800")
    )
    guest_route_max_pixels_per_second: float = float(
        os.getenv("GUEST_ROUTE_MAX_PIXELS_PER_SECOND", "120.0")
    )
    guest_route_max_event_gap_sec: float = float(
        os.getenv("GUEST_ROUTE_MAX_EVENT_GAP_SEC", "120.0")
    )
    guest_route_min_event_confidence: float = float(
        os.getenv("GUEST_ROUTE_MIN_EVENT_CONFIDENCE", "0.60")
    )
    guest_route_keep_latest_event_per_camera: bool = (
        os.getenv("GUEST_ROUTE_KEEP_LATEST_EVENT_PER_CAMERA", "true").strip().lower()
        == "true"
    )
    analysis_trigger_enabled: bool = (
        os.getenv("ANALYSIS_TRIGGER_ENABLED", "true").strip().lower() == "true"
    )
    analysis_trigger_person_confidence: float = float(
        os.getenv("ANALYSIS_TRIGGER_PERSON_CONFIDENCE", "0.28")
    )
    analysis_trigger_empty_log_interval_sec: float = float(
        os.getenv("ANALYSIS_TRIGGER_EMPTY_LOG_INTERVAL_SEC", "30.0")
    )

    @property
    def database_url(self) -> str:
        """Собрать строку подключения к MySQL.

        Если задан DATABASE_URL, он используется напрямую. Иначе строка
        собирается из DB_USER, DB_PASSWORD, DB_HOST, DB_PORT и DB_NAME. Явная
        проверка отсутствующих переменных нужна, чтобы приложение падало с
        понятной ошибкой при неправильной настройке, а не с длинным traceback
        SQLAlchemy.
        """

        if self.database_url_override:
            return self.database_url_override

        missing = [
            name
            for name, value in (
                ("DB_USER", self.db_user),
                ("DB_PASSWORD", self.db_password),
                ("DB_HOST", self.db_host),
                ("DB_PORT", self.db_port),
                ("DB_NAME", self.db_name),
            )
            if not value
        ]
        if missing:
            missing_list = ", ".join(missing)
            raise RuntimeError(
                f"Не заданы переменные окружения для БД: {missing_list}. "
                "Заполните backend/.env или передайте DATABASE_URL."
            )

        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_allow_origins(self) -> list[str]:
        """Вернуть список frontend-origin, которым разрешён доступ к API."""

        return _split_csv(self.cors_allow_origins_raw)

    @property
    def models_path(self) -> Path:
        """Абсолютный путь к каталогу локальных ML-моделей."""

        return _resolve_backend_path(self.models_dir).resolve()

    @property
    def reid_torch_cache_path(self) -> Path:
        """Путь к cache-директории TorchReID/torch.

        Если отдельная переменная не задана, cache кладётся внутрь каталога
        моделей проекта, чтобы веса и служебные файлы не расползались по системе
        и были проще переносимы на другой компьютер.
        """

        if self.reid_torch_cache_dir:
            return _resolve_backend_path(self.reid_torch_cache_dir).resolve()
        return (self.models_path / "torch").resolve()


settings = Settings()
