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
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_backend_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return BACKEND_ROOT / path


@dataclass(frozen=True)
class Settings:
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
    reid_blur_threshold: float = float(os.getenv("REID_BLUR_THRESHOLD", "30.0"))
    reid_update_alpha: float = float(os.getenv("REID_UPDATE_ALPHA", "0.65"))
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
        return _split_csv(self.cors_allow_origins_raw)

    @property
    def models_path(self) -> Path:
        return _resolve_backend_path(self.models_dir).resolve()

    @property
    def reid_torch_cache_path(self) -> Path:
        if self.reid_torch_cache_dir:
            return _resolve_backend_path(self.reid_torch_cache_dir).resolve()
        return (self.models_path / "torch").resolve()


settings = Settings()
