import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: Dashboard
    },
    {
      path: '/employees',
      name: 'employees',
      component: () => import('../views/Employees.vue')
    },
    {
      path: '/cameras',
      name: 'cameras',
      component: () => import('../views/Cameras.vue')
    },
    {
      path: '/route',
      name: 'route',
      component: () => import('../views/Route.vue')
    }
  ]
})

export default router