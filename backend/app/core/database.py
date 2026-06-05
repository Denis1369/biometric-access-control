"""Подключение к MySQL и dependency для сессий SQLModel.

Backend работает с базой через SQLModel/SQLAlchemy. В приложении создаётся один
общий engine, а на каждый HTTP-запрос FastAPI получает отдельную Session через
dependency `get_session`. Такой подход важен: endpoint работает в рамках своей
сессии, после завершения запроса она закрывается, а соединения переиспользуются
пулом SQLAlchemy.
"""

from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)

def get_session():
    """Отдать сессию БД для одного запроса FastAPI.

    Dependency используется почти во всех endpoint-ах и сервисах, которые
    вызываются из API. `yield` гарантирует, что после обработки запроса сессия
    будет закрыта. Параметр pool_pre_ping у engine дополнительно проверяет
    соединение перед использованием, что полезно для MySQL: если сервер закрыл
    idle-соединение, SQLAlchemy откроет новое вместо падения первого запроса.

    Генерирует:
        Session: активная SQLModel-сессия для чтения и записи данных.
    """

    with Session(engine) as session:
        yield session
