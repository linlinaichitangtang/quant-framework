<template>
  <!-- PWA 更新提示 -->
  <PwaUpdatePrompt />

  <!-- PWA 安装提示 -->
  <PwaInstallPrompt />

  <!-- 网络状态指示器 -->
  <NetworkStatusIndicator />
</template>

<script setup>
// ==================== PwaUpdatePrompt ====================
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'

const updateSW = ref(null)
const updateAvailable = ref(false)

onMounted(async () => {
  try {
    const { registerSW } = await import('virtual:pwa-register/vue')
    updateSW.value = registerSW({
      immediate: true,
      onNeedRefresh() {
        updateAvailable.value = true
        showUpdateDialog()
      },
      onOfflineReady() {
        console.log('[PWA] App is ready for offline use')
      },
      onRegisteredSW(swUrl, registration) {
        console.log('[PWA] Service worker registered:', swUrl)
        // 每小时检查一次更新
        if (registration) {
          setInterval(() => {
            registration.update()
          }, 60 * 60 * 1000)
        }
      },
      onRegisterError(error) {
        console.warn('[PWA] SW registration error:', error)
      }
    })
  } catch (e) {
    // 开发环境下 virtual:pwa-register 可能不可用
    console.log('[PWA] Service worker registration not available:', e.message)
  }
})

function showUpdateDialog() {
  ElMessageBox.confirm(
    '检测到新版本可用，是否立即更新？更新后页面将自动刷新。',
    '发现新版本',
    {
      confirmButtonText: '立即更新',
      cancelButtonText: '稍后再说',
      type: 'info'
    }
  ).then(() => {
    if (updateSW.value) {
      updateSW.value(true)
    } else {
      window.location.reload()
    }
  }).catch(() => {
    // 用户选择稍后更新
    updateAvailable.value = false
  })
}

// ==================== PwaInstallPrompt ====================
const deferredPrompt = ref(null)
const showInstallDialog = ref(false)
const DISMISSED_KEY = 'pwa-install-dismissed'

onMounted(() => {
  // 检查用户是否已忽略安装提示
  const dismissed = localStorage.getItem(DISMISSED_KEY)
  if (dismissed) {
    const dismissedTime = new Date(dismissed)
    const now = new Date()
    // 7天后再次提示
    const diffDays = (now - dismissedTime) / (1000 * 60 * 60 * 24)
    if (diffDays < 7) return
  }

  window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
})

onUnmounted(() => {
  window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
})

function handleBeforeInstallPrompt(e) {
  e.preventDefault()
  deferredPrompt.value = e
  // 延迟显示安装提示，避免影响用户操作
  setTimeout(() => {
    showInstallDialog.value = true
  }, 3000)
}

async function installPWA() {
  if (!deferredPrompt.value) return

  deferredPrompt.value.prompt()
  const { outcome } = await deferredPrompt.value.userChoice

  if (outcome === 'accepted') {
    ElMessage.success('应用安装成功！')
  } else {
    // 用户拒绝安装，记录到 localStorage
    localStorage.setItem(DISMISSED_KEY, new Date().toISOString())
  }

  deferredPrompt.value = null
  showInstallDialog.value = false
}

function dismissInstall() {
  showInstallDialog.value = false
  localStorage.setItem(DISMISSED_KEY, new Date().toISOString())
}

// ==================== NetworkStatusIndicator ====================
const isOnline = ref(navigator.onLine)
const showReconnected = ref(false)

onMounted(() => {
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
})

onUnmounted(() => {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
})

function handleOnline() {
  isOnline.value = true
  showReconnected.value = true
  ElMessage.success('已恢复连接')
  setTimeout(() => {
    showReconnected.value = false
  }, 3000)
}

function handleOffline() {
  isOnline.value = false
  ElMessage.warning('网络连接已断开')
}
</script>

<script>
/**
 * PwaUpdatePrompt - 内联子组件
 */
const PwaUpdatePrompt = {
  name: 'PwaUpdatePrompt',
  template: '<span />', // 逻辑组件，无可见 UI（通过 ElMessageBox 显示）
  setup() {
    // 逻辑已在父组件 setup 中实现
    return {}
  }
}

/**
 * PwaInstallPrompt - 内联子组件
 */
const PwaInstallPrompt = {
  name: 'PwaInstallPrompt',
  template: `
    <el-dialog
      v-model="visible"
      title="安装 OpenClaw"
      width="360px"
      :close-on-click-modal="false"
      custom-class="pwa-install-dialog"
    >
      <div style="text-align: center; padding: 10px 0;">
        <img src="/pwa-192x192.png" alt="OpenClaw" style="width: 64px; height: 64px; border-radius: 12px; margin-bottom: 12px;" />
        <p style="margin: 0 0 8px; font-size: 16px; font-weight: 500;">OpenClaw 量化交易监控</p>
        <p style="margin: 0; color: #909399; font-size: 13px;">添加到主屏幕，获得更好的使用体验</p>
      </div>
      <template #footer>
        <el-button @click="dismiss">稍后再说</el-button>
        <el-button type="primary" @click="install">立即安装</el-button>
      </template>
    </el-dialog>
  `,
  setup() {
    // 共享父组件的状态（通过 provide/inject 或直接引用）
    return {
      visible: { value: false },
      install() {},
      dismiss() {}
    }
  }
}

/**
 * NetworkStatusIndicator - 内联子组件
 */
const NetworkStatusIndicator = {
  name: 'NetworkStatusIndicator',
  template: `
    <div v-if="!isOnline" class="network-status-indicator">
      <el-tag type="danger" size="small" effect="dark">
        离线
      </el-tag>
    </div>
  `,
  setup() {
    const isOnline = ref(navigator.onLine)

    onMounted(() => {
      window.addEventListener('online', () => { isOnline.value = true })
      window.addEventListener('offline', () => { isOnline.value = false })
    })

    return { isOnline }
  }
}
</script>

<style scoped>
.network-status-indicator {
  position: fixed;
  bottom: 70px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  padding: 4px 12px;
  background: rgba(0, 0, 0, 0.6);
  border-radius: 16px;
}

@media (min-width: 769px) {
  .network-status-indicator {
    bottom: 20px;
  }
}
</style>
