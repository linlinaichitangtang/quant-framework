<template>
  <div id="app" ref="appRef">
    <el-container>
      <!-- 桌面端：固定侧边栏 -->
      <el-aside v-if="!isMobile" width="200px" class="sidebar">
        <div class="logo">
          <h2>OpenClaw</h2>
          <p>量化交易监控</p>
        </div>
        <el-menu
          :default-active="activeMenu"
          router
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
        >
          <el-menu-item index="/dashboard">
            <el-icon><DataLine /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/selections">
            <el-icon><Grid /></el-icon>
            <span>选股结果</span>
          </el-menu-item>
          <el-menu-item index="/trades">
            <el-icon><List /></el-icon>
            <span>交易记录</span>
          </el-menu-item>
          <el-menu-item index="/logs">
            <el-icon><Document /></el-icon>
            <span>系统日志</span>
          </el-menu-item>
          <el-menu-item index="/modeler">
            <el-icon><VideoCamera /></el-icon>
            <span>3D建模</span>
          </el-menu-item>
          <el-menu-item index="/share">
            <el-icon><Share /></el-icon>
            <span>项目分享</span>
          </el-menu-item>
          <el-menu-item index="/backtest">
            <el-icon><TrendCharts /></el-icon>
            <span>回测可视化</span>
          </el-menu-item>
          <el-menu-item index="/options">
            <el-icon><Coin /></el-icon>
            <span>期权分析</span>
          </el-menu-item>
          <el-menu-item index="/risk">
            <el-icon><Warning /></el-icon>
            <span>风控管理</span>
          </el-menu-item>
          <el-menu-item index="/ai">
            <el-icon><Monitor /></el-icon>
            <span>AI 智能分析</span>
          </el-menu-item>
          <el-menu-item index="/tenant">
            <el-icon><OfficeBuilding /></el-icon>
            <span>租户管理</span>
          </el-menu-item>
          <el-menu-item index="/plugins">
            <el-icon><Grid /></el-icon>
            <span>插件市场</span>
          </el-menu-item>
          <el-menu-item index="/billing">
            <el-icon><Wallet /></el-icon>
            <span>计费管理</span>
          </el-menu-item>
          <el-menu-item index="/algo-trading">
            <el-icon><Operation /></el-icon>
            <span>算法交易</span>
          </el-menu-item>
          <el-menu-item index="/ha-monitor">
            <el-icon><Monitor /></el-icon>
            <span>高可用监控</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 移动端：抽屉式侧边栏 -->
      <el-drawer
        v-model="drawerVisible"
        direction="ltr"
        :size="240"
        :show-close="false"
        :with-header="false"
        class="mobile-drawer"
      >
        <div class="drawer-content">
          <div class="logo">
            <h2>OpenClaw</h2>
            <p>量化交易监控</p>
          </div>
          <el-menu
            :default-active="activeMenu"
            router
            background-color="#304156"
            text-color="#bfcbd9"
            active-text-color="#409EFF"
            @select="onMenuSelect"
          >
            <el-menu-item index="/dashboard">
              <el-icon><DataLine /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/selections">
              <el-icon><Grid /></el-icon>
              <span>选股结果</span>
            </el-menu-item>
            <el-menu-item index="/trades">
              <el-icon><List /></el-icon>
              <span>交易记录</span>
            </el-menu-item>
            <el-menu-item index="/logs">
              <el-icon><Document /></el-icon>
              <span>系统日志</span>
            </el-menu-item>
            <el-menu-item index="/modeler">
              <el-icon><VideoCamera /></el-icon>
              <span>3D建模</span>
            </el-menu-item>
            <el-menu-item index="/share">
              <el-icon><Share /></el-icon>
              <span>项目分享</span>
            </el-menu-item>
            <el-menu-item index="/backtest">
              <el-icon><TrendCharts /></el-icon>
              <span>回测可视化</span>
            </el-menu-item>
            <el-menu-item index="/options">
              <el-icon><Coin /></el-icon>
              <span>期权分析</span>
            </el-menu-item>
            <el-menu-item index="/risk">
              <el-icon><Warning /></el-icon>
              <span>风控管理</span>
            </el-menu-item>
            <el-menu-item index="/ai">
              <el-icon><Monitor /></el-icon>
              <span>AI 智能分析</span>
            </el-menu-item>
            <el-menu-item index="/tenant">
              <el-icon><OfficeBuilding /></el-icon>
              <span>租户管理</span>
            </el-menu-item>
            <el-menu-item index="/plugins">
              <el-icon><Grid /></el-icon>
              <span>插件市场</span>
            </el-menu-item>
            <el-menu-item index="/billing">
              <el-icon><Wallet /></el-icon>
              <span>计费管理</span>
            </el-menu-item>
            <el-menu-item index="/algo-trading">
              <el-icon><Operation /></el-icon>
              <span>算法交易</span>
            </el-menu-item>
            <el-menu-item index="/ha-monitor">
              <el-icon><Monitor /></el-icon>
              <span>高可用监控</span>
            </el-menu-item>
          </el-menu>
        </div>
      </el-drawer>

      <el-container>
        <el-header class="header">
          <div class="header-left">
            <!-- 移动端汉堡菜单按钮 -->
            <el-icon
              v-if="isMobile"
              :size="22"
              class="menu-toggle"
              @click="drawerVisible = true"
            >
              <Menu />
            </el-icon>
            <div class="header-title">{{ pageTitle }}</div>
          </div>
          <div class="header-right">
            <el-badge :value="pendingSignals" :hidden="pendingSignals === 0">
              <el-icon :size="20"><Bell /></el-icon>
            </el-badge>
          </div>
        </el-header>
        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { DataLine, Grid, List, Document, Bell, VideoCamera, Share, TrendCharts, Coin, Warning, Menu, Monitor, OfficeBuilding, Wallet, Operation } from '@element-plus/icons-vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useResponsive } from '@/composables/useResponsive'
