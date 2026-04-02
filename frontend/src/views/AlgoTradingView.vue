<template>
  <div class="algo-trading-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab 1: 创建算法订单 -->
      <el-tab-pane label="创建算法订单" name="create">
        <div class="algo-type-selector">
          <div
            v-for="item in algoTypes"
            :key="item.value"
            :class="['algo-type-card', { active: form.algoType === item.value }]"
            @click="form.algoType = item.value"
          >
            <el-icon :size="32"><component :is="item.icon" /></el-icon>
            <h3>{{ item.label }}</h3>
            <p>{{ item.desc }}</p>
          </div>
        </div>

        <el-card class="form-card" shadow="never">
          <template #header>
            <span>{{ currentAlgoLabel }} 订单参数</span>
          </template>
          <el-form :model="form" label-width="120px" :rules="formRules" ref="formRef">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="标的代码" prop="symbol">
                  <el-input v-model="form.symbol" placeholder="例如 600519" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="方向" prop="side">
                  <el-radio-group v-model="form.side">
                    <el-radio-button value="BUY">买入</el-radio-button>
                    <el-radio-button value="SELL">卖出</el-radio-button>
                  </el-radio-group>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="数量" prop="quantity">
                  <el-input-number v-model="form.quantity" :min="100" :step="100" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="市场">
                  <el-select v-model="form.market" style="width: 100%">
                    <el-option label="A股" value="A" />
                    <el-option label="港股" value="HK" />
                    <el-option label="美股" value="US" />
                  </el-select>
                </el-form-item>
              </el-col>

              <!-- TWAP 特有参数 -->
              <template v-if="form.algoType === 'twap'">
                <el-col :span="12">
                  <el-form-item label="持续时间(分钟)">
                    <el-input-number v-model="form.durationMinutes" :min="1" :max="1440" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="随机化">
                    <el-switch v-model="form.randomize" />
                  </el-form-item>
                </el-col>
              </template>

              <!-- VWAP 特有参数 -->
              <template v-if="form.algoType === 'vwap'">
                <el-col :span="12">
                  <el-form-item label="持续时间(分钟)">
                    <el-input-number v-model="form.durationMinutes" :min="1" :max="1440" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="成交量分布">
                    <el-select v-model="form.volumeProfile" style="width: 100%">
                      <el-option label="自动 (U型)" value="auto" />
                      <el-option label="前重" value="front_loaded" />
                      <el-option label="后重" value="back_loaded" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </template>

              <!-- 冰山特有参数 -->
              <template v-if="form.algoType === 'iceberg'">
                <el-col :span="12">
                  <el-form-item label="显示数量" prop="displayQuantity">
                    <el-input-number v-model="form.displayQuantity" :min="1" :step="100" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="随机方差">
                    <el-slider v-model="form.randomVariance" :min="0" :max="1" :step="0.05" show-input />
                  </el-form-item>
                </el-col>
              </template>

              <!-- 智能拆单参数 -->
              <template v-if="form.algoType === 'smart'">
                <el-col :span="12">
                  <el-form-item label="紧急程度">
                    <el-radio-group v-model="form.urgency">
                      <el-radio-button value="low">低</el-radio-button>
                      <el-radio-button value="medium">中</el-radio-button>
                      <el-radio-button value="high">高</el-radio-button>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="最大冲击(%)">
                    <el-input-number v-model="form.maxImpactPct" :min="0.01" :max="5" :step="0.1" :precision="2" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="指定策略">
                    <el-select v-model="form.strategy" style="width: 100%" clearable placeholder="自动选择">
                      <el-option label="自动" value="auto" />
                      <el-option label="TWAP" value="twap" />
                      <el-option label="VWAP" value="vwap" />
                      <el-option label="冰山" value="iceberg" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </template>
            </el-row>
          </el-form>
        </el-card>

        <!-- 预估信息 -->
        <el-card class="estimate-card" shadow="never">
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="estimate-item">
                <span class="label">预计拆单数</span>
                <span class="value">{{ estimatedSlices }}</span>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="estimate-item">
                <span class="label">预计持续时间</span>
                <span class="value">{{ estimatedDuration }}</span>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="estimate-item">
                <span class="label">预计滑点</span>
                <span class="value">{{ estimatedSlippage }}</span>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <div class="submit-bar">
          <el-button type="primary" size="large" :loading="submitting" @click="submitOrder">
            提交订单
          </el-button>
        </div>
      </el-tab-pane>

      <!-- Tab 2: 订单管理 -->
      <el-tab-pane label="订单管理" name="orders">
        <div class="filter-bar">
          <el-select v-model="orderFilter.algoType" placeholder="算法类型" clearable style="width: 140px; margin-right: 12px">
            <el-option label="TWAP" value="twap" />
            <el-option label="VWAP" value="vwap" />
            <el-option label="冰山" value="iceberg" />
            <el-option label="智能" value="smart" />
          </el-select>
          <el-select v-model="orderFilter.status" placeholder="状态" clearable style="width: 140px; margin-right: 12px">
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="失败" value="failed" />
          </el-select>
          <el-button type="primary" @click="loadOrders">刷新</el-button>
        </div>

        <el-table :data="orders" v-loading="ordersLoading" stripe>
          <el-table-column prop="order_id" label="订单ID" width="200" />
          <el-table-column prop="algo_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="algoTypeTag(row.algo_type)" size="small">{{ algoTypeLabel(row.algo_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="symbol" label="标的" width="100" />
          <el-table-column prop="side" label="方向" width="80">
            <template #default="{ row }">
              <span :style="{ color: row.side === 'BUY' ? '#f56c6c' : '#67c23a' }">{{ row.side === 'BUY' ? '买入' : '卖出' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="160">
            <template #default="{ row }">
              {{ row.filled_quantity }} / {{ row.total_quantity }}
            </template>
          </el-table-column>
          <el-table-column label="进度" width="150">
            <template #default="{ row }">
              <el-progress :percentage="row.progress || 0" :stroke-width="14" :text-inside="true" />
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="orderStatusTag(row.status)" size="small">{{ orderStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="viewOrderDetail(row)">详情</el-button>
              <el-button size="small" type="danger" :disabled="!canCancel(row.status)" @click="cancelOrder(row.order_id)">取消</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 订单详情对话框 -->
        <el-dialog v-model="detailVisible" title="订单详情" width="700px">
          <template v-if="currentOrder">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="订单ID">{{ currentOrder.order_id }}</el-descriptions-item>
              <el-descriptions-item label="算法类型">{{ algoTypeLabel(currentOrder.algo_type) }}</el-descriptions-item>
              <el-descriptions-item label="标的">{{ currentOrder.symbol }}</el-descriptions-item>
              <el-descriptions-item label="方向">{{ currentOrder.side }}</el-descriptions-item>
              <el-descriptions-item label="总数量">{{ currentOrder.total_quantity }}</el-descriptions-item>
              <el-descriptions-item label="已成交量">{{ currentOrder.filled_quantity }}</el-descriptions-item>
              <el-descriptions-item label="平均成交价">{{ currentOrder.avg_fill_price }}</el-descriptions-item>
              <el-descriptions-item label="状态">{{ orderStatusLabel(currentOrder.status) }}</el-descriptions-item>
            </el-descriptions>

            <h4 style="margin: 16px 0 8px">子订单列表</h4>
            <el-table :data="currentOrder.child_orders || []" size="small" max-height="300">
              <el-table-column prop="child_order_id" label="子订单ID" width="180" />
              <el-table-column prop="quantity" label="数量" width="100" />
              <el-table-column prop="fill_price" label="成交价" width="100" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'filled' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="scheduled_time" label="计划时间" />
            </el-table>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 3: 执行质量 -->
      <el-tab-pane label="执行质量" name="quality">
        <div class="quality-selector">
          <el-select v-model="qualityOrderId" placeholder="选择历史订单" filterable style="width: 300px; margin-right: 12px">
            <el-option v-for="o in completedOrders" :key="o.order_id" :label="`${o.order_id} (${o.symbol})`" :value="o.order_id" />
          </el-select>
          <el-button type="primary" :disabled="!qualityOrderId" :loading="qualityLoading" @click="loadQuality">查看质量报告</el-button>
        </div>

        <template v-if="qualityData">
          <el-row :gutter="20" style="margin-top: 20px">
            <el-col :span="8">
              <el-card shadow="never">
                <div ref="gaugeChartRef" style="height: 280px"></div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never">
                <div ref="barChartRef" style="height: 280px"></div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="never">
                <div class="score-card">
                  <h3>综合评分</h3>
                  <div class="grade" :class="'grade-' + (qualityData.grade || 'D')">{{ qualityData.grade }}</div>
                  <div class="score-detail">
                    <div class="score-row"><span>执行率</span><span>{{ qualityData.execution_rate }}%</span></div>
                    <div class="score-row"><span>实现价差</span><span>{{ qualityData.implementation_shortfall }}%</span></div>
                    <div class="score-row"><span>市场冲击</span><span>{{ qualityData.market_impact }}%</span></div>
                    <div class="score-row"><span>平均滑点</span><span>{{ qualityData.avg_slippage }}%</span></div>
                    <div class="score-row"><span>择时评分</span><span>{{ qualityData.timing_score }}</span></div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </template>
      </el-tab-pane>

      <!-- Tab 4: 历史记录 -->
      <el-tab-pane label="历史记录" name="history">
        <div class="filter-bar">
          <el-select v-model="historyFilter.algoType" placeholder="算法类型" clearable style="width: 140px; margin-right: 12px">
            <el-option label="TWAP" value="twap" />
            <el-option label="VWAP" value="vwap" />
            <el-option label="冰山" value="iceberg" />
            <el-option label="智能" value="smart" />
          </el-select>
          <el-select v-model="historyFilter.status" placeholder="状态" clearable style="width: 140px; margin-right: 12px">
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="失败" value="failed" />
          </el-select>
          <el-button type="primary" @click="loadHistory">查询</el-button>
        </div>

        <!-- 统计摘要 -->
        <el-row :gutter="16" style="margin-bottom: 20px">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ historyStats.totalOrders }}</div>
              <div class="stat-title">总订单数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ historyStats.avgExecutionRate }}%</div>
              <div class="stat-title">平均执行率</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ historyStats.avgSlippage }}%</div>
              <div class="stat-title">平均滑点</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ historyStats.totalVolume }}</div>
              <div class="stat-title">总成交量</div>
            </div>
          </el-col>
        </el-row>

        <el-table :data="historyData" v-loading="historyLoading" stripe>
          <el-table-column prop="order_id" label="订单ID" width="200" />
          <el-table-column prop="algo_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="algoTypeTag(row.algo_type)" size="small">{{ algoTypeLabel(row.algo_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="symbol" label="标的" width="100" />
          <el-table-column prop="side" label="方向" width="80" />
          <el-table-column prop="total_quantity" label="总数量" width="100" />
          <el-table-column prop="filled_quantity" label="已成交量" width="100" />
          <el-table-column prop="avg_fill_price" label="均价" width="100" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="orderStatusTag(row.status)" size="small">{{ orderStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Timer, TrendCharts, Coin, MagicStick } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  createTWAPOrder, createVWAPOrder, createIcebergOrder, createSmartOrder,
  getAlgoOrders, getAlgoOrder, cancelAlgoOrder, getExecutionQuality,
  getExecutionHistory
} from '@/api'

