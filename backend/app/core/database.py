from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)

def get_session():
    """Генератор сессий для инъекции зависимостей в эндпоинты FastAPI"""
    with Session(engine) as session:
        yield session
