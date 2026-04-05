import { createRouter, createWebHistory } from 'vue-router'
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
    meta: { roles: ['super_admin'] },
  },
  {
    path: '/employees',
    name: 'employees',
    component: () => import('../views/Employees.vue'),
    meta: { roles: ['super_admin', 'checkpoint_operator'] },
  },
  {
    path: '/cameras',
    name: 'cameras',
    component: () => import('../views/Cameras.vue'),
    meta: { roles: ['super_admin', 'checkpoint_operator'] },
  },
  {
    path: '/route',
    name: 'route',
    component: () => import('../views/Route.vue'),
    meta: { roles: ['super_admin', 'checkpoint_operator'] },
  },
  {
    path: '/tracking',
    name: 'tracking',
    component: () => import('../views/Tracking.vue'),
    meta: { roles: ['super_admin', 'checkpoint_operator'] },
  },
  {
    path: '/video-analysis',
    name: 'video-analysis',
    component: () => import('../views/VideoAnalysis.vue'),
    meta: { roles: ['super_admin', 'checkpoint_operator'] },
  },
  {
    path: '/departments',
    name: 'departments',
    component: () => import('../views/Departments.vue'),
    meta: { roles: ['super_admin'] },
  },
  {
    path: '/guests',
    name: 'guests',
    component: () => import('../views/Guests.vue'),
    meta: { roles: ['super_admin', 'checkpoint_operator'] },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('../views/Users.vue'),
    meta: { roles: ['super_admin'] },
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

  const allowedRoles = to.meta.roles || []
  if (allowedRoles.length > 0 && !auth.hasAnyRole(...allowedRoles)) {
    return auth.getDefaultRoute()
  }

  return true
})

export default router
