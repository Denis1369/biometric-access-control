"""Ролевая модель и список permissions backend-а.

В системе есть несколько реальных ролей пользователей. Super Admin может всё;
техник отвечает за здания, этажи, планы, камеры, зоны видимости и граф
маршрутов; HR ведёт сотрудников, отделы и должности; аналитик смотрит отчёты,
журналы и маршруты; оператор КПП оформляет гостей, работает с проходной и может
строить маршрут гостя.

Endpoint-ы не должны проверять роли напрямую там, где важнее конкретное
действие. Поэтому действия описаны строковыми permissions, а роли получают
наборы этих permissions. Такой подход проще расширять: можно дать новой роли
часть функций без переписывания всех router-ов.
"""

from app.models.user import UserRole


DASHBOARD_READ = "dashboard:read"
USERS_MANAGE = "users:manage"
ROLES_MANAGE = "roles:manage"

BUILDINGS_READ = "buildings:read"
BUILDINGS_WRITE = "buildings:write"
FLOORS_READ = "floors:read"
FLOORS_WRITE = "floors:write"
FLOOR_PLANS_READ = "floor_plans:read"
FLOOR_PLANS_WRITE = "floor_plans:write"
FLOOR_MAP_VIEW = "floor_map:view"

CAMERAS_READ = "cameras:read"
CAMERAS_WRITE = "cameras:write"
CAMERA_SNAPSHOT_READ = "camera_snapshot:read"
CAMERA_PLACEMENT_READ = "camera_placement:read"
CAMERA_PLACEMENT_WRITE = "camera_placement:write"
CAMERA_ZONES_READ = "camera_zones:read"
CAMERA_ZONES_WRITE = "camera_zones:write"

ROUTE_GRAPH_READ = "route_graph:read"
ROUTE_GRAPH_WRITE = "route_graph:write"

EMPLOYEES_READ = "employees:read"
EMPLOYEES_LOOKUP = "employees:lookup"
EMPLOYEES_WRITE = "employees:write"
DEPARTMENTS_READ = "departments:read"
DEPARTMENTS_WRITE = "departments:write"
JOB_POSITIONS_READ = "job_positions:read"
JOB_POSITIONS_WRITE = "job_positions:write"

GUESTS_READ = "guests:read"
GUESTS_WRITE = "guests:write"
GUEST_PASSES_ISSUE = "guest_passes:issue"
GUEST_PASSES_CLOSE = "guest_passes:close"

CHECKPOINT_READ = "checkpoint:read"
CHECKPOINT_OPERATE = "checkpoint:operate"

ANALYTICS_READ = "analytics:read"
ACCESS_LOGS_READ = "access_logs:read"
ACCESS_LOGS_READ_RECENT = "access_logs:read_recent"
TRACKING_LOGS_READ = "tracking_logs:read"
GUEST_ROUTES_READ = "guest_routes:read"
GUEST_ROUTES_ANALYZE_VIDEO = "guest_routes:analyze_video"
VIDEO_ANALYSIS_READ = "video_analysis:read"
VIDEO_ANALYSIS_WRITE = "video_analysis:write"
REPORTS_EXPORT = "reports:export"


ALL_PERMISSIONS = frozenset(
    {
        DASHBOARD_READ,
        USERS_MANAGE,
        ROLES_MANAGE,
        BUILDINGS_READ,
        BUILDINGS_WRITE,
        FLOORS_READ,
        FLOORS_WRITE,
        FLOOR_PLANS_READ,
        FLOOR_PLANS_WRITE,
        FLOOR_MAP_VIEW,
        CAMERAS_READ,
        CAMERAS_WRITE,
        CAMERA_SNAPSHOT_READ,
        CAMERA_PLACEMENT_READ,
        CAMERA_PLACEMENT_WRITE,
        CAMERA_ZONES_READ,
        CAMERA_ZONES_WRITE,
        ROUTE_GRAPH_READ,
        ROUTE_GRAPH_WRITE,
        EMPLOYEES_READ,
        EMPLOYEES_LOOKUP,
        EMPLOYEES_WRITE,
        DEPARTMENTS_READ,
        DEPARTMENTS_WRITE,
        JOB_POSITIONS_READ,
        JOB_POSITIONS_WRITE,
        GUESTS_READ,
        GUESTS_WRITE,
        GUEST_PASSES_ISSUE,
        GUEST_PASSES_CLOSE,
        CHECKPOINT_READ,
        CHECKPOINT_OPERATE,
        ANALYTICS_READ,
        ACCESS_LOGS_READ,
        ACCESS_LOGS_READ_RECENT,
        TRACKING_LOGS_READ,
        GUEST_ROUTES_READ,
        GUEST_ROUTES_ANALYZE_VIDEO,
        VIDEO_ANALYSIS_READ,
        VIDEO_ANALYSIS_WRITE,
        REPORTS_EXPORT,
    }
)