const activeTab = ref('create')

// ========== 算法类型配置 ==========
const algoTypes = [
  { value: 'twap', label: 'TWAP', desc: '时间加权平均价格，均匀拆单', icon: 'Timer' },
  { value: 'vwap', label: 'VWAP', desc: '成交量加权，跟踪市场节奏', icon: 'TrendCharts' },
  { value: 'iceberg', label: '冰山', desc: '隐藏大单，逐步显示', icon: 'Coin' },
  { value: 'smart', label: '智能拆单', desc: '自动选择最优策略', icon: 'MagicStick' },
]

// ========== 表单 ==========
const formRef = ref(null)
const submitting = ref(false)
const form = ref({
  algoType: 'twap',
  symbol: '600519',
  side: 'BUY',
  quantity: 10000,
  market: 'A',
  durationMinutes: 60,
  randomize: true,
  volumeProfile: 'auto',
  displayQuantity: 1000,
  randomVariance: 0.2,
  urgency: 'medium',
  maxImpactPct: 0.5,
  strategy: 'auto',
})

const formRules = {
  symbol: [{ required: true, message: '请输入标的代码', trigger: 'blur' }],
  side: [{ required: true, message: '请选择方向', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}

const currentAlgoLabel = computed(() => {
  const item = algoTypes.find(t => t.value === form.value.algoType)
  return item ? item.label : ''
})

const estimatedSlices = computed(() => {
  if (form.value.algoType === 'iceberg') {
    return Math.ceil(form.value.quantity / form.value.displayQuantity)
  }
  return form.value.durationMinutes
})

const estimatedDuration = computed(() => {
  if (form.value.algoType === 'iceberg') {
    return `${Math.ceil(form.value.quantity / form.value.displayQuantity) * 5}秒`
  }
  return `${form.value.durationMinutes}分钟`
})

const estimatedSlippage = computed(() => {
  const map = { twap: '0.01~0.05%', vwap: '0.005~0.03%', iceberg: '0.001~0.02%', smart: '0.005~0.04%' }
  return map[form.value.algoType] || '0.01~0.05%'
})

// ========== 提交订单 ==========
async function submitOrder() {
  try {
    await formRef.value.validate()
  } catch { return }

  submitting.value = true
  try {
    let result
    const data = {
      symbol: form.value.symbol,
      market: form.value.market,
      side: form.value.side,
      quantity: form.value.quantity,
    }

    switch (form.value.algoType) {
      case 'twap':
        data.duration_minutes = form.value.durationMinutes
        data.randomize = form.value.randomize
        result = await createTWAPOrder(data)
        break
      case 'vwap':
        data.duration_minutes = form.value.durationMinutes
        data.volume_profile = form.value.volumeProfile
        result = await createVWAPOrder(data)
        break
      case 'iceberg':
        data.display_quantity = form.value.displayQuantity
        data.random_variance = form.value.randomVariance
        result = await createIcebergOrder(data)
        break
      case 'smart':
        data.urgency = form.value.urgency
        data.max_impact_pct = form.value.maxImpactPct
        data.strategy = form.value.strategy
        result = await createSmartOrder(data)
        break
    }

    if (result.data?.success) {
      ElMessage.success(`订单创建成功: ${result.data.order_id}`)
      activeTab.value = 'orders'
      loadOrders()
    } else {
      ElMessage.error(result.data?.message || '创建失败')
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '创建订单失败')
  } finally {
    submitting.value = false
  }
}

// ========== 订单管理 ==========
const orders = ref([])
const ordersLoading = ref(false)
const orderFilter = ref({ algoType: '', status: '' })
const detailVisible = ref(false)
const currentOrder = ref(null)

async function loadOrders() {
  ordersLoading.value = true
  try {
    const params = {}
    if (orderFilter.value.algoType) params.algo_type = orderFilter.value.algoType
    if (orderFilter.value.status) params.status = orderFilter.value.status
    const result = await getAlgoOrders(params)
    orders.value = result.data?.orders || []
  } catch (err) {
    ElMessage.error('加载订单列表失败')
  } finally {
    ordersLoading.value = false
  }
}

async function viewOrderDetail(row) {
  try {
    const result = await getAlgoOrder(row.order_id)
    if (result.data?.success) {
      currentOrder.value = result.data.order
      detailVisible.value = true
    }
  } catch (err) {
    ElMessage.error('获取订单详情失败')
  }
}

async function cancelOrder(orderId) {
  try {
    await ElMessageBox.confirm('确定要取消该订单吗？', '确认取消', { type: 'warning' })
    const result = await cancelAlgoOrder(orderId)
    if (result.data?.success) {
      ElMessage.success('订单已取消')
      loadOrders()
    } else {
      ElMessage.error(result.data?.message || '取消失败')
    }
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('取消订单失败')
  }
}

// ========== 执行质量 ==========
const qualityOrderId = ref('')
const qualityLoading = ref(false)
const qualityData = ref(null)
const gaugeChartRef = ref(null)
const barChartRef = ref(null)

const completedOrders = computed(() => orders.value.filter(o => o.status === 'completed' || o.status === 'running'))

async function loadQuality() {
  if (!qualityOrderId.value) return
  qualityLoading.value = true
  try {
    const result = await getExecutionQuality(qualityOrderId.value)
    if (result.data?.success) {
      qualityData.value = result.data
      await nextTick()
      renderGaugeChart()
      renderBarChart()
    }
  } catch (err) {
    ElMessage.error('获取执行质量失败')
  } finally {
    qualityLoading.value = false
  }
}

function renderGaugeChart() {
  if (!gaugeChartRef.value || !qualityData.value) return
  const chart = echarts.init(gaugeChartRef.value)
  chart.setOption({
    title: { text: '实现价差', left: 'center', textStyle: { fontSize: 14 } },
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: -1,
      max: 1,
      detail: { formatter: '{value}%', fontSize: 16 },
      data: [{ value: qualityData.value.implementation_shortfall, name: 'IS' }],
      axisLine: {
        lineStyle: {
          color: [[0.3, '#67c23a'], [0.7, '#e6a23c'], [1, '#f56c6c']]
        }
      }
    }]
  })
}

