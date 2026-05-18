export const ROLE_LABELS = Object.freeze({
  super_admin: 'Super Admin',
  technician: 'Техник',
  hr: 'HR',
  analyst: 'Аналитик',
  checkpoint_operator: 'Оператор КПП',
  manager_analyst: 'Аналитик (устар.)',
  tech_hr: 'Техник + HR (устар.)',
})

export const ROLE_HOME_ROUTES = Object.freeze({
  super_admin: '/',
  technician: '/tracking',
  hr: '/employees',
  analyst: '/',
  checkpoint_operator: '/route',
  manager_analyst: '/',
  tech_hr: '/tracking',
})

export const ASSIGNABLE_ROLE_OPTIONS = Object.freeze([
  { value: 'super_admin', label: ROLE_LABELS.super_admin },
  { value: 'technician', label: ROLE_LABELS.technician },
  { value: 'hr', label: ROLE_LABELS.hr },
  { value: 'analyst', label: ROLE_LABELS.analyst },
  { value: 'checkpoint_operator', label: ROLE_LABELS.checkpoint_operator },
])

export const PERMISSIONS = Object.freeze({
  DASHBOARD_READ: 'dashboard:read',
  USERS_MANAGE: 'users:manage',
  CAMERAS_READ: 'cameras:read',
  CAMERAS_WRITE: 'cameras:write',
  FLOOR_MAP_VIEW: 'floor_map:view',
  ROUTE_GRAPH_WRITE: 'route_graph:write',
  CAMERA_PLACEMENT_WRITE: 'camera_placement:write',
  CAMERA_ZONES_WRITE: 'camera_zones:write',
  EMPLOYEES_READ: 'employees:read',
  EMPLOYEES_WRITE: 'employees:write',
  DEPARTMENTS_READ: 'departments:read',
  DEPARTMENTS_WRITE: 'departments:write',
  GUESTS_READ: 'guests:read',
  GUESTS_WRITE: 'guests:write',
  GUEST_PASSES_ISSUE: 'guest_passes:issue',
  GUEST_PASSES_CLOSE: 'guest_passes:close',
  CHECKPOINT_READ: 'checkpoint:read',
  ANALYTICS_READ: 'analytics:read',
  GUEST_ROUTES_READ: 'guest_routes:read',
  GUEST_ROUTES_ANALYZE_VIDEO: 'guest_routes:analyze_video',
  VIDEO_ANALYSIS_READ: 'video_analysis:read',
  VIDEO_ANALYSIS_WRITE: 'video_analysis:write',
})
