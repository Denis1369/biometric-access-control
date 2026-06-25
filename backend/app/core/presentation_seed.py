"""Очистка и презентационное наполнение базы данных.

Этот модуль используется перед подготовкой скриншотов для отчёта и защиты
диплома. Обычный seed проекта специально не затирает существующие данные, чтобы
не мешать разработке. Здесь задача другая: получить чистую, аккуратную и
правдоподобную базу, где интерфейс выглядит как рабочая система, а не как набор
случайных тестов.

Скрипт делает три вещи:
1. Сохраняет резервную JSON-копию текущих строк в storage/db_backups.
2. Очищает прикладные таблицы системы.
3. Заполняет базу презентационными данными: пользователями разных ролей,
   сотрудниками, гостями, зданием УКСИВТ, этажом с планом, камерами, зонами
   видимости, графом маршрутов и журналами событий.

Запускать из папки backend:
    python -m app.core.presentation_seed
"""

from __future__ import annotations

import base64
import json
import math
import random
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401  # импорт нужен, чтобы SQLModel видел все таблицы
from app.core.config import PROJECT_ROOT
from app.core.database import engine
from app.core.security import get_password_hash
from app.models.buildings import Building
from app.models.camera_visibility_zones import CameraVisibilityZone
from app.models.cameras import Camera
from app.models.departments import Department
from app.models.employee_face_samples import EmployeeFaceSample
from app.models.employees import Employee
from app.models.floors import Floor
from app.models.guest_route_analysis_jobs import GuestRouteAnalysisJob
from app.models.guests import Guest, GuestFaceSample
from app.models.job_positions import JobPosition
from app.models.logs import AccessLog, TrackingLog
from app.models.route_edges import RouteEdge
from app.models.route_nodes import RouteNode
from app.models.user import User, UserRole
from app.models.video_analysis import VideoAnalysisEvent, VideoAnalysisJob


BACKUP_DIR = PROJECT_ROOT / "storage" / "db_backups"
PLAN_PATH = PROJECT_ROOT / "test_video" / "detailed_floor_plan_clean.png"
LAYOUT_PATH = PROJECT_ROOT / "test_video" / "recommended_camera_layout.json"

RANDOM_SEED = 20260610

TABLE_MODELS = [
    VideoAnalysisEvent,
    VideoAnalysisJob,
    GuestRouteAnalysisJob,
    TrackingLog,
    AccessLog,
    CameraVisibilityZone,
    RouteEdge,
    RouteNode,
    GuestFaceSample,
    Guest,
    EmployeeFaceSample,
    User,
    Camera,
    Floor,
    Building,
    JobPosition,
    Employee,
    Department,
]


def _serialize_value(value: Any) -> Any:
    """Преобразовать значение модели в JSON-совместимый вид для резервной копии."""

    if isinstance(value, bytes):
        return {"__bytes_base64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def backup_current_data(session: Session) -> Path:
    """Сохранить текущие строки основных таблиц перед очисткой.

    Резервная копия нужна как страховка: очистка БД является намеренно
    разрушительной операцией. Файл не является полноценным миграционным дампом
    MySQL, но содержит данные всех прикладных SQLModel-таблиц, включая BLOB-поля
    в base64. Для восстановления вручную этого обычно достаточно.
    """

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"presentation_reset_{datetime.now():%Y%m%d_%H%M%S}.json"
    payload: dict[str, list[dict[str, Any]]] = {}

    for model in TABLE_MODELS:
        rows = session.exec(select(model)).all()
        payload[model.__tablename__] = [
            {
                key: _serialize_value(value)
                for key, value in row.model_dump().items()
            }
            for row in rows
        ]

    backup_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return backup_path


def clear_application_tables(session: Session) -> None:
    """Очистить прикладные таблицы и сбросить автоинкременты.

    На время очистки отключается проверка внешних ключей MySQL. Это проще и
    безопаснее, чем пытаться вручную подобрать идеальный порядок удаления для
    всех связей. После удаления проверка включается обратно.
    """

    session.exec(text("SET FOREIGN_KEY_CHECKS = 0"))
    for model in TABLE_MODELS:
        table_name = model.__tablename__
        session.exec(text(f"DELETE FROM `{table_name}`"))
        session.exec(text(f"ALTER TABLE `{table_name}` AUTO_INCREMENT = 1"))
    session.exec(text("SET FOREIGN_KEY_CHECKS = 1"))
    session.commit()


def _load_layout() -> dict[str, Any]:
    """Прочитать рекомендованную расстановку камер и графа для плана УКСИВТ."""

    return json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))


