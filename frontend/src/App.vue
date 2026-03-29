<template>
  <div id="app">
    <el-container>
      <el-aside width="200px" class="sidebar">
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
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="header">
          <div class="header-title">{{ pageTitle }}</div>
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
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DataLine, Grid, List, Document, Bell, VideoCamera } from '@element-plus/icons-vue'
import { useDashboardStore } from '@/stores/dashboard'

const route = useRoute()
const store = useDashboardStore()

const activeMenu = computed(() => route.path)
const pendingSignals = computed(() => store.overview?.pending_signals_count || 0)

const pageTitleMap = {
  '/dashboard': '仪表盘',
  '/selections': '选股结果',
  '/trades': '交易记录',
  '/logs': '系统日志',
  '/modeler': '3D建模'
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

    .header-title {
      font-size: 18px;
      font-weight: 500;
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
</style>
