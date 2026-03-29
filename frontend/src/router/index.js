import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/Dashboard.vue')
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
    },
    {
      path: '/tracking',
      name: 'tracking',
      component: () => import('../views/Tracking.vue')
    },
    { 
      path: '/departments', 
      name: 'departments', 
      component: () => import('../views/Departments.vue') 
    }
  ]
})

export default router