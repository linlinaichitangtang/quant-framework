import { ref, onMounted } from 'vue'

/**
 * Web Push 推送通知组合式函数
 * 利用 Notification API + Service Worker 实现浏览器推送
 */
export function useNotification() {
  const supported = ref('Notification' in window)
  const permission = ref('Notification' in window ? Notification.permission : 'denied')
  const granted = ref(false)

  async function requestPermission() {
    if (!supported.value) return false
    try {
      const result = await Notification.requestPermission()
      permission.value = result
      granted.value = result === 'granted'
      return granted.value
    } catch {
      return false
    }
  }

  function notify(title, options = {}) {
    if (!granted.value) return null
    const {
      body = '',
      icon = '/pwa-192x192.png',
      badge = '/pwa-72x72.png',
      tag = 'openclaw',
      data = {},
      onClick = null
    } = options

    const notification = new Notification(title, {
      body,
      icon,
      badge,
      tag,
      data,
      vibrate: [200, 100, 200]
    })

    if (onClick) {
      notification.onclick = (event) => {
        event.preventDefault()
        window.focus()
        onClick(event)
        notification.close()
      }
    }

    // 5秒后自动关闭
    setTimeout(() => notification.close(), 5000)
    return notification
  }

  /**
   * 通过 Service Worker 发送推送（离线时也能收到）
   */
  async function pushViaSW(title, options = {}) {
    if (!('serviceWorker' in navigator)) return
    try {
      const registration = await navigator.serviceWorker.ready
      await registration.showNotification(title, {
        body: options.body || '',
        icon: '/pwa-192x192.png',
        badge: '/pwa-72x72.png',
        tag: options.tag || 'openclaw',
        data: options.data || {},
        vibrate: [200, 100, 200],
        actions: options.actions || []
      })
    } catch (e) {
      console.warn('SW push failed, falling back to Notification:', e)
      notify(title, options)
    }
  }

  onMounted(() => {
    if (supported.value) {
      permission.value = Notification.permission
      granted.value = Notification.permission === 'granted'
    }
  })

  return {
    supported,
    permission,
    granted,
    requestPermission,
    notify,
    pushViaSW
  }
}