TECHNICIAN_PERMISSIONS = frozenset(
    {
        BUILDINGS_READ,
        BUILDINGS_WRITE,
        FLOORS_READ,
        FLOORS_WRITE,
        FLOOR_PLANS_READ,
        FLOOR_PLANS_WRITE,
        FLOOR_MAP_VIEW,
        CAMERAS_READ,
        CAMERAS_WRITE,
        CAMERA_SNAPSHOT_READ,
        CAMERA_PLACEMENT_READ,
        CAMERA_PLACEMENT_WRITE,
        CAMERA_ZONES_READ,
        CAMERA_ZONES_WRITE,
        ROUTE_GRAPH_READ,
        ROUTE_GRAPH_WRITE,
    }
)

HR_PERMISSIONS = frozenset(
    {
        EMPLOYEES_READ,
        EMPLOYEES_LOOKUP,
        EMPLOYEES_WRITE,
        DEPARTMENTS_READ,
        DEPARTMENTS_WRITE,
        JOB_POSITIONS_READ,
        JOB_POSITIONS_WRITE,
    }
)

ANALYST_PERMISSIONS = frozenset(
    {
        DASHBOARD_READ,
        ANALYTICS_READ,
        ACCESS_LOGS_READ,
        TRACKING_LOGS_READ,
        GUEST_ROUTES_READ,
        VIDEO_ANALYSIS_READ,
        VIDEO_ANALYSIS_WRITE,
        REPORTS_EXPORT,
        BUILDINGS_READ,
        FLOORS_READ,
        FLOOR_PLANS_READ,
        CAMERA_PLACEMENT_READ,
        CAMERA_ZONES_READ,
        ROUTE_GRAPH_READ,
        EMPLOYEES_READ,
        EMPLOYEES_LOOKUP,
        DEPARTMENTS_READ,
        JOB_POSITIONS_READ,
        GUESTS_READ,
    }
)

CHECKPOINT_OPERATOR_PERMISSIONS = frozenset(
    {
        CHECKPOINT_READ,
        CHECKPOINT_OPERATE,
        GUESTS_READ,
        GUESTS_WRITE,
        GUEST_PASSES_ISSUE,
        GUEST_PASSES_CLOSE,
        ACCESS_LOGS_READ_RECENT,
        TRACKING_LOGS_READ,
        GUEST_ROUTES_READ,
        GUEST_ROUTES_ANALYZE_VIDEO,
        FLOOR_MAP_VIEW,
        BUILDINGS_READ,
        FLOORS_READ,
        FLOOR_PLANS_READ,
        CAMERA_PLACEMENT_READ,
        CAMERA_ZONES_READ,
        ROUTE_GRAPH_READ,
        CAMERA_SNAPSHOT_READ,
        EMPLOYEES_LOOKUP,
    }
)

ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: ALL_PERMISSIONS,
    UserRole.TECHNICIAN: TECHNICIAN_PERMISSIONS,
    UserRole.HR: HR_PERMISSIONS,
    UserRole.ANALYST: ANALYST_PERMISSIONS,
    UserRole.CHECKPOINT_OPERATOR: CHECKPOINT_OPERATOR_PERMISSIONS,
    # Старые роли оставлены как мост для уже существующих учётных записей:
    # если в базе остался прежний enum, пользователь не потеряет доступ до
    # ручного переназначения роли администратором.
    UserRole.MANAGER_ANALYST: ANALYST_PERMISSIONS,
    UserRole.TECH_HR: TECHNICIAN_PERMISSIONS | HR_PERMISSIONS,
}


def get_permissions_for_role(role: UserRole) -> frozenset[str]:
    """Вернуть набор действий, разрешённых роли.

    Параметры:
        role: Роль пользователя из таблицы users.

    Возвращает:
        frozenset permissions. Для неизвестной роли возвращается пустой набор,
        чтобы доступ закрывался безопасно, а не открывался по умолчанию.
    """

    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role: UserRole, permission: str) -> bool:
    """Проверить одно конкретное разрешение у роли.

    Helper удобен в местах, где нужно не подключать FastAPI dependency, а просто
    принять решение внутри сервиса или при сборке интерфейсного payload-а.

    Параметры:
        role: Роль пользователя.
        permission: Строковый код действия, например `camera_zones:write`.

    Возвращает:
        True, если роль содержит указанное разрешение.
    """

    return permission in get_permissions_for_role(role)
