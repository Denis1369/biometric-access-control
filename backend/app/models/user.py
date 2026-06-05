"""Модели учётных записей пользователей и их ролей.

Таблица users отвечает не за кадровую карточку человека, а за вход в систему:
логин, хэш пароля, роль, активность и необязательную связь с сотрудником. Роль
дальше превращается в набор permissions в core/permissions.py и определяет,
какие разделы интерфейса доступны пользователю.
"""

from enum import Enum

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Enum as SAEnum, String


class UserRole(str, Enum):
    """Роли пользователей, которые используются в backend и frontend.

    Эти строковые значения сохраняются в MySQL и передаются клиенту. Они должны
    оставаться стабильными, потому что от них зависят меню, кнопки и проверки
    доступа. Legacy-роли оставлены для старых записей базы, чтобы приложение
    могло загрузиться даже после изменения ролевой модели.
    """

    SUPER_ADMIN = "super_admin"
    CHECKPOINT_OPERATOR = "checkpoint_operator"
    TECHNICIAN = "technician"
    HR = "hr"
    ANALYST = "analyst"

    # Старые роли сохранены для безопасного чтения существующих строк БД до
    # ручного переназначения пользователей на новые роли.
    MANAGER_ANALYST = "manager_analyst"
    TECH_HR = "tech_hr"


def user_role_values(enum_cls: type[UserRole]) -> list[str]:
    """Вернуть строковые значения ролей для SQLAlchemy Enum.

    MySQL должен хранить именно значения вроде `super_admin`, а не Python-имена
    enum-полей. Это делает БД понятнее и стабильнее при обмене данными с
    frontend-ом.
    """

    return [role.value for role in enum_cls]


class User(SQLModel, table=True):
    """Учётная запись для входа в систему и проверки прав.

    username используется при авторизации, password_hash хранит bcrypt-хэш
    пароля, role определяет доступные действия, is_active позволяет отключить
    вход без удаления истории, а employee_id связывает логин с карточкой
    сотрудника, если пользователь является реальным сотрудником организации.
    """

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(100), unique=True, nullable=False, index=True))
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    role: UserRole = Field(
        default=UserRole.CHECKPOINT_OPERATOR,
        sa_column=Column(
            SAEnum(UserRole, values_callable=user_role_values),
            nullable=False,
            default=UserRole.CHECKPOINT_OPERATOR.value,
        ),
    )
    is_active: bool = Field(default=True)

    employee_id: int | None = Field(default=None, foreign_key="employees.id", unique=True)
