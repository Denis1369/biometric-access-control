from sqlmodel import SQLModel, Field
from datetime import time

class Department(SQLModel, table=True):
    __tablename__ = "departments"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    
    work_start: time = Field(default=time(9, 0))
    work_end: time = Field(default=time(18, 0))
    
    lunch_start: time = Field(default=time(13, 0))
    lunch_end: time = Field(default=time(14, 0))