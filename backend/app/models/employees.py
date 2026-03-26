from sqlmodel import SQLModel, Field

class Employee(SQLModel, table=True):
    __tablename__ = "employees"

    id: int | None = Field(default=None, primary_key=True)
    last_name: str = Field(index=True)
    first_name: str
    middle_name: str | None = Field(default=None)
    department_id: int | None = Field(default=None, foreign_key="departments.id")
    is_active: bool = Field(default=True)