def _body_embedding(seed: int) -> list[float]:
    """Сформировать стабильный демонстрационный Re-ID вектор гостя.

    Это не реальный биометрический образец, а презентационная заглушка, чтобы в
    интерфейсе гость выглядел полностью оформленным и кнопки маршрута были
    доступны. Размер 512 выбран как типичный размер embedding Re-ID модели.
    """

    rng = random.Random(seed)
    values = [rng.uniform(-1.0, 1.0) for _ in range(512)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [round(value / norm, 6) for value in values]


def seed_departments(session: Session) -> dict[str, Department]:
    """Создать небольшое количество отделов с рабочими графиками."""

    specs = [
        ("Безопасность", time(8, 0), time(17, 0), time(12, 30), time(13, 0)),
        ("Учебная часть", time(8, 30), time(17, 30), time(13, 0), time(14, 0)),
        ("IT-инфраструктура", time(9, 0), time(18, 0), time(13, 0), time(14, 0)),
        ("Бухгалтерия", time(9, 0), time(18, 0), time(13, 0), time(14, 0)),
        ("Администрация", time(9, 0), time(18, 0), time(13, 0), time(14, 0)),
    ]
    departments: dict[str, Department] = {}
    for name, work_start, work_end, lunch_start, lunch_end in specs:
        department = Department(
            name=name,
            work_start=work_start,
            work_end=work_end,
            lunch_start=lunch_start,
            lunch_end=lunch_end,
        )
        session.add(department)
        session.flush()
        departments[name] = department
    return departments


def seed_job_positions(session: Session, departments: dict[str, Department]) -> None:
    """Создать справочник должностей, который выглядит естественно в HR-разделе."""

    specs = [
        ("Оператор КПП", "Безопасность", 10),
        ("Старший смены", "Безопасность", 20),
        ("Инспектор безопасности", "Безопасность", 30),
        ("Методист", "Учебная часть", 10),
        ("Секретарь учебной части", "Учебная часть", 20),
        ("Системный администратор", "IT-инфраструктура", 10),
        ("Сетевой инженер", "IT-инфраструктура", 20),
        ("Бухгалтер", "Бухгалтерия", 10),
        ("Экономист", "Бухгалтерия", 20),
        ("Диспетчер", "Администрация", 10),
        ("Специалист по кадрам", "Администрация", 20),
    ]
    for name, department_name, sort_order in specs:
        session.add(
            JobPosition(
                name=name,
                department_id=departments[department_name].id,
                sort_order=sort_order,
                is_active=True,
            )
        )


def seed_employees(session: Session, departments: dict[str, Department]) -> dict[str, Employee]:
    """Создать компактный список сотрудников для карточек и аналитики."""

    specs = [
        ("Данилов", "Олег", "Олегович", "Оператор КПП", "Безопасность"),
        ("Белова", "Ирина", "Алексеевна", "Старший смены", "Безопасность"),
        ("Белов", "Сергей", "Алексеевич", "Инспектор безопасности", "Безопасность"),
        ("Иванова", "Мария", "Сергеевна", "Методист", "Учебная часть"),
        ("Кузнецов", "Артём", "Игоревич", "Секретарь учебной части", "Учебная часть"),
        ("Елисеев", "Олег", "Евгеньевич", "Системный администратор", "IT-инфраструктура"),
        ("Орлов", "Иван", "Евгеньевич", "Сетевой инженер", "IT-инфраструктура"),
        ("Нестерова", "Анна", "Андреевна", "Бухгалтер", "Бухгалтерия"),
        ("Рябов", "Олег", "Игоревич", "Экономист", "Бухгалтерия"),
        ("Зайцева", "Алина", "Сергеевна", "Специалист по кадрам", "Администрация"),
        ("Медведев", "Павел", "Владимирович", "Диспетчер", "Администрация"),
        ("Титова", "Дарья", "Сергеевна", "Специалист по кадрам", "Администрация"),
    ]
    employees: dict[str, Employee] = {}
    for last_name, first_name, middle_name, position, department_name in specs:
        employee = Employee(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            position=position,
            department_id=departments[department_name].id,
            is_active=True,
        )
        session.add(employee)
        session.flush()
        employees[f"{last_name} {first_name}"] = employee
    return employees


def seed_users(session: Session, employees: dict[str, Employee]) -> None:
    """Создать пользователей разных ролей для проверки меню и прав доступа."""

    specs = [
        ("admin", "admin", UserRole.SUPER_ADMIN, None),
        ("operator", "operator", UserRole.CHECKPOINT_OPERATOR, "Данилов Олег"),
        ("technician", "technician", UserRole.TECHNICIAN, "Орлов Иван"),
        ("hr", "hr", UserRole.HR, "Зайцева Алина"),
        ("analyst", "analyst", UserRole.ANALYST, "Иванова Мария"),
    ]
    for username, password, role, employee_key in specs:
        session.add(
            User(
                username=username,
                password_hash=get_password_hash(password),
                role=role,
                is_active=True,
                employee_id=employees[employee_key].id if employee_key else None,
            )
        )


def seed_building_floor(session: Session) -> tuple[Building, Floor]:
    """Создать корпус УКСИВТ и загрузить детальный план второго этажа."""

    building = Building(
        name="УКСИВТ",
        address="г. Екатеринбург, ул. Кирова, 65",
    )
    session.add(building)
    session.flush()

    floor = Floor(
        building_id=building.id,
        name="Основной",
        floor_number=2,
        plan_mime_type="image/png",
        plan_image=PLAN_PATH.read_bytes(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(floor)
    session.flush()
    return building, floor


def _camera_source(camera_number: int) -> str:
    """Вернуть путь к синхронизированному demo-видео камеры."""

    trimmed_path = PROJECT_ROOT / "test_video" / "trimmed_114630_114845" / f"{camera_number}.mp4"
    if trimmed_path.exists():
        return f"file://test_video/trimmed_114630_114845/{camera_number}.mp4"
    return f"file://test_video/{camera_number}.mp4"


def seed_cameras_zones_and_graph(
    session: Session,
    building: Building,
    floor: Floor,
) -> dict[int, Camera]:
    """Создать камеры УКСИВТ, зоны видимости и маршрутный граф."""

    layout = _load_layout()
    cameras_by_number: dict[int, Camera] = {}
    directions = {
        1: "in",
        2: "internal",
        3: "internal",
        4: "internal",
        5: "internal",
        6: "out",
    }

    for camera_data in layout["recommended_cameras"]:
        camera_number = int(camera_data["camera_number"])
        camera = Camera(
            name=f"UKSIVT Camera{camera_number:02d}",
            ip_address=_camera_source(camera_number),
            is_active=True,
            building_id=building.id,
            floor_id=floor.id,
            plan_x=float(camera_data["plan_x_normalized"]),
            plan_y=float(camera_data["plan_y_normalized"]),
            direction=directions.get(camera_number, "internal"),
        )
        session.add(camera)
        session.flush()
        cameras_by_number[camera_number] = camera

        points = [
            {"x": float(point["x"]), "y": float(point["y"])}
            for point in camera_data["visibility_zone_points"]
        ]
        session.add(
            CameraVisibilityZone(
                camera_id=camera.id,
                floor_id=floor.id,
                points_json=points,
            )
        )

    logical_to_db_id: dict[int, int] = {}
    node_models: dict[int, RouteNode] = {}
    for node_data in layout["suggested_route_graph"]["nodes"]:
        node = RouteNode(
            floor_id=floor.id,
            x=float(node_data["x"]),
            y=float(node_data["y"]),
        )
        session.add(node)
        session.flush()
        logical_id = int(node_data["id"])
        logical_to_db_id[logical_id] = int(node.id)
        node_models[logical_id] = node

    for edge_data in layout["suggested_route_graph"]["edges"]:
        from_logical_id = int(edge_data["from_node_id"])
        to_logical_id = int(edge_data["to_node_id"])
        from_node = node_models[from_logical_id]
        to_node = node_models[to_logical_id]
        session.add(
            RouteEdge(
                floor_id=floor.id,
                from_node_id=logical_to_db_id[from_logical_id],
                to_node_id=logical_to_db_id[to_logical_id],
                weight=round(math.hypot(to_node.x - from_node.x, to_node.y - from_node.y), 2),
                is_bidirectional=True,
            )
        )

    return cameras_by_number


def seed_guests(session: Session, employees: dict[str, Employee]) -> dict[str, Guest]:
    """Создать гостей с активными и завершёнными пропусками."""

    now = datetime.now().replace(second=0, microsecond=0)
    specs = [
        ("Иванов", "Иван", "Петрович", "Иванова Мария", now + timedelta(days=2), True, 1),
        ("Смирнова", "Екатерина", "Андреевна", "Зайцева Алина", now + timedelta(days=1), True, 2),
        ("Соколов", "Дмитрий", "Олегович", "Елисеев Олег", now - timedelta(days=1), False, 3),
    ]
    guests: dict[str, Guest] = {}
    for last_name, first_name, middle_name, host_key, valid_until, is_active, seed in specs:
        guest = Guest(
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            employee_id=employees[host_key].id,
            valid_until=valid_until,
            is_active=is_active,
            body_embedding=_body_embedding(seed),
            body_embedding_updated_at=now - timedelta(hours=seed),
        )
        session.add(guest)
        session.flush()
        guests[f"{last_name} {first_name}"] = guest
    return guests


def _workday_dates(days_back: int = 12) -> list[date]:
    """Вернуть последние рабочие дни для генерации месячной аналитики."""

    today = date.today()
    days: list[date] = []
    for offset in range(days_back - 1, -1, -1):
        current = today - timedelta(days=offset)
        if current.weekday() < 5:
            days.append(current)
    return days


def seed_access_and_tracking_logs(
    session: Session,
    employees: dict[str, Employee],
    guests: dict[str, Guest],
    cameras: dict[int, Camera],
) -> None:
    """Создать журналы проходов и отслеживания для живого дашборда."""

    rng = random.Random(RANDOM_SEED)
    today = date.today()
    workdays = _workday_dates()
    employee_list = list(employees.values())

    for current_day in workdays:
        for index, employee in enumerate(employee_list):
            if current_day != today and rng.random() < 0.08:
                continue

            arrival_base = datetime.combine(current_day, time(8, 45))
            arrival = arrival_base + timedelta(minutes=rng.randint(-18, 42))
            departure_base = datetime.combine(current_day, time(17, 30))
            departure = departure_base + timedelta(minutes=rng.randint(-35, 55))

            in_camera = cameras[1]
            out_camera = cameras[6]
            confidence = round(rng.uniform(0.91, 0.99), 3)
            session.add(
                AccessLog(
                    employee_id=employee.id,
                    camera_id=in_camera.id,
                    timestamp=arrival,
                    status="granted",
                    confidence=confidence,
                )
            )
            if index % 7 == 0 and current_day == today:
                session.add(
                    AccessLog(
                        employee_id=employee.id,
                        camera_id=in_camera.id,
                        timestamp=arrival - timedelta(minutes=3),
                        status="denied",
                        confidence=0.62,
                    )
                )
            if current_day != today or index % 4 != 0:
                session.add(
                    AccessLog(
                        employee_id=employee.id,
                        camera_id=out_camera.id,
                        timestamp=departure,
                        status="granted",
                        confidence=round(rng.uniform(0.9, 0.99), 3),
                    )
                )

            if rng.random() < 0.55:
                session.add(
                    TrackingLog(
                        employee_id=employee.id,
                        camera_id=rng.choice([cameras[2].id, cameras[3].id, cameras[5].id]),
                        timestamp=arrival + timedelta(minutes=rng.randint(25, 190)),
                        confidence=round(rng.uniform(0.82, 0.96), 3),
                    )
                )

    ivan = guests["Иванов Иван"]
    route_times = [
        (cameras[1], datetime.combine(today, time(10, 7)), "access_in"),
        (cameras[2], datetime.combine(today, time(10, 10)), "track"),
        (cameras[3], datetime.combine(today, time(10, 15)), "track"),
        (cameras[5], datetime.combine(today, time(10, 23)), "track"),
        (cameras[6], datetime.combine(today, time(10, 31)), "track"),
        (cameras[6], datetime.combine(today, time(10, 36)), "access_out"),
    ]
    for camera, timestamp, event_type in route_times:
        if event_type == "track":
            session.add(
                TrackingLog(
                    guest_id=ivan.id,
                    camera_id=camera.id,
                    timestamp=timestamp,
                    confidence=0.91,
                )
            )
        else:
            session.add(
                AccessLog(
                    guest_id=ivan.id,
                    camera_id=camera.id,
                    timestamp=timestamp,
                    status="granted",
                    confidence=0.93,
                )
            )

    smirnova = guests["Смирнова Екатерина"]
    session.add(
        AccessLog(
            guest_id=smirnova.id,
            camera_id=cameras[1].id,
            timestamp=datetime.combine(today, time(14, 5)),
            status="granted",
            confidence=0.89,
        )
    )
    session.add(
        TrackingLog(
            guest_id=smirnova.id,
            camera_id=cameras[3].id,
            timestamp=datetime.combine(today, time(14, 18)),
            confidence=0.84,
        )
    )

    sokolov = guests["Соколов Дмитрий"]
    yesterday = today - timedelta(days=1)
    session.add(
        AccessLog(
            guest_id=sokolov.id,
            camera_id=cameras[1].id,
            timestamp=datetime.combine(yesterday, time(11, 20)),
            status="granted",
            confidence=0.87,
        )
    )
    session.add(
        AccessLog(
            guest_id=sokolov.id,
            camera_id=cameras[6].id,
            timestamp=datetime.combine(yesterday, time(12, 4)),
            status="granted",
            confidence=0.88,
        )
    )


def seed_analysis_jobs(
    session: Session,
    guests: dict[str, Guest],
    floor: Floor,
) -> None:
    """Добавить завершённые задания анализа для презентационных экранов."""

    today = date.today()
    started_at = datetime.combine(today, time(10, 8))
    finished_at = datetime.combine(today, time(10, 34))
    ivan = guests["Иванов Иван"]

    session.add(
        GuestRouteAnalysisJob(
            guest_id=ivan.id,
            floor_id=floor.id,
            status="completed",
            processed_cameras=6,
            events_written=4,
            warnings_json=[],
            created_at=started_at - timedelta(minutes=2),
            started_at=started_at,
            finished_at=finished_at,
        )
    )

    video_job = VideoAnalysisJob(
        original_filename="uksivt_demo_route.mp4",
        source_path="storage/video_analysis/uksivt_demo_route.mp4",
        status="completed",
        reader_backend="pyav",
        total_frames=4200,
        analyzed_frames=4200,
        duration_sec=135.0,
        granted_count=5,
        denied_count=1,
        created_at=datetime.combine(today, time(9, 45)),
        started_at=datetime.combine(today, time(9, 46)),
        finished_at=datetime.combine(today, time(9, 49)),
    )
    session.add(video_job)
    session.flush()
    for frame_index, sec, status, person_name, confidence in [
        (180, 6.0, "granted", "Иванов Иван", 0.92),
        (840, 28.0, "granted", "Иванов Иван", 0.9),
        (1620, 54.0, "denied", "Неизвестное лицо", 0.58),
        (2760, 92.0, "granted", "Иванов Иван", 0.94),
    ]:
        session.add(
            VideoAnalysisEvent(
                job_id=video_job.id,
                frame_index=frame_index,
                timestamp_sec=sec,
                status=status,
                person_type="guest" if status == "granted" else None,
                person_id=ivan.id if status == "granted" else None,
                person_name=person_name,
                decision="доступ разрешён" if status == "granted" else "требуется проверка оператором",
                confidence=confidence,
                distance=round(1 - confidence, 3),
                preview_path=None,
            )
        )


def reset_presentation_database() -> dict[str, Any]:
    """Полностью пересобрать демонстрационное содержимое БД."""

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        backup_path = backup_current_data(session)
        clear_application_tables(session)

        departments = seed_departments(session)
        seed_job_positions(session, departments)
        employees = seed_employees(session, departments)
        seed_users(session, employees)
        building, floor = seed_building_floor(session)
        cameras = seed_cameras_zones_and_graph(session, building, floor)
        guests = seed_guests(session, employees)
        seed_access_and_tracking_logs(session, employees, guests, cameras)
        seed_analysis_jobs(session, guests, floor)
        session.commit()

        return {
            "backup_path": str(backup_path),
            "departments": len(departments),
            "employees": len(employees),
            "users": 5,
            "guests": len(guests),
            "buildings": 1,
            "floors": 1,
            "cameras": len(cameras),
            "route_nodes": len(session.exec(select(RouteNode)).all()),
            "route_edges": len(session.exec(select(RouteEdge)).all()),
            "access_logs": len(session.exec(select(AccessLog)).all()),
            "tracking_logs": len(session.exec(select(TrackingLog)).all()),
        }


def main() -> None:
    """Точка запуска из командной строки."""

    result = reset_presentation_database()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
