from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from html import escape
import random

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models.buildings import Building
from app.models.cameras import Camera
from app.models.departments import Department
from app.models.employees import Employee
from app.models.floors import Floor
from app.models.guests import Guest
from app.models.job_positions import JobPosition
from app.models.logs import AccessLog, TrackingLog
from app.models.user import User, UserRole

LOOKBACK_DAYS = 10
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
SEED_RANDOM = 20260410


@dataclass(frozen=True)
class DepartmentSpec:
    name: str
    work_start: time
    work_end: time
    lunch_start: time
    lunch_end: time
    positions: tuple[str, ...]
    employee_count: int


@dataclass(frozen=True)
class RoomSpec:
    label: str
    x: int
    y: int
    width: int
    height: int
    fill: str


@dataclass(frozen=True)
class CameraSpec:
    key: str
    name: str
    ip_address: str
    direction: str
    plan_x: float
    plan_y: float
    is_active: bool = False


@dataclass(frozen=True)
class FloorSpec:
    key: str
    name: str
    floor_number: int
    rooms: tuple[RoomSpec, ...]
    cameras: tuple[CameraSpec, ...]


@dataclass(frozen=True)
class BuildingSpec:
    name: str
    address: str
    floors: tuple[FloorSpec, ...]


@dataclass(frozen=True)
class GuestSpec:
    last_name: str
    first_name: str
    middle_name: str | None
    host_department: str
    site_key: str
    visit_offsets: tuple[int, ...]
    arrival_window: tuple[int, int]
    duration_minutes: tuple[int, int]
    valid_for_days: int
    is_active: bool
    keep_open_today: bool = False


@dataclass
class EmployeeContext:
    employee: Employee
    department: Department
    site_key: str


@dataclass
class GuestContext:
    guest: Guest
    host: Employee
    site_key: str
    spec: GuestSpec


DEPARTMENT_SPECS: tuple[DepartmentSpec, ...] = (
    DepartmentSpec(
        name="Безопасность",
        work_start=time(8, 0),
        work_end=time(17, 0),
        lunch_start=time(12, 30),
        lunch_end=time(13, 0),
        positions=("Оператор КПП", "Старший смены", "Инспектор безопасности"),
        employee_count=4,
    ),
    DepartmentSpec(
        name="IT-инфраструктура",
        work_start=time(9, 0),
        work_end=time(18, 0),
        lunch_start=time(13, 0),
        lunch_end=time(14, 0),
        positions=("Системный администратор", "DevOps инженер", "Сетевой инженер", "Специалист техподдержки"),
        employee_count=5,
    ),
    DepartmentSpec(
        name="Финансы",
        work_start=time(9, 30),
        work_end=time(18, 30),
        lunch_start=time(13, 0),
        lunch_end=time(14, 0),
        positions=("Финансовый аналитик", "Бухгалтер", "Экономист", "Специалист по закупкам"),
        employee_count=4,
    ),
    DepartmentSpec(
        name="HR и подбор",
        work_start=time(9, 0),
        work_end=time(18, 0),
        lunch_start=time(13, 0),
        lunch_end=time(14, 0),
        positions=("HR-менеджер", "Рекрутер", "Специалист по адаптации", "Кадровый администратор"),
        employee_count=4,
    ),
    DepartmentSpec(
        name="Логистика",
        work_start=time(8, 30),
        work_end=time(17, 30),
        lunch_start=time(12, 30),
        lunch_end=time(13, 15),
        positions=("Кладовщик", "Координатор поставок", "Специалист по приемке", "Диспетчер склада"),
        employee_count=5,
    ),
    DepartmentSpec(
        name="Администрация",
        work_start=time(9, 0),
        work_end=time(18, 0),
        lunch_start=time(13, 0),
        lunch_end=time(14, 0),
        positions=("Офис-менеджер", "Ассистент руководителя", "Менеджер проектов", "Юрист"),
        employee_count=4,
    ),
)

