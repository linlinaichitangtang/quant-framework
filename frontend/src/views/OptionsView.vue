<template>
  <div class="options-view">
    <div class="page-header">
      <h2>期权分析</h2>
    </div>

    <!-- 参数配置 -->
    <el-card shadow="hover" class="config-card">
      <template #header>期权链参数</template>
      <el-form :inline="true" :model="chainParams">
        <el-form-item label="标的代码">
          <el-input v-model="chainParams.symbol" placeholder="AAPL" style="width: 120px" />
        </el-form-item>
        <el-form-item label="标的价格">
          <el-input-number v-model="chainParams.price" :min="1" :step="1" style="width: 140px" />
        </el-form-item>
        <el-form-item label="到期日">
          <el-date-picker v-model="chainParams.expiry" type="date" value-format="YYYY-MM-DD" placeholder="选择到期日" style="width: 160px" />
        </el-form-item>
        <el-form-item label="无风险利率">
          <el-input-number v-model="chainParams.rate" :min="0" :max="0.2" :step="0.01" :precision="2" style="width: 130px" />
        </el-form-item>
        <el-form-item label="波动率">
          <el-input-number v-model="chainParams.vol" :min="0.05" :max="2" :step="0.05" :precision="2" style="width: 130px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchChain" :loading="loading">查询期权链</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 期权链表格 -->
    <el-card shadow="hover" class="chain-card" v-if="chainData.length > 0">
      <template #header>
        <div class="chain-header">
          <span>期权链 — {{ chainParams.symbol }} @ {{ chainParams.price }}</span>
          <el-radio-group v-model="displayMode" size="small">
            <el-radio-button value="table">表格</el-radio-button>
            <el-radio-button value="greeks">希腊字母</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <!-- 表格模式 -->
      <el-table v-if="displayMode === 'table'" :data="chainData" stripe max-height="600" style="width: 100%" size="small">
        <el-table-column prop="strike_price" label="行权价" width="90" align="center" />
        <el-table-column label="看涨" align="center">
          <el-table-column prop="call_bid" label="买价" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'CALL' ? row.bid?.toFixed(2) : '' }}</template>
          </el-table-column>
          <el-table-column prop="call_ask" label="卖价" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'CALL' ? row.ask?.toFixed(2) : '' }}</template>
          </el-table-column>
          <el-table-column prop="call_last" label="最新" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'CALL' ? row.last_price?.toFixed(2) : '' }}</template>
          </el-table-column>
          <el-table-column prop="call_vol" label="成交量" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'CALL' ? row.volume : '' }}</template>
          </el-table-column>
          <el-table-column prop="call_oi" label="持仓量" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'CALL' ? row.open_interest : '' }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="看跌" align="center">
          <el-table-column prop="put_bid" label="买价" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'PUT' ? row.bid?.toFixed(2) : '' }}</template>
          </el-table-column>
          <el-table-column prop="put_ask" label="卖价" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'PUT' ? row.ask?.toFixed(2) : '' }}</template>
          </el-table-column>
          <el-table-column prop="put_last" label="最新" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'PUT' ? row.last_price?.toFixed(2) : '' }}</template>
          </el-table-column>
          <el-table-column prop="put_vol" label="成交量" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'PUT' ? row.volume : '' }}</template>
          </el-table-column>
          <el-table-column prop="put_oi" label="持仓量" width="80" align="right">
            <template #default="{ row }">{{ row.option_type === 'PUT' ? row.open_interest : '' }}</template>
          </el-table-column>
        </el-table-column>
        <el-table-column label="隐含波动率" width="100" align="center">
          <template #default="{ row }">{{ row.option_type === 'CALL' ? (row.implied_vol * 100).toFixed(1) + '%' : '' }}</template>
        </el-table-column>
      </el-table>

      <!-- 希腊字母模式 -->
      <el-table v-if="displayMode === 'greeks'" :data="chainData" stripe max-height="600" style="width: 100%" size="small">
        <el-table-column prop="option_type" label="类型" width="60" align="center">
          <template #default="{ row }">
            <el-tag :type="row.option_type === 'CALL' ? 'danger' : 'success'" size="small">
              {{ row.option_type === 'CALL' ? 'C' : 'P' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="strike_price" label="行权价" width="90" align="center" />
        <el-table-column label="Delta" width="90" align="right">
          <template #default="{ row }">{{ row.delta?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="Gamma" width="90" align="right">
          <template #default="{ row }">{{ row.gamma?.toFixed(6) }}</template>
        </el-table-column>
        <el-table-column label="Theta" width="90" align="right">
          <template #default="{ row }">
            <span :class="row.theta < 0 ? 'loss' : ''">{{ row.theta?.toFixed(4) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Vega" width="90" align="right">
          <template #default="{ row }">{{ row.vega?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="IV" width="80" align="right">
          <template #default="{ row }">{{ (row.implied_vol * 100).toFixed(1) }}%</template>
        </el-table-column>
        <el-table-column label="内在" width="80" align="right">
          <template #default="{ row }">{{ row.intrinsic_value?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="时间" width="80" align="right">
          <template #default="{ row }">{{ row.time_value?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="实值" width="60" align="center">
          <template #default="{ row }">{{ row.is_itm ? '✓' : '' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 组合盈亏分析 -->
    <el-card shadow="hover" class="pnl-card">
      <template #header>
        <div class="chain-header">
          <span>组合盈亏分析</span>
          <el-button type="primary" size="small" @click="addLeg" :disabled="pnlLegs.length >= 4">添加腿</el-button>
          <el-button type="success" size="small" @click="calcPnl" :loading="pnlLoading">计算盈亏</el-button>
        </div>
      </template>

      <el-table :data="pnlLegs" stripe size="small" style="width: 100%; margin-bottom: 16px;">
        <el-table-column label="方向" width="80">
          <template #default="{ row }">
            <el-select v-model="row.action" size="small" style="width: 70px">
              <el-option label="买入" value="buy" />
              <el-option label="卖出" value="sell" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-select v-model="row.option_type" size="small" style="width: 70px">
              <el-option label="CALL" value="CALL" />
              <el-option label="PUT" value="PUT" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="行权价" width="100">
          <template #default="{ row }">
            <el-input-number v-model="row.strike" :min="1" :step="1" size="small" controls-position="right" style="width: 90px" />
          </template>
        </el-table-column>
        <el-table-column label="权利金" width="100">
          <template #default="{ row }">
            <el-input-number v-model="row.premium" :min="0.01" :step="0.5" :precision="2" size="small" controls-position="right" style="width: 90px" />
          </template>
        </el-table-column>
        <el-table-column label="数量" width="80">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="1" :max="100" size="small" controls-position="right" style="width: 70px" />
          </template>
        </el-table-column>
        <el-table-column label="乘数" width="80">
          <template #default="{ row }">
            <el-input-number v-model="row.multiplier" :min="1" size="small" controls-position="right" style="width: 70px" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="60">
          <template #default="{ $index }">
            <el-button size="small" type="danger" link @click="pnlLegs.splice($index, 1)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 预设策略 -->
      <div class="preset-strategies">
        <span class="preset-label">预设策略：</span>
        <el-button size="small" @click="loadPreset('bull_call_spread')">牛市价差</el-button>
        <el-button size="small" @click="loadPreset('bear_put_spread')">熊市价差</el-button>
        <el-button size="small" @click="loadPreset('straddle')">跨式</el-button>
        <el-button size="small" @click="loadPreset('strangle')">宽跨式</el-button>
        <el-button size="small" @click="loadPreset('iron_condor')">铁鹰</el-button>
        <el-button size="small" @click="loadPreset('butterfly')">蝴蝶</el-button>
      </div>

      <!-- 盈亏图 -->
      <div ref="pnlChartRef" style="height: 400px; margin-top: 16px;" v-show="pnlChartData.length > 0"></div>

      <!-- 盈亏指标 -->
      <el-row :gutter="16" v-if="pnlResult" style="margin-top: 16px;">
        <el-col :span="6">
          <div class="pnl-metric">
            <div class="pnl-label">最大盈利</div>
            <div class="pnl-value profit">${{ pnlResult.max_profit?.toLocaleString() }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="pnl-metric">
            <div class="pnl-label">最大亏损</div>
            <div class="pnl-value loss">${{ pnlResult.max_loss?.toLocaleString() }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="pnl-metric">
            <div class="pnl-label">盈亏平衡点</div>
            <div class="pnl-value">{{ pnlResult.breakevens?.join(' / ') || '-' }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="pnl-metric">
            <div class="pnl-label">净权利金</div>
            <div class="pnl-value">{{ netPremiumDisplay }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getOptionChain, getOptionStrategyPnl } from '@/api'

const loading = ref(false)
const pnlLoading = ref(false)
const displayMode = ref('table')

// 期权链参数
const chainParams = reactive({
  symbol: 'AAPL',
  price: 185,
  expiry: '2025-06-20',
  rate: 0.05,
  vol: 0.30,
})

// 期权链数据
const chainData = ref([])

// 组合盈亏
const pnlLegs = ref([])
const pnlResult = ref(null)
const pnlChartData = ref([])
const pnlChartRef = ref(null)
let pnlChart = null

// 计算净权利金
const netPremiumDisplay = computed(() => {
  let net = 0
  for (const leg of pnlLegs.value) {
    const sign = leg.action === 'sell' ? 1 : -1
    net += sign * leg.premium * leg.quantity * leg.multiplier
  }
  const prefix = net >= 0 ? '+' : ''
  return `${prefix}$${net.toFixed(0)}`
})

// 获取期权链
async function fetchChain() {
  loading.value = true
  try {
    const data = await getOptionChain({
      symbol: chainParams.symbol,
      underlying_price: chainParams.price,
      expiry_date: chainParams.expiry,
      risk_free_rate: chainParams.rate,
      base_volatility: chainParams.vol,
    })
    chainData.value = data.contracts || []
  } catch (e) {
    ElMessage.error('获取期权链失败')
  } finally {
    loading.value = false
  }
}

// 添加腿
function addLeg() {
  pnlLegs.value.push({
    action: 'buy',
    option_type: 'CALL',
    strike: chainParams.price,
    premium: 5.0,
    quantity: 1,
    multiplier: 100,
  })
}

// 加载预设策略
function loadPreset(type) {
  const K = chainParams.price
  const step = Math.round(K * 0.05)
  const presets = {
    bull_call_spread: [
      { action: 'buy', option_type: 'CALL', strike: K, premium: 5.0, quantity: 1, multiplier: 100 },
      { action: 'sell', option_type: 'CALL', strike: K + step, premium: 2.5, quantity: 1, multiplier: 100 },
    ],
    bear_put_spread: [
      { action: 'buy', option_type: 'PUT', strike: K, premium: 4.5, quantity: 1, multiplier: 100 },
      { action: 'sell', option_type: 'PUT', strike: K - step, premium: 2.0, quantity: 1, multiplier: 100 },
    ],
    straddle: [
      { action: 'buy', option_type: 'CALL', strike: K, premium: 5.0, quantity: 1, multiplier: 100 },
      { action: 'buy', option_type: 'PUT', strike: K, premium: 4.5, quantity: 1, multiplier: 100 },
    ],
    strangle: [
      { action: 'buy', option_type: 'CALL', strike: K + step, premium: 3.0, quantity: 1, multiplier: 100 },
      { action: 'buy', option_type: 'PUT', strike: K - step, premium: 2.5, quantity: 1, multiplier: 100 },
    ],
    iron_condor: [
      { action: 'sell', option_type: 'PUT', strike: K - step, premium: 3.0, quantity: 1, multiplier: 100 },
      { action: 'buy', option_type: 'PUT', strike: K - step * 2, premium: 1.5, quantity: 1, multiplier: 100 },
      { action: 'sell', option_type: 'CALL', strike: K + step, premium: 3.0, quantity: 1, multiplier: 100 },
      { action: 'buy', option_type: 'CALL', strike: K + step * 2, premium: 1.5, quantity: 1, multiplier: 100 },
    ],
    butterfly: [
      { action: 'buy', option_type: 'CALL', strike: K - step, premium: 6.0, quantity: 1, multiplier: 100 },
      { action: 'sell', option_type: 'CALL', strike: K, premium: 4.0, quantity: 2, multiplier: 100 },
      { action: 'buy', option_type: 'CALL', strike: K + step, premium: 2.0, quantity: 1, multiplier: 100 },
    ],
  }
  pnlLegs.value = JSON.parse(JSON.stringify(presets[type] || []))
  ElMessage.success('已加载预设策略')
}

// 计算盈亏
async function calcPnl() {
  if (pnlLegs.value.length === 0) {
    ElMessage.warning('请先添加组合腿')
    return
  }
  pnlLoading.value = true
  try {
    const data = await getOptionStrategyPnl(pnlLegs.value)
    pnlResult.value = data
    pnlChartData.value = data.pnl_data || []
    await nextTick()
    initPnlChart()
  } catch (e) {
    ElMessage.error('计算盈亏失败')
  } finally {
    pnlLoading.value = false
  }
}

// 初始化盈亏图
function initPnlChart() {
  if (!pnlChartRef.value || pnlChartData.value.length === 0) return
  if (pnlChart) pnlChart.dispose()
  pnlChart = echarts.init(pnlChartRef.value)

  const prices = pnlChartData.value.map(d => d.price)
  const pnls = pnlChartData.value.map(d => d.pnl)

  pnlChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: p => `标的价格: $${p[0].name}<br/>盈亏: $${p[0].value.toFixed(0)}`
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: prices,
      name: '标的价格 ($)',
      axisLabel: { formatter: v => '$' + Number(v).toFixed(0) },
    },
    yAxis: {
      type: 'value',
      name: '盈亏 ($)',
      axisLabel: { formatter: v => '$' + Number(v).toFixed(0) },
    },
    series: [{
      type: 'line',
      data: pnls,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
          { offset: 0.5, color: 'rgba(103, 194, 58, 0.02)' },
          { offset: 0.5, color: 'rgba(245, 108, 108, 0.02)' },
          { offset: 1, color: 'rgba(245, 108, 108, 0.3)' },
        ])
      },
      markLine: {
        data: [{ yAxis: 0 }],
        lineStyle: { color: '#999', type: 'dashed' },
      },
    }],
  })
}

function handleResize() {
  pnlChart?.resize()
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  pnlChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.options-view {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 22px;
}
.config-card, .chain-card, .pnl-card {
  margin-bottom: 20px;
}
.chain-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.preset-strategies {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.preset-label {
  font-size: 13px;
  color: #909399;
}
.pnl-metric {
  text-align: center;
  padding: 8px 0;
}
.pnl-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}
.pnl-value {
  font-size: 18px;
  font-weight: 600;
}
.profit { color: #67C23A; font-weight: 600; }
.loss { color: #F56C6C; font-weight: 600; }
</style>
