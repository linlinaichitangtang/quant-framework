/**
 * 离线请求队列
 *
 * 拦截因网络错误失败的请求，存储到 IndexedDB，
 * 当网络恢复时自动重放队列中的请求。
 *
 * 数据库: openclaw-offline
 * Store: pending-requests
 * 每条记录: { url, method, data, headers, timestamp, retryCount }
 */

const DB_NAME = 'openclaw-offline'
const DB_VERSION = 1
const STORE_NAME = 'pending-requests'
const MAX_RETRY_COUNT = 3
const BASE_DELAY_MS = 1000 // 基础延迟 1秒

let db = null

/**
 * 打开 IndexedDB 数据库
 */
function openDB() {
  return new Promise((resolve, reject) => {
    if (db) {
      resolve(db)
      return
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = (event) => {
      const database = event.target.result
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true
        })
        store.createIndex('timestamp', 'timestamp', { unique: false })
      }
    }

    request.onsuccess = (event) => {
      db = event.target.result
      resolve(db)
    }

    request.onerror = (event) => {
      console.error('[OfflineQueue] Failed to open IndexedDB:', event.target.error)
      reject(event.target.error)
    }
  })
}

/**
 * 添加请求到队列
 */
async function addToQueue(entry) {
  try {
    const database = await openDB()
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const request = store.add({
        url: entry.url,
        method: entry.method || 'GET',
        data: entry.data || null,
        headers: entry.headers || {},
        timestamp: Date.now(),
        retryCount: 0
      })

      request.onsuccess = () => {
        console.log('[OfflineQueue] Request queued:', entry.method, entry.url)
        resolve(request.result)
      }

      request.onerror = (event) => {
        console.error('[OfflineQueue] Failed to queue request:', event.target.error)
        reject(event.target.error)
      }
    })
  } catch (e) {
    console.error('[OfflineQueue] addToQueue error:', e)
  }
}

/**
 * 获取队列中所有待处理请求（按时间排序）
 */
async function getAllPending() {
  try {
    const database = await openDB()
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const index = store.index('timestamp')
      const request = index.openCursor()

      const entries = []

      request.onsuccess = (event) => {
        const cursor = event.target.result
        if (cursor) {
          entries.push(cursor.value)
          cursor.continue()
        } else {
          resolve(entries)
        }
      }

      request.onerror = (event) => {
        reject(event.target.error)
      }
    })
  } catch (e) {
    console.error('[OfflineQueue] getAllPending error:', e)
    return []
  }
}

/**
 * 更新队列条目
 */
async function updateEntry(id, updates) {
  try {
    const database = await openDB()
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const getReq = store.get(id)

      getReq.onsuccess = () => {
        const entry = getReq.result
        if (!entry) {
          reject(new Error('Entry not found'))
          return
        }
        const updated = { ...entry, ...updates }
        const putReq = store.put(updated)
        putReq.onsuccess = () => resolve(updated)
        putReq.onerror = (event) => reject(event.target.error)
      }

      getReq.onerror = (event) => reject(event.target.error)
    })
  } catch (e) {
    console.error('[OfflineQueue] updateEntry error:', e)
  }
}

/**
 * 删除队列条目
 */
async function removeEntry(id) {
  try {
    const database = await openDB()
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const request = store.delete(id)

      request.onsuccess = () => resolve()
      request.onerror = (event) => reject(event.target.error)
    })
  } catch (e) {
    console.error('[OfflineQueue] removeEntry error:', e)
  }
}

/**
 * 指数退避延迟
 */
function getBackoffDelay(retryCount) {
  return BASE_DELAY_MS * Math.pow(2, retryCount)
}

/**
 * 重放单个请求
 */