import { useSwipe } from '@/composables/useSwipe'

const route = useRoute()
const store = useDashboardStore()
const { isMobile } = useResponsive()

const appRef = ref(null)
const drawerVisible = ref(false)

// 左滑打开菜单，右滑关闭
useSwipe(appRef, {
  threshold: 60,
  onSwipeLeft: () => {
    if (isMobile.value) drawerVisible.value = true
  },
  onSwipeRight: () => {
    if (isMobile.value) drawerVisible.value = false
  }
})

// 路由变化时关闭抽屉
watch(() => route.path, () => {
  drawerVisible.value = false
})

function onMenuSelect() {
  drawerVisible.value = false
}

const activeMenu = computed(() => route.path)
const pendingSignals = computed(() => store.overview?.pending_signals_count || 0)

const pageTitleMap = {
  '/dashboard': '仪表盘',
  '/selections': '选股结果',
  '/trades': '交易记录',
  '/logs': '系统日志',
  '/modeler': '3D建模',
  '/share': '项目分享',
  '/backtest': '回测可视化',
  '/options': '期权分析',
  '/risk': '风控管理',
  '/ai': 'AI 智能分析',
  '/tenant': '租户管理',
  '/plugins': '插件市场',
  '/billing': '计费管理',
  '/algo-trading': '算法交易',
  '/ha-monitor': '高可用监控',
  '/multi-market': '多市场',
  '/community': '社区'
}

const pageTitle = computed(() => pageTitleMap[route.path] || '量化交易监控')
</script>

<style lang="scss">
#app {
  height: 100vh;
  width: 100%;

  .el-container {
    height: 100%;
  }

  .sidebar {
    background-color: #304156;

    .logo {
      height: 60px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      background-color: #263445;
      color: #fff;

      h2 {
        font-size: 18px;
        margin: 0;
        line-height: 1.2;
      }

      p {
        font-size: 12px;
        margin: 0;
        opacity: 0.8;
      }
    }
  }

  .header {
    background-color: #fff;
    border-bottom: 1px solid #e6e6e6;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .header-title {
      font-size: 18px;
      font-weight: 500;
    }

    .menu-toggle {
      cursor: pointer;
      color: #303133;
      padding: 4px;
      border-radius: 4px;

      &:active {
        background-color: #f0f2f5;
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 20px;
    }
  }

  .main-content {
    background-color: #f0f2f5;
    overflow-y: auto;
  }

  .fade-enter-active, .fade-leave-active {
    transition: opacity 0.3s ease;
  }
  .fade-enter-from, .fade-leave-to {
    opacity: 0;
  }
}

/* 移动端抽屉样式 */
.mobile-drawer {
  .el-drawer__body {
    padding: 0;
    background-color: #304156;
  }

  .drawer-content {
    height: 100%;
    display: flex;
    flex-direction: column;

    .logo {
      height: 60px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      background-color: #263445;
      color: #fff;
      flex-shrink: 0;

      h2 {
        font-size: 18px;
        margin: 0;
        line-height: 1.2;
      }

      p {
        font-size: 12px;
        margin: 0;
        opacity: 0.8;
      }
    }

    .el-menu {
      border-right: none;
      flex: 1;
      overflow-y: auto;
    }
  }
}

