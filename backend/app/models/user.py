from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Enum as SAEnum, String

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    CHECKPOINT_OPERATOR = "checkpoint_operator"
    TECHNICIAN = "technician"
    HR = "hr"
    ANALYST = "analyst"

    # Legacy roles are kept so existing database rows can still be read safely.
    MANAGER_ANALYST = "manager_analyst"
    TECH_HR = "tech_hr"


def user_role_values(enum_cls: type[UserRole]) -> list[str]:
    return [role.value for role in enum_cls]


class User(SQLModel, table=True):
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
