"""API авторизации и получения текущего пользователя.

Этот router обслуживает вход в систему и проверку текущей сессии. Frontend
использует `/api/auth/login`, чтобы получить JWT-токен, а затем вызывает
`/api/auth/me`, чтобы узнать роль пользователя и список разрешений для показа
или скрытия разделов интерфейса. Реальная защита всё равно остаётся на backend:
frontend только делает интерфейс удобнее, но не считается источником прав.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import get_current_user
from app.core.permissions import get_permissions_for_role
from app.core.security import create_access_token, verify_password
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/auth", tags=["Авторизация"])


class TokenResponse(SQLModel):
    """Ответ после успешного входа в систему.

    В ответе возвращается токен доступа и базовая информация о пользователе,
    чтобы frontend сразу мог сохранить сессию, показать имя пользователя и
    перенаправить его на доступный раздел приложения.
    """

    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: UserRole


class CurrentUserResponse(SQLModel):
    """Данные текущего пользователя, которые frontend запрашивает при старте.

    Этот объект содержит не только роль, но и уже рассчитанный список permission.
    Благодаря этому интерфейс может быстро понять, какие кнопки и страницы
    доступны пользователю: например, технику показывается настройка плана, а
    оператору КПП — выдача гостевых пропусков.
    """

    id: int
    username: str
    role: UserRole
    permissions: list[str]
    is_active: bool
    employee_id: int | None = None


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    """Проверить логин и пароль пользователя и выдать JWT-токен.

    Функция вызывается со страницы входа. FastAPI получает поля username/password
    в стандартном OAuth2-формате, затем backend ищет пользователя в базе, сверяет
    пароль с хэшем и проверяет, что учётная запись активна. Если всё корректно,
    создаётся токен, который дальше передаётся во все защищённые API-запросы.
    """
    user = session.exec(
        select(User).where(User.username == form_data.username)
    ).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь деактивирован",
        )

    access_token = create_access_token(
        {"sub": str(user.id), "role": user.role.value}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Вернуть сведения о пользователе, которому принадлежит текущий JWT.

    Dependency `get_current_user` уже проверила токен и активность пользователя.
    Здесь остаётся собрать данные, необходимые frontend-у: id, логин, роль,
    права и связанный сотрудник, если учётная запись привязана к карточке
    сотрудника.
    """
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        permissions=sorted(get_permissions_for_role(current_user.role)),
        is_active=current_user.is_active,
        employee_id=current_user.employee_id,
    )