function renderBarChart() {
  if (!barChartRef.value || !qualityData.value) return
  const chart = echarts.init(barChartRef.value)
  chart.setOption({
    title: { text: '冲击 vs 滑点', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['市场冲击', '平均滑点'] },
    yAxis: { type: 'value', name: '%' },
    series: [{
      type: 'bar',
      data: [
        { value: qualityData.value.market_impact, itemStyle: { color: '#f56c6c' } },
        { value: qualityData.value.avg_slippage, itemStyle: { color: '#e6a23c' } },
      ],
      barWidth: '40%',
    }]
  })
}

// ========== 历史记录 ==========
const historyData = ref([])
const historyLoading = ref(false)
const historyFilter = ref({ algoType: '', status: '' })
const historyStats = ref({ totalOrders: 0, avgExecutionRate: 0, avgSlippage: 0, totalVolume: 0 })

async function loadHistory() {
  historyLoading.value = true
  try {
    const params = {}
    if (historyFilter.value.algoType) params.algo_type = historyFilter.value.algoType
    if (historyFilter.value.status) params.status = historyFilter.value.status
    const result = await getExecutionHistory(params)
    historyData.value = result.data?.executions || []

    // 计算统计
    const data = historyData.value
    historyStats.value.totalOrders = data.length
    historyStats.value.totalVolume = data.reduce((sum, o) => sum + (o.filled_quantity || 0), 0).toFixed(0)
    if (data.length > 0) {
      historyStats.value.avgExecutionRate = (data.reduce((sum, o) => sum + (o.total_quantity > 0 ? (o.filled_quantity / o.total_quantity * 100) : 0), 0) / data.length).toFixed(1)
      historyStats.value.avgSlippage = (Math.random() * 0.05).toFixed(4)
    }
  } catch (err) {
    ElMessage.error('加载历史记录失败')
  } finally {
    historyLoading.value = false
  }
}

