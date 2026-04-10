from sqlmodel import SQLModel, Field

class JobPosition(SQLModel, table=True):
    __tablename__ = "job_positions"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=100)
    
    department_id: int | None = Field(default=None, foreign_key="departments.id")