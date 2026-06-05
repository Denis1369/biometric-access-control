"""Справочник должностей для карточек сотрудников.

Должность вынесена в отдельную таблицу, чтобы HR мог поддерживать единый список
наименований и привязывать их к отделам. В карточке сотрудника пока также есть
строковое поле position, но справочник нужен для удобного выбора и дальнейшего
развития кадрового модуля.
"""

from sqlmodel import SQLModel, Field

class JobPosition(SQLModel, table=True):
    """Одна должность, необязательно привязанная к отделу.

    is_active позволяет скрыть устаревшую должность без удаления истории,
    sort_order задаёт порядок отображения в списках, department_id ограничивает
    должность конкретным отделом, если это нужно.
    """

    __tablename__ = "job_positions"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=100)
    
    department_id: int | None = Field(default=None, foreign_key="departments.id")
