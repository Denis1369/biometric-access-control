import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from sqlmodel import Session, SQLModel

import app.models  # noqa: F401
from app.api import (
    analytics,
    auth,
    buildings,
    cameras,
    departments,
    employees,
    floors,
    guests,
    job_positions,
    route_graph,
    users,
    video_analysis,
    websockets,
)
from app.core.config import settings
from app.core.database import engine
from app.core.seed import ensure_demo_data
from app.services.stream_manager import stream_manager

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def ensure_runtime_schema_updates():
    inspector = inspect(engine)
    guest_columns = {column["name"] for column in inspector.get_columns("guests")}

    statements: list[str] = []
    if "body_embedding" not in guest_columns:
        statements.append("ALTER TABLE guests ADD COLUMN body_embedding JSON NULL")
    if "body_embedding_updated_at" not in guest_columns:
        statements.append(
            "ALTER TABLE guests ADD COLUMN body_embedding_updated_at DATETIME NULL"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)

    logger.info("Применены runtime-обновления схемы для Re-ID.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    ensure_runtime_schema_updates()

    with Session(engine) as session:
        seeded = ensure_demo_data(session)
        if seeded:
            logger.info("Пустая база обнаружена, демоданные добавлены автоматически.")

    logger.info("Запуск фонового анализа видеопотоков...")
    stream_manager.start_all()
    
    yield

    logger.info("Остановка потоков...")
    for cam_id in list(stream_manager.workers.keys()):
        stream_manager.remove_camera(cam_id)

app = FastAPI(
    title="Biometric Access Control API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(departments.router)
app.include_router(job_positions.router)
app.include_router(cameras.router)
app.include_router(websockets.router)
app.include_router(analytics.router)
app.include_router(buildings.router)
app.include_router(floors.router)
app.include_router(route_graph.router)
app.include_router(guests.router)
app.include_router(users.router)
app.include_router(video_analysis.router)

@app.get("/")
def root():
    return {"status": "ok", "message": "API is running"}
