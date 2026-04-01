import { ref, computed, onMounted, onUnmounted } from 'vue'

// 响应式断点（与 Element Plus 一致）
export const BREAKPOINTS = {
  xs: 0,      // < 768px  手机
  sm: 768,    // >= 768px 平板竖屏
  md: 992,    // >= 992px 平板横屏
  lg: 1200,   // >= 1200px 桌面
  xl: 1920    // >= 1920px 大屏
}

// 全局单例，避免多个组件重复监听
let instance = null

export function useResponsive() {
  if (instance) return instance

  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1200)

  const isMobile = computed(() => width.value < BREAKPOINTS.sm)
  const isTablet = computed(() => width.value >= BREAKPOINTS.sm && width.value < BREAKPOINTS.lg)
  const isDesktop = computed(() => width.value >= BREAKPOINTS.lg)

  // Element Plus el-col 的 span 映射
  const colSpan = computed(() => ({
    stat: isMobile.value ? 12 : 6,     // 统计卡片：手机2列，桌面4列
    filter: isMobile.value ? 24 : undefined, // 筛选表单：手机全宽
    table: isMobile.value ? 'mini' : 'default'
  }))

  function onResize() {
    width.value = window.innerWidth
  }

  onMounted(() => {
    window.addEventListener('resize', onResize, { passive: true })
  })

  onUnmounted(() => {
    window.removeEventListener('resize', onResize)
    instance = null
  })

  instance = {
    width,
    isMobile,
    isTablet,
    isDesktop,
    colSpan,
    BREAKPOINTS
  }

  return instance
}
