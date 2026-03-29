import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue')
  },
  {
    path: '/selections',
    name: 'Selections',
    component: () => import('@/views/Selections.vue')
  },
  {
    path: '/trades',
    name: 'Trades',
    component: () => import('@/views/Trades.vue')
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/Logs.vue')
  },
  {
    path: '/modeler',
    name: 'Modeler',
    component: () => import('@/views/ModelerView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
