from passlib.context import CryptContext
from sqlmodel import Session, select
from wcore.database import engine
from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

valid_hash = pwd_context.hash("admin")

with Session(engine) as session:
    users = session.exec(select(User)).all()
    for user in users:
        user.password_hash = valid_hash
        session.add(user)
    
    session.commit()
    print("Успех! Пароли всех пользователей изменены на 'admin'.")