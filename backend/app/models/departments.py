"""Модель отдела с рабочим графиком для аналитики посещаемости.

Отдел нужен не только для группировки сотрудников. Его рабочее время используется
при расчёте опозданий и ранних уходов, поэтому график хранится рядом с отделом,
а не зашивается в код аналитики.
"""

from sqlmodel import SQLModel, Field
from datetime import time

class Department(SQLModel, table=True):
    """Отдел организации и стандартные границы рабочего дня/обеда.

    work_start/work_end задают нормальный рабочий день, lunch_start/lunch_end
    оставлены для отчётности и будущих сценариев, где нужно учитывать обеденный
    перерыв при анализе посещаемости.
    """

    __tablename__ = "departments"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    
    work_start: time = Field(default=time(9, 0))
    work_end: time = Field(default=time(18, 0))
    
    lunch_start: time = Field(default=time(13, 0))
    lunch_end: time = Field(default=time(14, 0))
