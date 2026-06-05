"""Модель сотрудников организации.

Файл описывает основную таблицу сотрудников, которые могут проходить через КПП,
попадать в отчёты посещаемости и связываться с учётной записью пользователя.
Фотографии лиц и embedding-векторы вынесены в отдельную таблицу, чтобы у одного
сотрудника можно было хранить несколько биометрических образцов.
"""

from sqlmodel import SQLModel, Field


class Employee(SQLModel, table=True):
    """Карточка сотрудника, используемая в HR-разделе, аналитике и распознавании.

    Здесь хранится только кадровая часть: ФИО, должность, отдел и признак
    активности. Если сотрудник уволен или временно не используется в системе,
    запись можно оставить в базе, но снять активность, чтобы не потерять историю
    проходов и аналитики.
    """

    __tablename__ = "employees"

    id: int | None = Field(default=None, primary_key=True)
    last_name: str = Field(index=True)
    first_name: str
    middle_name: str | None = Field(default=None)
    position: str | None = Field(default=None)
    department_id: int | None = Field(default=None, foreign_key="departments.id")
    is_active: bool = Field(default=True)
