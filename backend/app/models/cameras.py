from sqlmodel import SQLModel, Field


class Camera(SQLModel, table=True):
    __tablename__ = "cameras"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    ip_address: str = Field(unique=True)
    is_active: bool = Field(default=True)

    building_id: int | None = Field(default=None, foreign_key="buildings.id", index=True)
    floor_id: int | None = Field(default=None, foreign_key="floors.id", index=True)

    plan_x: float | None = Field(default=None)
    plan_y: float | None = Field(default=None)

    direction: str = Field(default="in")