async function replayEntry(entry) {
  try {
    const options = {
      method: entry.method,
      headers: {
        'Content-Type': 'application/json',
        ...entry.headers
      }
    }

    if (entry.data && entry.method !== 'GET') {
      options.body = typeof entry.data === 'string' ? entry.data : JSON.stringify(entry.data)
    }

    // 附加认证 token
    const token = localStorage.getItem('access_token')
    if (token) {
      options.headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(entry.url, options)

    if (response.ok) {
      // 请求成功，从队列中移除
      await removeEntry(entry.id)
      console.log('[OfflineQueue] Request replayed successfully:', entry.method, entry.url)
      return true
    } else if (response.status >= 400 && response.status < 500) {
      // 4xx 错误不重试（客户端错误）
      await removeEntry(entry.id)
      console.warn('[OfflineQueue] Client error, removing from queue:', entry.method, entry.url, response.status)
      return true
    } else {
      // 5xx 错误，增加重试次数
      const newRetryCount = entry.retryCount + 1
      if (newRetryCount >= MAX_RETRY_COUNT) {
        await removeEntry(entry.id)
        console.warn('[OfflineQueue] Max retries reached, removing:', entry.method, entry.url)
        return true
      }
      await updateEntry(entry.id, { retryCount: newRetryCount })
      return false
    }
  } catch (e) {
    // 网络错误，增加重试次数
    const newRetryCount = entry.retryCount + 1
    if (newRetryCount >= MAX_RETRY_COUNT) {
      await removeEntry(entry.id)
      console.warn('[OfflineQueue] Max retries reached (network error), removing:', entry.method, entry.url)
      return true
    }
    await updateEntry(entry.id, { retryCount: newRetryCount })
    return false
  }
}

/**
 * 重放所有队列中的请求
 */
async function replayAll() {
  const entries = await getAllPending()
  if (entries.length === 0) return

  console.log(`[OfflineQueue] Replaying ${entries.length} queued requests...`)

  for (const entry of entries) {
    if (entry.retryCount >= MAX_RETRY_COUNT) {
      await removeEntry(entry.id)
      continue
    }

    // 指数退避
    if (entry.retryCount > 0) {
      const delay = getBackoffDelay(entry.retryCount)
      await new Promise(resolve => setTimeout(resolve, delay))
    }

    const success = await replayEntry(entry)
    if (!success) {
      // 请求仍然失败，等待后继续下一个
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  }
}

/**
 * 获取队列大小
 */
export async function getQueueSize() {
  const entries = await getAllPending()
  return entries.length
}

/**
 * 清空队列
 */
export async function clearQueue() {
  try {
    const database = await openDB()
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const request = store.clear()

      request.onsuccess = () => {
        console.log('[OfflineQueue] Queue cleared')
        resolve()
      }
      request.onerror = (event) => reject(event.target.error)
    })
  } catch (e) {
    console.error('[OfflineQueue] clearQueue error:', e)
  }
}

/**
 * 初始化离线请求队列
 *
 * 拦截 fetch 请求，当网络错误时将请求存入 IndexedDB。
 * 当网络恢复时自动重放队列。
 */
export function initOfflineQueue() {
  console.log('[OfflineQueue] Initializing...')

  // 保存原始 fetch
  const originalFetch = window.fetch

  // 替换全局 fetch
  window.fetch = async function (...args) {
    try {
      const response = await originalFetch.apply(this, args)
      return response
    } catch (error) {
      // 判断是否为网络错误（非 4xx/5xx）
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        // 网络不可用，将请求加入队列
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || ''
        const options = args[1] || {}

        // 只对 API 请求进行排队（忽略静态资源等）
        if (url.includes('/api/')) {
          console.log('[OfflineQueue] Network error, queuing request:', options.method || 'GET', url)
          await addToQueue({
            url,
            method: options.method || 'GET',
            data: options.body || null,
            headers: options.headers || {}
          })
        }
      }
      throw error
    }
  }

  // 监听网络恢复事件
  window.addEventListener('online', () => {
    console.log('[OfflineQueue] Network restored, replaying queued requests...')
    // 延迟 1 秒后重放，确保网络稳定
    setTimeout(() => {
      replayAll()
    }, 1000)
  })

  // 页面加载时检查是否有待处理请求
  if (navigator.onLine) {
    setTimeout(() => {
      replayAll()
    }, 2000)
  }

  console.log('[OfflineQueue] Initialized successfully')
}
