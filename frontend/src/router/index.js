import { createRouter, createWebHistory } from 'vue-router'
import { PERMISSIONS } from '../constants/roles'
import { useAuth } from '../services/auth'

const auth = useAuth()

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { permissions: [PERMISSIONS.DASHBOARD_READ] },
  },
  {
    path: '/employees',
    name: 'employees',
    component: () => import('../views/Employees.vue'),
    meta: { permissions: [PERMISSIONS.EMPLOYEES_READ] },
  },
  {
    path: '/cameras',
    name: 'cameras',
    component: () => import('../views/Cameras.vue'),
    meta: { permissions: [PERMISSIONS.CAMERAS_READ] },
  },
  {
    path: '/route',
    name: 'route',
    component: () => import('../views/Route.vue'),
    meta: { permissions: [PERMISSIONS.CHECKPOINT_READ] },
  },
  {
    path: '/tracking',
    name: 'tracking',
    component: () => import('../views/Tracking.vue'),
    meta: { permissions: [PERMISSIONS.FLOOR_MAP_VIEW] },
  },
  {
    path: '/video-analysis',
    name: 'video-analysis',
    component: () => import('../views/VideoAnalysis.vue'),
    meta: { permissions: [PERMISSIONS.VIDEO_ANALYSIS_READ] },
  },
  {
    path: '/departments',
    name: 'departments',
    component: () => import('../views/Departments.vue'),
    meta: { permissions: [PERMISSIONS.DEPARTMENTS_READ] },
  },
  {
    path: '/guests',
    name: 'guests',
    component: () => import('../views/Guests.vue'),
    meta: { permissions: [PERMISSIONS.GUESTS_READ] },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('../views/Users.vue'),
    meta: { permissions: [PERMISSIONS.USERS_MANAGE] },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: () => auth.getDefaultRoute(),
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async (to) => {
  if (!auth.state.initialized) {
    await auth.initialize()
  }

  if (to.meta.public) {
    if (to.path === '/login' && auth.isAuthenticated()) {
      return auth.getDefaultRoute()
    }
    return true
  }

  if (!auth.state.token) {
    return {
      path: '/login',
      query: { redirect: to.fullPath },
    }
  }

  if (!auth.state.user) {
    await auth.initialize(true)
    if (!auth.state.user) {
      return {
        path: '/login',
        query: { redirect: to.fullPath },
      }
    }
  }

  const requiredPermissions = to.meta.permissions || []
  if (requiredPermissions.length > 0 && !requiredPermissions.every((permission) => auth.hasPermission(permission))) {
    return auth.getDefaultRoute()
  }

  return true
})

export default router
