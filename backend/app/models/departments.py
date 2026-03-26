from sqlmodel import SQLModel, Field

class Department(SQLModel, table=True):
    __tablename__ = "departments"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)