BUILDING_SPECS: tuple[BuildingSpec, ...] = (
    BuildingSpec(
        name="Главный офис",
        address="г. Екатеринбург, ул. Малышева, 51",
        floors=(
            FloorSpec(
                key="hq_l1",
                name="Входная группа",
                floor_number=1,
                rooms=(
                    RoomSpec("Ресепшен", 80, 220, 250, 190, "#dbeafe"),
                    RoomSpec("Турникеты", 370, 220, 260, 190, "#dcfce7"),
                    RoomSpec("Ожидание посетителей", 680, 220, 300, 190, "#fef3c7"),
                    RoomSpec("Переговорная Quick Meet", 80, 470, 280, 160, "#fee2e2"),
                    RoomSpec("Служба охраны", 430, 470, 250, 160, "#ede9fe"),
                ),
                cameras=(
                    CameraSpec("hq_in", "Турникет A вход", "rtsp://10.10.1.11:554/Streaming/Channels/101", "in", 0.24, 0.56),
                    CameraSpec("hq_out", "Турникет A выход", "rtsp://10.10.1.12:554/Streaming/Channels/101", "out", 0.31, 0.56),
                    CameraSpec("hq_lobby", "Ресепшен обзор", "rtsp://10.10.1.13:554/Streaming/Channels/101", "internal", 0.14, 0.43),
                ),
            ),
            FloorSpec(
                key="hq_l2",
                name="Открытый офис",
                floor_number=2,
                rooms=(
                    RoomSpec("Open space север", 80, 180, 430, 220, "#dcfce7"),
                    RoomSpec("Серверная", 560, 180, 210, 220, "#dbeafe"),
                    RoomSpec("Help Desk", 820, 180, 260, 220, "#fee2e2"),
                    RoomSpec("Кухня", 80, 460, 240, 150, "#fef3c7"),
                    RoomSpec("Переговорная Orion", 370, 460, 300, 150, "#ede9fe"),
                ),
                cameras=(
                    CameraSpec("hq_open_north", "Open space север", "rtsp://10.10.2.11:554/Streaming/Channels/101", "internal", 0.23, 0.39),
                    CameraSpec("hq_server", "Серверная зона", "rtsp://10.10.2.12:554/Streaming/Channels/101", "internal", 0.56, 0.40),
                ),
            ),
            FloorSpec(
                key="hq_l3",
                name="Управление и переговорные",
                floor_number=3,
                rooms=(
                    RoomSpec("Дирекция", 80, 180, 280, 220, "#dbeafe"),
                    RoomSpec("Финансовый блок", 410, 180, 310, 220, "#dcfce7"),
                    RoomSpec("HR блок", 770, 180, 280, 220, "#fee2e2"),
                    RoomSpec("Переговорная Восток", 160, 470, 320, 150, "#fef3c7"),
                    RoomSpec("Лифт холл", 560, 470, 220, 150, "#ede9fe"),
                ),
                cameras=(
                    CameraSpec("hq_meeting", "Переговорная Восток", "rtsp://10.10.3.11:554/Streaming/Channels/101", "internal", 0.33, 0.69),
                    CameraSpec("hq_lift", "Лифт холл 3 этаж", "rtsp://10.10.3.12:554/Streaming/Channels/101", "internal", 0.58, 0.68),
                ),
            ),
        ),
    ),
    BuildingSpec(
        name="Логистический центр",
        address="г. Екатеринбург, ул. Монтажников, 26",
        floors=(
            FloorSpec(
                key="wh_l1",
                name="КПП и приемка",
                floor_number=1,
                rooms=(
                    RoomSpec("КПП", 90, 220, 230, 180, "#dbeafe"),
                    RoomSpec("Приемка", 370, 180, 320, 260, "#dcfce7"),
                    RoomSpec("Зона досмотра", 740, 180, 250, 260, "#fee2e2"),
                    RoomSpec("Комната смены", 180, 480, 260, 140, "#fef3c7"),
                    RoomSpec("Окно выдачи", 510, 480, 250, 140, "#ede9fe"),
                ),
                cameras=(
                    CameraSpec("wh_in", "КПП склад вход", "rtsp://10.20.1.11:554/Streaming/Channels/101", "in", 0.16, 0.50),
                    CameraSpec("wh_out", "КПП склад выход", "rtsp://10.20.1.12:554/Streaming/Channels/101", "out", 0.24, 0.50),
                    CameraSpec("wh_receipt", "Зона приемки", "rtsp://10.20.1.13:554/Streaming/Channels/101", "internal", 0.48, 0.39),
                ),
            ),
            FloorSpec(
                key="wh_l2",
                name="Складские ряды",
                floor_number=2,
                rooms=(
                    RoomSpec("Стеллажный ряд A", 90, 180, 250, 460, "#dcfce7"),
                    RoomSpec("Стеллажный ряд B", 390, 180, 250, 460, "#dbeafe"),
                    RoomSpec("Стеллажный ряд C", 690, 180, 250, 460, "#fee2e2"),
                    RoomSpec("Погрузочная рампа", 990, 180, 130, 460, "#fef3c7"),
                ),
                cameras=(
                    CameraSpec("wh_rack_b", "Стеллажный коридор B", "rtsp://10.20.2.11:554/Streaming/Channels/101", "internal", 0.49, 0.51),
                    CameraSpec("wh_dock", "Погрузочная рампа", "rtsp://10.20.2.12:554/Streaming/Channels/101", "internal", 0.89, 0.52),
                ),
            ),
        ),
    ),
)

