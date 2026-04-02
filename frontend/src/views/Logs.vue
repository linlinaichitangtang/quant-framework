<template>
  <div class="logs-page">
    <div class="page-card">
      <div class="filter-bar">
        <el-form :inline="true" :model="filters">
          <el-form-item label="日志级别">
            <el-select v-model="filters.level" placeholder="全部" @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="DEBUG" value="DEBUG" />
              <el-option label="INFO" value="INFO" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="ERROR" value="ERROR" />
            </el-select>
          </el-form-item>
          <el-form-item label="模块">
            <el-select v-model="filters.module" placeholder="全部" @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="数据采集" value="data_collection" />
              <el-option label="选股" value="selection" />
              <el-option label="信号生成" value="signal" />
              <el-option label="FMZ执行" value="fmz" />
              <el-option label="系统" value="system" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="filters.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchData">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
            <el-button type="danger" @click="clearLogs" :loading="clearing">清空日志</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="logs-container">
        <div v-for="log in list" :key="log.id" class="log-item">
          <span class="log-time">{{ formatTime(log.created_at) }}</span>
          <el-tag :type="getLevelType(log.level)" size="small" class="log-level">{{ log.level }}</el-tag>
          <span class="log-module">[{{ log.module }}]</span>
          <span class="log-message">{{ log.message }}</span>
        </div>

        <el-empty v-if="!loading && list.length === 0" description="暂无日志" />
      </div>

      <div class="pagination-wrapper" v-if="total > pagination.pageSize">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>

      <div class="auto-refresh">
        <el-switch v-model="autoRefresh" />
        <span>自动刷新 (每 10 秒)</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getLogs, clearLogs } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const clearing = ref(false)
const autoRefresh = ref(true)

const filters = ref({
  level: '',
  module: '',
  dateRange: []
})

const pagination = ref({
  page: 1,
  pageSize: 50
})

let refreshTimer = null

onMounted(() => {
  fetchData()
  if (autoRefresh.value) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})

function startAutoRefresh() {
  refreshTimer = setInterval(() => {
    fetchData(false)
  }, 10000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// 监听自动刷新切换
autoRefresh.value = autoRefresh
if (autoRefresh.value) {
  startAutoRefresh()
} else {
  stopAutoRefresh()
}

async function fetchData(showLoading = true) {
  if (showLoading) {
    loading.value = true
  }
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    }
    if (filters.value.level) {
      params.level = filters.value.level
    }
    if (filters.value.module) {
      params.module = filters.value.module
    }
    if (filters.value.dateRange && filters.value.dateRange.length === 2) {
      params.start_date = filters.value.dateRange[0]
      params.end_date = filters.value.dateRange[1]
    }

    const res = await getLogs(params)
    list.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    console.error('Failed to fetch logs:', error)
    if (showLoading) {
      ElMessage.error('获取日志失败')
    }
  } finally {
    if (showLoading) {
      loading.value = false
    }
  }
}

function handleFilterChange() {
  pagination.value.page = 1
}

function resetFilters() {
  filters.value = {
    level: '',
    module: '',
    dateRange: []
  }
  pagination.value.page = 1
  fetchData()
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm('此操作将清空所有日志, 是否继续?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    clearing.value = true
    try {
      await clearLogs()
      list.value = []
      total.value = 0
      ElMessage.success('日志已清空')
    } catch (e) {
      ElMessage.error('清空日志失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      clearing.value = false
    }
  } catch {
    // 用户取消
  }
}

function getLevelType(level) {
  const map = {
    'DEBUG': 'info',
    'INFO': 'success',
    'WARNING': 'warning',
    'ERROR': 'danger'
  }
  return map[level] || 'info'
}

function formatTime(timeStr) {
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.logs-page {
  padding: 0;
}

.filter-bar {
  margin-bottom: 16px;
}

.logs-container {
  max-height: calc(100vh - 350px);
  overflow-y: auto;
  background: #fafafa;
  border-radius: 4px;
}

.log-item {
  padding: 8px 12px;
  border-bottom: 1px solid #eaeaea;
  font-family: monospace;
  font-size: 13px;
  line-height: 1.5;

  &:hover {
    background: #f0f0f0;
  }
}

.log-time {
  color: #909399;
  margin-right: 8px;
}

.log-level {
  margin-right: 8px;
}

.log-module {
  color: #409EFF;
  margin-right: 8px;
}

.log-message {
  color: #303133;
  word-break: break-all;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.auto-refresh {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
}

@media screen and (max-width: 767px) {
  .logs-page {
    .logs-container {
      max-height: calc(100vh - 380px);
    }
    .auto-refresh {
      font-size: 13px;
    }
  }
}
</style>
