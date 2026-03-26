from sqlmodel import SQLModel, Field

class Camera(SQLModel, table=True):
    __tablename__ = "cameras"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    ip_address: str = Field(unique=True)
    is_active: bool = Field(default=True)