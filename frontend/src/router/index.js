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
  },
  {
    path: '/tenant',
    name: 'TenantManage',
    component: () => import('@/views/TenantManageView.vue'),
    meta: { title: '租户管理' }
  },
  {
    path: '/plugins',
    name: 'PluginMarket',
    component: () => import('@/views/PluginMarketView.vue'),
    meta: { title: '插件市场' }
  },
  {
    path: '/billing',
    name: 'Billing',
    component: () => import('@/views/BillingView.vue'),
    meta: { title: '计费管理' }
  },
  {
    path: '/ai',
    name: 'AIAssistant',
    component: () => import('@/views/AIAssistantView.vue'),
    meta: { title: 'AI 智能分析' }
  },
  {
    path: '/algo-trading',
    name: 'AlgoTrading',
    component: () => import('@/views/AlgoTradingView.vue'),
    meta: { title: '算法交易' }
  },
  {
    path: '/ha-monitor',
    name: 'HAMonitor',
    component: () => import('@/views/HAMonitorView.vue'),
    meta: { title: '高可用监控' }
  },
  {
    path: '/multi-market',
    name: 'MultiMarket',
    component: () => import('@/views/MultiMarketView.vue'),
    meta: { title: '多市场' }
  },
  {
    path: '/community',
    name: 'Community',
    component: () => import('@/views/CommunityView.vue'),
    meta: { title: '社区' }
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
