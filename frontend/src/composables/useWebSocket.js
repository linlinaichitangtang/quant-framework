/**
 * WebSocket 实时推送 Composable
 *
 * 用法：
 * import { useWebSocket } from '@/composables/useWebSocket'
 * const { connected, subscribe, unsubscribe } = useWebSocket()
 */

import { ref, onMounted, onUnmounted } from 'vue'

const connected = ref(false)
const clientId = ref(null)
let ws = null
let reconnectTimer = null
let heartbeatTimer = null
const listeners = new Map() // { event: [callbacks] }

function getWsUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/ws`
}

function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) return

  const url = getWsUrl()
  ws = new WebSocket(url)

  ws.onopen = () => {
    connected.value = true
    console.log('[WebSocket] 已连接')
    startHeartbeat()
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      const eventCallbacks = listeners.get(msg.event)
      if (eventCallbacks) {
        eventCallbacks.forEach(cb => cb(msg.data))
      }
      // 频道级别的监听
      const channelCallbacks = listeners.get(`channel:${msg.channel}`)
      if (channelCallbacks) {
        channelCallbacks.forEach(cb => cb(msg))
      }
    } catch (e) {
      console.error('[WebSocket] 消息解析失败:', e)
    }
  }

  ws.onclose = () => {
    connected.value = false
    clientId.value = null
    stopHeartbeat()
    console.log('[WebSocket] 已断开，3秒后重连...')
    reconnectTimer = setTimeout(connect, 3000)
  }

  ws.onerror = (error) => {
    console.error('[WebSocket] 错误:', error)
  }
}

function disconnect() {
  clearTimeout(reconnectTimer)
  stopHeartbeat()
  if (ws) {
    ws.close()
    ws = null
  }
  connected.value = false
  clientId.value = null
}

function send(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(typeof data === 'string' ? data : JSON.stringify(data))
  }
}

function subscribe(channel) {
  send({ action: 'subscribe', channel })
}

function unsubscribe(channel) {
  send({ action: 'unsubscribe', channel })
}

function on(event, callback) {
  if (!listeners.has(event)) {
    listeners.set(event, [])
  }
  listeners.get(event).push(callback)
}

function off(event, callback) {
  const cbs = listeners.get(event)
  if (cbs) {
    const index = cbs.indexOf(callback)
    if (index > -1) cbs.splice(index, 1)
  }
}

function startHeartbeat() {
  heartbeatTimer = setInterval(() => {
    send({ action: 'ping' })
  }, 30000)
}

function stopHeartbeat() {
  clearInterval(heartbeatTimer)
}

export function useWebSocket() {
  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    clientId,
    subscribe,
    unsubscribe,
    send,
    on,
    off,
    connect,
    disconnect,
  }
}
