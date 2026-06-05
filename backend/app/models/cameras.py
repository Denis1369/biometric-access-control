"""Модель камеры для live-потоков, file-видео и отображения на плане.

Камера в системе является одновременно источником видеоданных и объектом
инфраструктуры здания. Она может быть реальной IP-камерой, RTSP-потоком или
локальным demo-видео. Поля floor_id, plan_x и plan_y позволяют показать камеру
на плане этажа, а direction помогает аналитике понять, является событие входом,
выходом или внутренним наблюдением.
"""

from sqlmodel import Field, SQLModel


class Camera(SQLModel, table=True):
    """Камера, её источник видео и положение на плане здания.

    ip_address исторически называется адресом, но в проекте в нём может лежать
    и RTSP URL, и путь к file-видео. plan_x/plan_y хранятся как относительные
    координаты от 0 до 1, чтобы маркер камеры не съезжал при масштабировании
    изображения плана.
    """

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
