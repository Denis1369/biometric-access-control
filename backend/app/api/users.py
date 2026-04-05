from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel, select

from app.core.database import get_session
from app.core.deps import get_current_user, require_roles
from app.core.security import get_password_hash
from app.models.employees import Employee
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/users", tags=["Пользователи"])

PRACTICE_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.CHECKPOINT_OPERATOR,
}


class UserRead(SQLModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    employee_id: int | None = None
    employee_name: str | None = None


class UserCreate(SQLModel):
    username: str
    password: str
    role: UserRole = UserRole.CHECKPOINT_OPERATOR
    is_active: bool = True
    employee_id: int | None = None


class UserUpdate(SQLModel):
    username: str | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    employee_id: int | None = None


def build_employee_name(employee: Employee | None) -> str | None:
    if not employee:
        return None
    return " ".join(
        part for part in [employee.last_name, employee.first_name, employee.middle_name] if part
    ).strip() or None


def build_user_read(session: Session, user: User) -> UserRead:
    employee = session.get(Employee, user.employee_id) if user.employee_id else None
    return UserRead(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        employee_id=user.employee_id,
        employee_name=build_employee_name(employee),
    )


def validate_employee_link(session: Session, employee_id: int | None, ignore_user_id: int | None = None) -> None:
    if employee_id is None:
        return

    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=400, detail="Указанный сотрудник не найден")

    existing_user = session.exec(select(User).where(User.employee_id == employee_id)).first()
    if existing_user and existing_user.id != ignore_user_id:
        raise HTTPException(status_code=400, detail="Этот сотрудник уже привязан к другому пользователю")


def validate_practice_role(role: UserRole) -> None:
    if role not in PRACTICE_ROLES:
        raise HTTPException(
            status_code=400,
            detail="На текущем этапе доступны только роли super_admin и checkpoint_operator",
        )


@router.get(
    "/",
    response_model=List[UserRead],
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)
def get_users(session: Session = Depends(get_session)):
    users = session.exec(select(User).order_by(User.id.desc())).all()
    return [build_user_read(session, user) for user in users]


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)
def create_user(payload: UserCreate, session: Session = Depends(get_session)):
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Логин должен содержать минимум 3 символа")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")

    validate_practice_role(payload.role)

    exists = session.exec(select(User).where(User.username == username)).first()
    if exists:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")

    validate_employee_link(session, payload.employee_id)

    user = User(
        username=username,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        employee_id=payload.employee_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return build_user_read(session, user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_roles(UserRole.SUPER_ADMIN))],
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    data = payload.model_dump(exclude_unset=True)

    if "username" in data:
        username = (data["username"] or "").strip()
        if len(username) < 3:
            raise HTTPException(status_code=400, detail="Логин должен содержать минимум 3 символа")
        exists = session.exec(select(User).where(User.username == username, User.id != user_id)).first()
        if exists:
            raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
        user.username = username

    if "employee_id" in data:
        validate_employee_link(session, data["employee_id"], ignore_user_id=user_id)
        user.employee_id = data["employee_id"]

    if "role" in data:
        validate_practice_role(data["role"])
        if current_user.id == user.id and data["role"] != UserRole.SUPER_ADMIN:
            raise HTTPException(status_code=400, detail="Нельзя снять роль super_admin у своей учетной записи")
        user.role = data["role"]

    if "is_active" in data:
        if current_user.id == user.id and data["is_active"] is False:
            raise HTTPException(status_code=400, detail="Нельзя деактивировать свою учетную запись")
        user.is_active = data["is_active"]

    if "password" in data and data["password"]:
        if len(data["password"]) < 6:
            raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")
        user.password_hash = get_password_hash(data["password"])

    session.add(user)
    session.commit()
    session.refresh(user)
    return build_user_read(session, user)