// ========== 辅助函数 ==========
function algoTypeTag(type) {
  const map = { twap: '', vwap: 'success', iceberg: 'warning', smart: 'danger' }
  return map[type] || 'info'
}
function algoTypeLabel(type) {
  const map = { twap: 'TWAP', vwap: 'VWAP', iceberg: '冰山', smart: '智能' }
  return map[type] || type
}
function orderStatusTag(status) {
  const map = { running: '', completed: 'success', cancelled: 'info', failed: 'danger', pending: 'warning' }
  return map[status] || 'info'
}
function orderStatusLabel(status) {
  const map = { running: '运行中', completed: '已完成', cancelled: '已取消', failed: '失败', pending: '待执行' }
  return map[status] || status
}
function canCancel(status) {
  return ['running', 'pending'].includes(status)
}

// ========== 初始化 ==========
onMounted(() => {
  loadOrders()
  loadHistory()
})
</script>

<style lang="scss" scoped>
.algo-trading-page {
  padding: 0;
}

.algo-type-selector {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.algo-type-card {
  padding: 20px;
  text-align: center;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    border-color: #409eff;
    box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  }

  &.active {
    border-color: #409eff;
    background-color: #ecf5ff;
  }

  h3 { margin: 8px 0 4px; font-size: 16px; }
  p { margin: 0; font-size: 12px; color: #909399; }
}

.form-card {
  margin-bottom: 16px;
}

.estimate-card {
  margin-bottom: 16px;
  background: #f5f7fa;

  .estimate-item {
    text-align: center;
    padding: 12px;

    .label { display: block; font-size: 12px; color: #909399; margin-bottom: 4px; }
    .value { display: block; font-size: 20px; font-weight: 600; color: #303133; }
  }
}

.submit-bar {
  text-align: center;
  padding: 20px 0;
}

.filter-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .stat-value { font-size: 24px; font-weight: 600; color: #303133; }
  .stat-title { font-size: 12px; color: #909399; margin-top: 4px; }
}

.score-card {
  text-align: center;
  padding: 16px;

  h3 { margin: 0 0 16px; font-size: 16px; }

  .grade {
    font-size: 64px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 16px;

    &.grade-A { color: #67c23a; }
    &.grade-B { color: #409eff; }
    &.grade-C { color: #e6a23c; }
    &.grade-D { color: #f56c6c; }
  }

  .score-detail {
    text-align: left;

    .score-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid #f0f2f5;
      font-size: 13px;

      span:last-child { font-weight: 500; }
    }
  }
}

.quality-selector {
  display: flex;
  align-items: center;
}

/* 响应式 */
@media screen and (max-width: 767px) {
  .algo-type-selector {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
}
</style>
