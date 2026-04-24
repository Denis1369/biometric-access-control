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


settings = Settings()
