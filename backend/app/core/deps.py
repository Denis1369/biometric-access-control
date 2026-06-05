"""FastAPI dependency для авторизации и проверки прав.

Endpoint-ы проекта не должны самостоятельно разбирать JWT и проверять роли.
Вместо этого они подключают dependency из этого файла: `get_current_user`,
`require_roles`, `require_permissions` или `require_any_permission`.

Такой слой делает правила доступа едиными для всего backend-а. Если пользователь
не авторизован, деактивирован или не имеет нужного разрешения, endpoint получает
готовую HTTPException, а бизнес-логика не выполняется.
"""

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.core.database import get_session
from app.core.permissions import get_permissions_for_role
from app.core.security import decode_access_token_subject
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Определить текущего пользователя по JWT-токену.

    Функция используется как dependency в защищённых endpoint-ах. Токен может
    прийти стандартным способом через заголовок Authorization: Bearer, а также
    через query-параметр `token`. Второй вариант нужен для WebSocket и некоторых
    браузерных сценариев, где передать Bearer-заголовок сложнее.

    После декодирования subject из JWT backend читает пользователя из БД и
    отдельно проверяет `is_active`. Это позволяет администратору быстро закрыть
    доступ без удаления учётной записи и истории действий.

    Параметры:
        request: Текущий HTTP-запрос. Нужен для fallback-чтения token из query.
        token: Bearer-токен из OAuth2PasswordBearer, если он был передан.
        session: Сессия БД для загрузки пользователя.

    Возвращает:
        Активный пользователь, который выполняет запрос.

    Ошибки:
        HTTPException: 401, если токен отсутствует или недействителен; 403, если
        учётная запись деактивирована.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    raw_token = token or request.query_params.get("token")
    if not raw_token:
        raise credentials_exception

    user_id = decode_access_token_subject(raw_token)
    if user_id is None:
        raise credentials_exception

    user = session.get(User, user_id)
    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь деактивирован",
        )

    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    """Создать dependency для проверки роли пользователя.

    Сейчас основная модель доступа строится на permissions, но проверка ролей
    остаётся полезной для простых административных правил или совместимости.
    Функция возвращает вложенную dependency, которую можно передать в Depends.

    Параметры:
        allowed_roles: Роли, которым разрешено выполнить endpoint.

    Возвращает:
        Dependency, возвращающая текущего пользователя при успешной проверке.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        """Проверить, что текущая роль входит в список разрешённых."""

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )
        return current_user

    return dependency


def require_permissions(*required_permissions: str) -> Callable:
    """Создать dependency, требующую все перечисленные разрешения.

    Это основной способ защиты endpoint-ов. Например, сохранение зоны видимости
    камеры требует CAMERA_ZONES_WRITE, а чтение маршрута гостя — GUEST_ROUTES_READ.
    Если хотя бы одного разрешения нет, запрос завершается 403.

    Параметры:
        required_permissions: Набор permissions, которые должны присутствовать
            у роли текущего пользователя.

    Возвращает:
        Dependency, возвращающая пользователя после успешной проверки.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        """Проверить наличие всех требуемых permissions у текущего пользователя."""

        permissions = get_permissions_for_role(current_user.role)
        missing_permissions = [
            permission
            for permission in required_permissions
            if permission not in permissions
        ]
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )
        return current_user

    return dependency


def require_any_permission(*allowed_permissions: str) -> Callable:
    """Создать dependency, где достаточно одного разрешения из списка.

    Используется для endpoint-ов, которые доступны нескольким уровням доступа.
    Например, полный журнал проходов и последние события проходной могут быть
    разными permissions, но оба разрешают открыть один и тот же поток данных.

    Параметры:
        allowed_permissions: Список разрешений, любое из которых подходит.

    Возвращает:
        Dependency, возвращающая текущего пользователя при успешной проверке.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        """Проверить, что у пользователя есть хотя бы одно разрешение."""

        permissions = get_permissions_for_role(current_user.role)
        if not any(permission in permissions for permission in allowed_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )
        return current_user

    return dependency
