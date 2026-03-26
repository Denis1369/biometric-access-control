from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.core.database import engine
import app.models 
from app.api import employees, departments, cameras, analytics, websockets


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(
    title="Biometric Access Control API", 
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees.router)
app.include_router(employees.router)
app.include_router(departments.router)
app.include_router(cameras.router)
app.include_router(websockets.router)
app.include_router(analytics.router)

@app.get("/")
def root():
    return {"status": "ok", "message": "API is running"}