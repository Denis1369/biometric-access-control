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
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )
        return current_user

    return dependency


def require_permissions(*required_permissions: str) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
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
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        permissions = get_permissions_for_role(current_user.role)
        if not any(permission in permissions for permission in allowed_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции",
            )
        return current_user

    return dependency