GUEST_SPECS: tuple[GuestSpec, ...] = (
    GuestSpec("Ильин", "Максим", "Олегович", "IT-инфраструктура", "hq", (7, 3, 0), (9 * 60 + 40, 11 * 60 + 20), (55, 135), 4, True),
    GuestSpec("Климова", "Дарья", "Сергеевна", "HR и подбор", "hq", (4,), (11 * 60, 12 * 60 + 20), (45, 85), -1, False),
    GuestSpec("Соловьёва", "Елена", "Игоревна", "Финансы", "hq", (8, 2), (10 * 60 + 30, 12 * 60 + 10), (70, 150), -2, False),
    GuestSpec("Кудрявцев", "Павел", "Викторович", "Администрация", "hq", (6, 1), (14 * 60, 15 * 60 + 30), (30, 95), 1, True),
    GuestSpec("Волков", "Сергей", "Андреевич", "Логистика", "warehouse", (9, 5, 2, 0), (8 * 60 + 50, 10 * 60 + 10), (35, 90), 2, True, keep_open_today=True),
    GuestSpec("Николаева", "Марина", "Петровна", "Финансы", "hq", (5,), (15 * 60, 16 * 60), (60, 120), -3, False),
)

MALE_FIRST_NAMES = (
    "Алексей", "Андрей", "Владимир", "Дмитрий", "Егор", "Иван", "Кирилл", "Максим", "Никита",
    "Олег", "Павел", "Роман", "Сергей", "Тимофей", "Фёдор", "Юрий",
)
FEMALE_FIRST_NAMES = (
    "Алина", "Анна", "Валерия", "Дарья", "Екатерина", "Ирина", "Ксения", "Марина",
    "Наталья", "Ольга", "Полина", "Светлана", "Татьяна", "Юлия", "Яна",
)
MALE_LAST_NAMES = (
    "Агапов", "Белов", "Воронов", "Грачёв", "Данилов", "Елисеев", "Зайцев", "Киреев",
    "Лобанов", "Медведев", "Нестеров", "Орлов", "Панкратов", "Рябов", "Савельев", "Титов",
)
FEMALE_LAST_NAMES = (
    "Агапова", "Белова", "Воронова", "Грачёва", "Данилова", "Елисеева", "Зайцева", "Киреева",
    "Лобанова", "Медведева", "Нестерова", "Орлова", "Панкратова", "Рябова", "Савельева", "Титова",
)
MALE_MIDDLE_NAMES = (
    "Алексеевич", "Андреевич", "Викторович", "Владимирович", "Дмитриевич",
    "Евгеньевич", "Игоревич", "Михайлович", "Олегович", "Сергеевич",
)
FEMALE_MIDDLE_NAMES = (
    "Алексеевна", "Андреевна", "Викторовна", "Владимировна", "Дмитриевна",
    "Евгеньевна", "Игоревна", "Михайловна", "Олеговна", "Сергеевна",
)


def ensure_demo_data(session: Session) -> bool:
    had_business_data = _has_business_data(session)
    ensure_default_super_admin(session)
    if had_business_data:
        return False

    seed_demo_data(session)
    return True