/* ========== 全局响应式样式 ========== */

/* 手机端 (< 768px) */
@media screen and (max-width: 767px) {
  .el-header {
    padding: 0 12px !important;
    height: 50px !important;

    .header-title {
      font-size: 16px !important;
    }
  }

  .el-main {
    padding: 12px !important;
  }

  /* 页面卡片适配 */
  .page-card {
    padding: 12px !important;
    margin-bottom: 12px !important;
    border-radius: 8px !important;
  }

  .stat-card {
    padding: 12px !important;
    margin-bottom: 8px !important;

    .stat-value {
      font-size: 20px !important;
    }

    .stat-title {
      font-size: 12px !important;
    }
  }

  /* 表格适配：使用卡片列表模式 */
  .el-table {
    font-size: 13px;

    .el-table__header-wrapper {
      display: none; // 隐藏表头，使用卡片模式
    }

    .el-table__body-wrapper {
      .el-table__body {
        .el-table__row {
          display: block;
          margin-bottom: 12px;
          background: #fff;
          border-radius: 8px;
          box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
          padding: 12px;
          border-bottom: none !important;

          td {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0 !important;
            border-bottom: 1px solid #f0f2f5 !important;

            &::before {
              content: attr(data-label);
              font-weight: 500;
              color: #909399;
              font-size: 12px;
              margin-right: 12px;
              flex-shrink: 0;
            }

            .cell {
              text-align: right;
            }
          }

          td:first-child {
            display: none; // 隐藏第一列（通常是序号或ID）
          }
        }
      }
    }
  }

  /* 筛选栏适配 */
  .filter-bar {
    .el-form--inline {
      .el-form-item {
        display: flex;
        margin-right: 0 !important;
        margin-bottom: 8px !important;
        width: 100%;

        .el-form-item__content {
          flex: 1;

          .el-select, .el-input {
            width: 100% !important;
          }
        }
      }
    }
  }

  /* 分页适配 */
  .pagination-wrapper {
    justify-content: center !important;

    .el-pagination {
      .el-pagination__sizes,
      .el-pagination__jump {
        display: none !important;
      }
    }
  }

  /* 对话框适配 */
  .el-dialog {
    width: 92% !important;
    margin: 0 auto !important;
    max-height: 90vh;

    .el-dialog__body {
      padding: 16px !important;
    }

    .el-form-item__label {
      font-size: 13px !important;
    }
  }

  /* 图表容器高度调整 */
  [style*="height: 300px"] {
    height: 220px !important;
  }

  [style*="height: 400px"] {
    height: 280px !important;
  }

  /* 日志项适配 */
  .log-item {
    font-size: 11px !important;
    padding: 6px 8px !important;
    flex-wrap: wrap;

    .log-time {
      font-size: 10px !important;
    }
  }

  /* 登录页适配 */
  .login-card {
    width: 92% !important;
    padding: 24px 16px !important;
    margin: 0 4%;

    .login-header h1 {
      font-size: 24px !important;
    }
  }

  /* 3D 建模页 - 隐藏侧面板 */
  .modeler-sidebar {
    display: none !important;
  }
}

/* 平板竖屏 (768px - 991px) */
@media screen and (min-width: 768px) and (max-width: 991px) {
  .el-aside {
    width: 64px !important;

    .logo p,
    .el-menu-item span {
      display: none !important;
    }

    .logo h2 {
      font-size: 14px !important;
    }

    .el-menu-item {
      justify-content: center;
    }
  }

  .page-card {
    padding: 16px !important;
  }

  .stat-card {
    padding: 16px !important;

    .stat-value {
      font-size: 22px !important;
    }
  }
}

/* 触控优化 */
@media (hover: none) and (pointer: coarse) {
  .el-button {
    min-height: 40px;
    padding: 8px 16px;
  }

  .el-input__inner {
    min-height: 40px;
  }

  .el-select .el-input__inner {
    min-height: 40px;
  }

  .el-menu-item {
    height: 48px;
    line-height: 48px;
  }

  .el-table .el-table__row td {
    min-height: 44px;
  }

  /* 增大可点击区域 */
  .el-badge {
    padding: 8px;
  }

  .el-icon {
    cursor: pointer;
  }
}

/* 安全区域适配（iPhone 刘海屏等） */
@supports (padding: env(safe-area-inset-top)) {
  .el-header {
    padding-top: env(safe-area-inset-top) !important;
  }

  .el-main {
    padding-bottom: env(safe-area-inset-bottom) !important;
  }
}
</style>
