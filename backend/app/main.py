import asyncio
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
    camera_visibility,
    cameras,
    departments,
    employees,
    floors,
    guest_route_analysis,
    guest_routes,
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
from app.models.user import UserRole
from app.services.guest_route_analysis_service import fail_interrupted_route_analysis_jobs
from app.services.stream_manager import stream_manager
from app.services.websocket_manager import topic_ws_manager

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
    user_columns = {column["name"]: column for column in inspector.get_columns("users")}

    statements: list[str] = []
    if "body_embedding" not in guest_columns:
        statements.append("ALTER TABLE guests ADD COLUMN body_embedding JSON NULL")
    if "body_embedding_updated_at" not in guest_columns:
        statements.append(
            "ALTER TABLE guests ADD COLUMN body_embedding_updated_at DATETIME NULL"
        )
    role_column = user_columns.get("role")
    if role_column is not None and engine.dialect.name == "mysql":
        role_type = str(role_column["type"]).lower()
        role_values = [role.value for role in UserRole]
        if not all(value in role_type for value in role_values):
            enum_values = ", ".join(f"'{value}'" for value in role_values)
            statements.append(
                "ALTER TABLE users "
                f"MODIFY COLUMN role ENUM({enum_values}) "
                f"NOT NULL DEFAULT '{UserRole.CHECKPOINT_OPERATOR.value}'"
            )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)

    logger.info("Применены runtime-обновления схемы для Re-ID.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    topic_ws_manager.set_loop(asyncio.get_running_loop())
    create_db_and_tables()
    ensure_runtime_schema_updates()

    with Session(engine) as session:
        seeded = ensure_demo_data(session)
        if seeded:
            logger.info("Пустая база обнаружена, демоданные добавлены автоматически.")

    interrupted_jobs = fail_interrupted_route_analysis_jobs()
    if interrupted_jobs:
        logger.warning(
            "Помечены как прерванные незавершённые offline route jobs: %s",
            interrupted_jobs,
        )

    logger.info("Запуск фонового анализа видеопотоков...")
    stream_manager.start_all()
    
    yield

    logger.info("Остановка потоков...")
    topic_ws_manager.set_loop(None)
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
app.include_router(camera_visibility.router)
app.include_router(websockets.router)
app.include_router(analytics.router)
app.include_router(buildings.router)
app.include_router(floors.router)
app.include_router(route_graph.router)
app.include_router(guest_route_analysis.router)
app.include_router(guest_routes.router)
app.include_router(guests.router)
app.include_router(users.router)
app.include_router(video_analysis.router)

@app.get("/")
def root():
    return {"status": "ok", "message": "API is running"}