def ensure_default_super_admin(session: Session) -> User:
    user = session.exec(
        select(User).where(User.username == DEFAULT_ADMIN_USERNAME)
    ).first()
    changed = False

    if user is None:
        user = User(
            username=DEFAULT_ADMIN_USERNAME,
            password_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        session.add(user)
        changed = True
    else:
        if not _password_matches(DEFAULT_ADMIN_PASSWORD, user.password_hash):
            user.password_hash = get_password_hash(DEFAULT_ADMIN_PASSWORD)
            changed = True
        if user.role != UserRole.SUPER_ADMIN:
            user.role = UserRole.SUPER_ADMIN
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            session.add(user)

    if changed:
        session.commit()
        session.refresh(user)
    elif user.id is None:
        session.flush()

    return user


def seed_demo_data(session: Session) -> None:
    rng = random.Random(SEED_RANDOM)

    departments = _seed_departments(session)
    _seed_job_positions(session, departments)
    buildings, floors, cameras = _seed_locations(session)
    employees = _seed_employees(session, departments, rng)
    guests = _seed_guests(session, employees, rng)
    _seed_recent_activity(session, employees, guests, cameras, rng)
    session.commit()

    print(
        "Демоданные загружены:"
        f" отделов={len(departments)},"
        f" зданий={len(buildings)},"
        f" этажей={len(floors)},"
        f" камер={len(cameras)},"
        f" сотрудников={len(employees)},"
        f" гостей={len(guests)}"
    )


def _has_business_data(session: Session) -> bool:
    models = (
        Department,
        JobPosition,
        Building,
        Floor,
        Camera,
        Employee,
        Guest,
        AccessLog,
        TrackingLog,
    )
    return any(session.exec(select(model.id).limit(1)).first() is not None for model in models)


def _password_matches(plain_password: str, password_hash: str) -> bool:
    try:
        return verify_password(plain_password, password_hash)
    except Exception:
        return False


def _seed_departments(session: Session) -> dict[str, Department]:
    departments: dict[str, Department] = {}
    for spec in DEPARTMENT_SPECS:
        department = Department(
            name=spec.name,
            work_start=spec.work_start,
            work_end=spec.work_end,
            lunch_start=spec.lunch_start,
            lunch_end=spec.lunch_end,
        )
        session.add(department)
        session.flush()
        departments[spec.name] = department
    return departments


def _seed_job_positions(session: Session, departments: dict[str, Department]) -> None:
    for spec in DEPARTMENT_SPECS:
        department = departments[spec.name]
        for index, position_name in enumerate(spec.positions, start=1):
            session.add(
                JobPosition(
                    name=position_name,
                    is_active=True,
                    sort_order=index * 10,
                    department_id=department.id,
                )
            )
    session.flush()


def _seed_locations(session: Session) -> tuple[dict[str, Building], dict[str, Floor], dict[str, Camera]]:
    buildings: dict[str, Building] = {}
    floors: dict[str, Floor] = {}
    cameras: dict[str, Camera] = {}

    for building_index, building_spec in enumerate(BUILDING_SPECS, start=1):
        building = Building(
            name=building_spec.name,
            address=building_spec.address,
            created_at=datetime.now() - timedelta(days=120 - building_index * 5),
        )
        session.add(building)
        session.flush()
        buildings[building_spec.name] = building

        for floor_spec in building_spec.floors:
            plan_bytes = _build_floor_plan_svg(
                building_spec.name,
                floor_spec.name,
                floor_spec.floor_number,
                floor_spec.rooms,
            )
            floor = Floor(
                building_id=building.id,
                name=floor_spec.name,
                floor_number=floor_spec.floor_number,
                plan_mime_type="image/svg+xml",
                plan_image=plan_bytes,
                created_at=datetime.now() - timedelta(days=110 - floor_spec.floor_number * 3),
                updated_at=datetime.now() - timedelta(days=5),
            )
            session.add(floor)
            session.flush()
            floors[floor_spec.key] = floor

            for camera_spec in floor_spec.cameras:
                camera = Camera(
                    name=camera_spec.name,
                    ip_address=camera_spec.ip_address,
                    # Demo cameras stay inactive until a real stream source is configured.
                    is_active=camera_spec.is_active,
                    building_id=building.id,
                    floor_id=floor.id,
                    plan_x=camera_spec.plan_x,
                    plan_y=camera_spec.plan_y,
                    direction=camera_spec.direction,
                )
                session.add(camera)
                session.flush()
                cameras[camera_spec.key] = camera

    return buildings, floors, cameras


def _seed_employees(
    session: Session,
    departments: dict[str, Department],
    rng: random.Random,
) -> list[EmployeeContext]:
    employee_contexts: list[EmployeeContext] = []
    used_names: set[tuple[str, str, str | None]] = set()

    for spec in DEPARTMENT_SPECS:
        department = departments[spec.name]
        for index in range(spec.employee_count):
            last_name, first_name, middle_name = _build_unique_name(rng, used_names)
            position = spec.positions[index % len(spec.positions)]
            employee = Employee(
                last_name=last_name,
                first_name=first_name,
                middle_name=middle_name,
                position=position,
                department_id=department.id,
                is_active=True,
            )
            session.add(employee)
            session.flush()
            employee_contexts.append(
                EmployeeContext(
                    employee=employee,
                    department=department,
                    site_key=_resolve_site_key(spec.name, index),
                )
            )

    return employee_contexts


def _seed_guests(
    session: Session,
    employees: list[EmployeeContext],
    rng: random.Random,
) -> list[GuestContext]:
    today = date.today()
    host_pool: dict[str, list[EmployeeContext]] = {}
    for context in employees:
        host_pool.setdefault(context.department.name, []).append(context)

    used_names = {
        (ctx.employee.last_name, ctx.employee.first_name, ctx.employee.middle_name)
        for ctx in employees
    }
    guest_contexts: list[GuestContext] = []

    for spec in GUEST_SPECS:
        host_context = rng.choice(host_pool[spec.host_department])
        valid_until_date = today + timedelta(days=spec.valid_for_days)
        valid_until = datetime.combine(valid_until_date, time(20, 0))

        guest_name = (spec.last_name, spec.first_name, spec.middle_name)
        if guest_name in used_names:
            raise ValueError("Гостевые ФИО должны отличаться от сотрудников")
        used_names.add(guest_name)

        guest = Guest(
            last_name=spec.last_name,
            first_name=spec.first_name,
            middle_name=spec.middle_name,
            employee_id=host_context.employee.id,
            valid_until=valid_until,
            is_active=spec.is_active,
        )
        session.add(guest)
        session.flush()

        guest_contexts.append(
            GuestContext(
                guest=guest,
                host=host_context.employee,
                site_key=spec.site_key,
                spec=spec,
            )
        )

    return guest_contexts


def _seed_recent_activity(
    session: Session,
    employees: list[EmployeeContext],
    guests: list[GuestContext],
    cameras: dict[str, Camera],
    rng: random.Random,
) -> None:
    now = datetime.now().replace(second=0, microsecond=0)
    today = now.date()
    site_cameras = {
        "hq": {
            "in": cameras["hq_in"],
            "out": cameras["hq_out"],
            "internal": [cameras["hq_lobby"], cameras["hq_open_north"], cameras["hq_server"], cameras["hq_meeting"], cameras["hq_lift"]],
        },
        "warehouse": {
            "in": cameras["wh_in"],
            "out": cameras["wh_out"],
            "internal": [cameras["wh_receipt"], cameras["wh_rack_b"], cameras["wh_dock"]],
        },
    }

    access_logs: list[AccessLog] = []
    tracking_logs: list[TrackingLog] = []

    for offset in range(LOOKBACK_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_limit = now if day == today else datetime.combine(day, time(23, 59))
        is_weekend = day.weekday() >= 5

        for context in employees:
            attendance_probability = _attendance_probability(context.department.name, is_weekend)
            if rng.random() > attendance_probability:
                continue

            entry_camera = site_cameras[context.site_key]["in"]
            exit_camera = site_cameras[context.site_key]["out"]
            internal_cameras = site_cameras[context.site_key]["internal"]

            arrival = _build_arrival_time(day, context.department.work_start, rng)
            if arrival >= day_limit:
                continue

            if rng.random() < 0.09:
                denied_time = max(arrival - timedelta(minutes=rng.randint(2, 9)), datetime.combine(day, time(6, 0)))
                if denied_time < day_limit:
                    access_logs.append(
                        AccessLog(
                            camera_id=entry_camera.id,
                            timestamp=denied_time,
                            status="denied",
                            confidence=round(rng.uniform(0.53, 0.76), 3),
                        )
                    )

            access_logs.append(
                AccessLog(
                    employee_id=context.employee.id,
                    camera_id=entry_camera.id,
                    timestamp=arrival,
                    status="granted",
                    confidence=round(rng.uniform(0.91, 0.99), 3),
                )
            )

            departure = _build_departure_time(day, context.department.work_end, rng)
            if departure <= arrival:
                departure = arrival + timedelta(hours=8)

            if rng.random() < 0.22:
                lunch_exit = arrival + timedelta(hours=4, minutes=rng.randint(-10, 35))
                lunch_return = lunch_exit + timedelta(minutes=rng.randint(28, 68))
                if lunch_exit < day_limit:
                    access_logs.append(
                        AccessLog(
                            employee_id=context.employee.id,
                            camera_id=exit_camera.id,
                            timestamp=lunch_exit,
                            status="granted",
                            confidence=round(rng.uniform(0.88, 0.98), 3),
                        )
                    )
                if lunch_return < day_limit:
                    access_logs.append(
                        AccessLog(
                            employee_id=context.employee.id,
                            camera_id=entry_camera.id,
                            timestamp=lunch_return,
                            status="granted",
                            confidence=round(rng.uniform(0.89, 0.99), 3),
                        )
                    )

            visible_until = min(departure, day_limit)
            for track_time in _build_tracking_times(arrival, visible_until, rng):
                camera = rng.choice(internal_cameras)
                tracking_logs.append(
                    TrackingLog(
                        employee_id=context.employee.id,
                        camera_id=camera.id,
                        timestamp=track_time,
                        confidence=round(rng.uniform(0.82, 0.97), 3),
                    )
                )

            if departure < day_limit:
                access_logs.append(
                    AccessLog(
                        employee_id=context.employee.id,
                        camera_id=exit_camera.id,
                        timestamp=departure,
                        status="granted",
                        confidence=round(rng.uniform(0.89, 0.99), 3),
                    )
                )

        for guest_context in guests:
            if offset not in guest_context.spec.visit_offsets:
                continue

            entry_camera = site_cameras[guest_context.site_key]["in"]
            exit_camera = site_cameras[guest_context.site_key]["out"]
            internal_cameras = site_cameras[guest_context.site_key]["internal"]

            arrival = _build_guest_arrival(day, guest_context.spec.arrival_window, rng)
            if arrival >= day_limit:
                continue

            if rng.random() < 0.15:
                access_logs.append(
                    AccessLog(
                        camera_id=entry_camera.id,
                        timestamp=max(arrival - timedelta(minutes=3), datetime.combine(day, time(7, 0))),
                        status="denied",
                        confidence=round(rng.uniform(0.57, 0.78), 3),
                    )
                )

            access_logs.append(
                AccessLog(
                    guest_id=guest_context.guest.id,
                    camera_id=entry_camera.id,
                    timestamp=arrival,
                    status="granted",
                    confidence=round(rng.uniform(0.86, 0.96), 3),
                )
            )

            visit_end = arrival + timedelta(
                minutes=rng.randint(*guest_context.spec.duration_minutes)
            )
            visible_until = min(visit_end, day_limit)

            for track_time in _build_tracking_times(arrival, visible_until, rng, max_points=2):
                tracking_logs.append(
                    TrackingLog(
                        guest_id=guest_context.guest.id,
                        camera_id=rng.choice(internal_cameras).id,
                        timestamp=track_time,
                        confidence=round(rng.uniform(0.79, 0.94), 3),
                    )
                )

            keep_open = guest_context.spec.keep_open_today and day == today
            if not keep_open and visit_end < day_limit:
                access_logs.append(
                    AccessLog(
                        guest_id=guest_context.guest.id,
                        camera_id=exit_camera.id,
                        timestamp=visit_end,
                        status="granted",
                        confidence=round(rng.uniform(0.84, 0.96), 3),
                    )
                )

    access_logs.sort(key=lambda log: log.timestamp)
    tracking_logs.sort(key=lambda log: log.timestamp)
    session.add_all(access_logs)
    session.add_all(tracking_logs)


def _attendance_probability(department_name: str, is_weekend: bool) -> float:
    if department_name == "Безопасность":
        return 0.82 if is_weekend else 0.95
    if department_name == "Логистика":
        return 0.32 if is_weekend else 0.9
    if is_weekend:
        return 0.05
    return 0.88


def _resolve_site_key(department_name: str, index: int) -> str:
    if department_name == "Логистика":
        return "warehouse"
    if department_name == "Безопасность":
        return "hq" if index % 2 == 0 else "warehouse"
    return "hq"


def _build_unique_name(
    rng: random.Random,
    used_names: set[tuple[str, str, str | None]],
) -> tuple[str, str, str]:
    while True:
        is_female = rng.random() < 0.45
        if is_female:
            full_name = (
                rng.choice(FEMALE_LAST_NAMES),
                rng.choice(FEMALE_FIRST_NAMES),
                rng.choice(FEMALE_MIDDLE_NAMES),
            )
        else:
            full_name = (
                rng.choice(MALE_LAST_NAMES),
                rng.choice(MALE_FIRST_NAMES),
                rng.choice(MALE_MIDDLE_NAMES),
            )

        if full_name not in used_names:
            used_names.add(full_name)
            return full_name


def _build_arrival_time(day: date, work_start: time, rng: random.Random) -> datetime:
    base = datetime.combine(day, work_start)
    late_roll = rng.random()
    if late_roll < 0.17:
        offset_minutes = rng.randint(6, 37)
    elif late_roll < 0.62:
        offset_minutes = rng.randint(-6, 7)
    else:
        offset_minutes = -rng.randint(8, 28)
    return base + timedelta(minutes=offset_minutes)


def _build_departure_time(day: date, work_end: time, rng: random.Random) -> datetime:
    base = datetime.combine(day, work_end)
    early_roll = rng.random()
    if early_roll < 0.12:
        offset_minutes = -rng.randint(18, 65)
    elif early_roll < 0.72:
        offset_minutes = rng.randint(-8, 18)
    else:
        offset_minutes = rng.randint(20, 55)
    return base + timedelta(minutes=offset_minutes)


def _build_guest_arrival(day: date, arrival_window: tuple[int, int], rng: random.Random) -> datetime:
    start_minutes, end_minutes = arrival_window
    selected_minutes = rng.randint(start_minutes, end_minutes)
    return datetime.combine(day, time.min) + timedelta(minutes=selected_minutes)


def _build_tracking_times(
    start_time: datetime,
    end_time: datetime,
    rng: random.Random,
    max_points: int = 3,
) -> list[datetime]:
    if end_time <= start_time + timedelta(minutes=15):
        return []

    points = rng.randint(1, max_points)
    window_minutes = int((end_time - start_time).total_seconds() // 60)
    timestamps = []
    for _ in range(points):
        minute_offset = rng.randint(10, max(10, window_minutes - 5))
        timestamps.append(start_time + timedelta(minutes=minute_offset))
    return sorted(set(timestamps))


def _build_floor_plan_svg(
    building_name: str,
    floor_name: str,
    floor_number: int,
    rooms: tuple[RoomSpec, ...],
) -> bytes:
    room_markup = "\n".join(
        (
            f'<g>'
            f'<rect x="{room.x}" y="{room.y}" width="{room.width}" height="{room.height}" rx="22" fill="{room.fill}" stroke="#94a3b8" stroke-width="3" />'
            f'<text x="{room.x + 18}" y="{room.y + 36}" font-size="24" font-weight="700" fill="#0f172a">{escape(room.label)}</text>'
            f'</g>'
        )
        for room in rooms
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#f8fafc" />
      <stop offset="100%" stop-color="#e2e8f0" />
    </linearGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#bg)" />
  <rect x="34" y="34" width="1132" height="732" rx="28" fill="#ffffff" stroke="#cbd5e1" stroke-width="4" />
  <text x="88" y="108" font-size="38" font-weight="700" fill="#0f172a">{escape(building_name)}</text>
  <text x="88" y="148" font-size="24" fill="#475569">Этаж {floor_number}: {escape(floor_name)}</text>
  <path d="M90 190 H1110" stroke="#cbd5e1" stroke-width="4" stroke-linecap="round" />
  <rect x="1030" y="70" width="95" height="34" rx="10" fill="#eff6ff" />
  <text x="1062" y="93" font-size="18" font-weight="700" fill="#1d4ed8">N</text>
  <path d="M1080 138 V94" stroke="#1d4ed8" stroke-width="6" stroke-linecap="round" />
  <path d="M1080 82 L1068 100 L1092 100 Z" fill="#1d4ed8" />
  {room_markup}
  <path d="M80 440 H1080" stroke="#e2e8f0" stroke-width="18" stroke-linecap="round" />
  <path d="M720 180 V650" stroke="#e2e8f0" stroke-width="18" stroke-linecap="round" />
</svg>"""
    return svg.encode("utf-8")
