import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 触控手势组合式函数
 * 支持左滑/右滑检测，用于移动端导航
 */
export function useSwipe(elementRef, options = {}) {
  const {
    threshold = 50,       // 最小滑动距离
    onSwipeLeft,
    onSwipeRight,
    onSwipeUp,
    onSwipeDown
  } = options

  const startX = ref(0)
  const startY = ref(0)
  const startTime = ref(0)

  function onTouchStart(e) {
    const touch = e.touches[0]
    startX.value = touch.clientX
    startY.value = touch.clientY
    startTime.value = Date.now()
  }

  function onTouchEnd(e) {
    const touch = e.changedTouches[0]
    const deltaX = touch.clientX - startX.value
    const deltaY = touch.clientY - startY.value
    const elapsed = Date.now() - startTime.value

    // 忽略太慢的滑动（超过 500ms）
    if (elapsed > 500) return

    const absX = Math.abs(deltaX)
    const absY = Math.abs(deltaY)

    if (absX < threshold && absY < threshold) return

    if (absX > absY) {
      // 水平滑动
      if (deltaX > 0 && onSwipeRight) {
        onSwipeRight(deltaX)
      } else if (deltaX < 0 && onSwipeLeft) {
        onSwipeLeft(deltaX)
      }
    } else {
      // 垂直滑动
      if (deltaY > 0 && onSwipeDown) {
        onSwipeDown(deltaY)
      } else if (deltaY < 0 && onSwipeUp) {
        onSwipeUp(deltaY)
      }
    }
  }

  onMounted(() => {
    const el = elementRef.value || document.body
    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchend', onTouchEnd, { passive: true })
  })

  onUnmounted(() => {
    const el = elementRef.value || document.body
    el.removeEventListener('touchstart', onTouchStart)
    el.removeEventListener('touchend', onTouchEnd)
  })

  return { startX, startY }
}
