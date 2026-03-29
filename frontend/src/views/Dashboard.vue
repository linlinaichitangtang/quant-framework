<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="16">
      <el-col :span="6">
        <div class="stat-card">
        <div class="stat-title">总持仓市值</div>
        <div class="stat-value">{{ formatCurrency(overview?.total_market_value) }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
        <div class="stat-title">未实现盈亏</div>
        <div :class="['stat-value', overview?.total_unrealized_profit > 0 ? 'profit-positive' : 'profit-negative']">
          {{ formatCurrency(overview?.total_unrealized_profit) }}
        </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
        <div class="stat-title">当前持仓数</div>
        <div class="stat-value">{{ overview?.total_positions }}</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card">
        <div class="stat-title">待执行信号</div>
        <div class="stat-value">{{ overview?.pending_signals_count }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 当前持仓 -->
    <div class="page-card" style="margin-top: 16px;">
      <h3>当前持仓</h3>
      <el-table :data="positions" v-loading="loading">
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="avg_cost" label="平均成本" width="120" />
        <el-table-column prop="current_price" label="当前价" width="100" />
        <el-table-column prop="market_value" label="市值" width="120" />
        <el-table-column label="盈亏比例" width="120">
          <template #default="{ row }">
          <span :class="row.profit_pct > 0 ? 'profit-positive' : 'profit-negative'">
            {{ row.profit_pct.toFixed(2) }}%
          </span>
          </template>
        </el-table-column>
        <el-table-column label="盈亏金额" width="120">
          <template #default="{ row }">
          <span :class="row.profit_amount > 0 ? 'profit-positive' : 'profit-negative'">
            ¥{{ row.profit_amount?.toFixed(2) }}
          </span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && positions.length === 0" description="暂无持仓" />
    </div>

    <!-- 今日信号 -->
    <div class="page-card">
      <h3>今日交易信号</h3>
      <el-table :data="todaySignals" v-loading="loading">
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="side" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.side === 'BUY' ? 'danger' : 'success'">
              {{ row.side === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="strategy_name" label="策略" width="150" />
        <el-table-column prop="target_price" label="目标价" width="100" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'PENDING'"
              type="primary"
              size="small"
              @click="executeSignal(row.id)"
            >
              执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && todaySignals.length === 0" description="今日暂无信号" />
    </div>

    <!-- 绩效图表 -->
    <div class="page-card">
      <h3>绩效概览</h3>
      <div ref="chartRef" style="width: 100%; height: 300px;"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { getPositions, getSignals, executeSignal as apiExecuteSignal } from '@/api'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

const store = useDashboardStore()
const loading = ref(true)
const positions = ref([])
const todaySignals = ref([])
const chartRef = ref(null)
let chart = null

const overview = computed(() => store.overview)

onMounted(async () => {
  await Promise.all([
    store.fetchOverview(),
    fetchPositions(),
    fetchTodaySignals()
  ])
  loading.value = false
  initChart()
})

function formatCurrency(val) {
  if (val == null) return '¥0.00'
  return `¥${val.toFixed(2)}`
}

async function fetchPositions() {
  try {
    const res = await getPositions()
    positions.value = res || []
  } catch (e) {
    console.error(e)
    positions.value = []
  }
}

async function fetchTodaySignals() {
  try {
    const today = new Date().toISOString().split('T')[0]
    const res = await getSignals({
      page: 1,
      page_size: 20
    })
    todaySignals.value = res.data || []
  } catch (e) {
    console.error(e)
    todaySignals.value = []
  }
}

function getStatusType(status) {
  const map = {
    'PENDING': 'warning',
    'EXECUTED': 'success',
    'FAILED': 'danger',
    'EXPIRED': 'info'
  }
  return map[status] || 'info'
}

function getStatusText(status) {
  const map = {
    'PENDING': '待执行',
    'EXECUTED': '已执行',
    'FAILED': '执行失败',
    'EXPIRED': '已过期'
  }
  return map[status] || status
}

async function executeSignal(signalId) {
  try {
    await apiExecuteSignal(signalId)
    ElMessage.success('执行成功')
    fetchTodaySignals()
    store.fetchOverview()
  } catch (e) {
    ElMessage.error('执行失败')
  }
}

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)

  const option = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['累计收益']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value} %'
      }
    },
    series: [{
      name: '累计收益',
      type: 'line',
      smooth: true,
      data: [0, 1.2, 2.5, 1.8, 3.2, 4.5, 5.8],
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
          { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
        ])
      }
    }]
  }

  chart.setOption(option)
}

// 响应式
window.addEventListener('resize', () => {
  chart?.resize()
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

h3 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
</style>
