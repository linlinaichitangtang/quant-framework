import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 15000
})

// 是否正在刷新 Token
let isRefreshing = false
// 等待 Token 刷新的请求队列
let failedQueue = []

function processQueue(error, token = null) {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// 请求拦截器：自动附加 Token
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器：处理 401 和 Token 刷新
service.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    const originalRequest = error.config
    const status = error.response?.status

    // 401 未认证：尝试刷新 Token
    if (status === 401 && !originalRequest._retry) {
      // 登录接口不需要刷新
      if (originalRequest.url.includes('/auth/login') ||
          originalRequest.url.includes('/auth/register') ||
          originalRequest.url.includes('/auth/refresh')) {
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // 正在刷新中，加入队列等待
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return service(originalRequest)
        }).catch(err => {
          return Promise.reject(err)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        // 无 refresh_token，跳转登录页
        handleLogout()
        return Promise.reject(error)
      }

      return new Promise((resolve, reject) => {
        axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
          .then(res => {
            const { access_token, refresh_token } = res.data
            localStorage.setItem('access_token', access_token)
            localStorage.setItem('refresh_token', refresh_token)
            originalRequest.headers.Authorization = `Bearer ${access_token}`
            processQueue(null, access_token)
            resolve(service(originalRequest))
          })
          .catch(err => {
            processQueue(err, null)
            handleLogout()
            reject(err)
          })
          .finally(() => {
            isRefreshing = false
          })
      })
    }

    // 其他错误
    const message = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

function handleLogout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  ElMessage.warning('登录已过期，请重新登录')
  router.push('/login')
}

export default service
