from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

import app.models  # noqa: F401
from app.api import analytics, auth, buildings, cameras, departments, employees, floors, guests, users, video_analysis, websockets
from app.core.database import engine
from app.services.stream_manager import stream_manager


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    print("Запуск фонового анализа видеопотоков...")
    stream_manager.start_all()
    yield

    print("Остановка потоков...")
    for cam_id in list(stream_manager.workers.keys()):
        stream_manager.remove_camera(cam_id)


app = FastAPI(
    title="Biometric Access Control API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(video_analysis.router)
app.include_router(employees.router)
app.include_router(departments.router)
app.include_router(cameras.router)
app.include_router(websockets.router)
app.include_router(analytics.router)
app.include_router(buildings.router)
app.include_router(floors.router)
app.include_router(guests.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "API is running"}
