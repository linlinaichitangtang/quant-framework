import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true }
  },
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
  },
  {
    path: '/share',
    name: 'Share',
    component: () => import('@/views/ShareView.vue')
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/BacktestView.vue')
  },
  {
    path: '/options',
    name: 'Options',
    component: () => import('@/views/OptionsView.vue')
  },
  {
    path: '/risk',
    name: 'Risk',
    component: () => import('@/views/RiskView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录用户跳转到登录页
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  if (!to.meta.public && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
