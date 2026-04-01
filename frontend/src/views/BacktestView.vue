<template>
  <div class="backtest-view">
    <!-- 顶部：回测列表 + 新建回测 -->
    <div class="page-header">
      <h2>回测可视化</h2>
      <el-button type="primary" @click="showRunDialog = true" :loading="store.running">
        运行新回测
      </el-button>
    </div>

    <!-- 回测列表 -->
    <el-card v-if="!currentResult" class="result-list-card">
      <el-table :data="store.results" v-loading="store.loading" stripe style="width: 100%">
        <el-table-column prop="name" label="回测名称" min-width="160" />
        <el-table-column prop="strategy_type" label="策略类型" width="140" />
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="总收益率" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.total_return >= 0 ? 'profit' : 'loss'">
              {{ formatPct(row.total_return) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最大回撤" width="110" align="right">
          <template #default="{ row }">
            <span class="loss">{{ formatPct(row.max_drawdown) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="夏普比率" width="100" align="right">
          <template #default="{ row }">
            {{ row.sharpe_ratio != null ? row.sharpe_ratio.toFixed(2) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="胜率" width="90" align="right">
          <template #default="{ row }">
            {{ row.win_rate != null ? (row.win_rate * 100).toFixed(1) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="n_trades" label="交易次数" width="90" align="right" />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewDetail(row.id)">查看</el-button>
            <el-popconfirm title="确定删除此回测？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap" v-if="store.total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="store.total"
          layout="prev, pager, next"
          @current-change="loadResults"
        />
      </div>
    </el-card>

    <!-- 回测详情 -->
    <template v-if="currentResult">
      <div class="detail-header">
        <el-button @click="currentResult = null" :icon="ArrowLeft">返回列表</el-button>
        <h3>{{ currentResult.name }}</h3>
        <el-tag :type="statusType(currentResult.status)">{{ statusText(currentResult.status) }}</el-tag>
      </div>

      <!-- 指标卡片 -->
      <el-row :gutter="16" class="metrics-row">
        <el-col :span="4" v-for="m in metrics" :key="m.label">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value" :class="m.cls">{{ m.value }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 图表区域 -->
      <el-row :gutter="16" class="charts-row">
        <el-col :span="16">
          <el-card shadow="hover">
            <template #header>收益曲线</template>
            <div ref="equityChartRef" style="height: 380px;"></div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>回撤曲线</template>
            <div ref="drawdownChartRef" style="height: 380px;"></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="charts-row">
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>特征重要性 (SHAP)</template>
            <div ref="featureChartRef" style="height: 360px;"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>交易盈亏分布</template>
            <div ref="pnlDistChartRef" style="height: 360px;"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 交易明细 -->
      <el-card shadow="hover" class="trades-card">
        <template #header>交易明细 ({{ currentResult.trades?.length || 0 }} 笔)</template>
        <el-table :data="currentResult.trades || []" stripe max-height="500" style="width: 100%">
          <el-table-column prop="date" label="日期" width="110" />
          <el-table-column prop="action" label="方向" width="70">
            <template #default="{ row }">
              <el-tag :type="row.action === 'buy' ? 'danger' : 'success'" size="small">
                {{ row.action === 'buy' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="code" label="代码" width="120" />
          <el-table-column label="价格" width="100" align="right">
            <template #default="{ row }">{{ row.price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="shares" label="数量" width="80" align="right" />
          <el-table-column label="盈亏" width="120" align="right">
            <template #default="{ row }">
              <span v-if="row.pnl != null" :class="row.pnl >= 0 ? 'profit' : 'loss'">
                {{ row.pnl.toFixed(2) }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="盈亏比例" width="110" align="right">
            <template #default="{ row }">
              <span v-if="row.pnl_pct != null" :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                {{ (row.pnl_pct * 100).toFixed(2) }}%
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="佣金" width="90" align="right">
            <template #default="{ row }">{{ row.commission?.toFixed(2) || '-' }}</template>
          </el-table-column>
          <el-table-column label="印花税" width="90" align="right">
            <template #default="{ row }">{{ row.stamp_tax?.toFixed(2) || '-' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 新建回测对话框 -->
    <el-dialog v-model="showRunDialog" title="运行新回测" width="560px" destroy-on-close>
      <el-form :model="runForm" label-width="120px" :rules="formRules" ref="formRef">
        <el-form-item label="回测名称" prop="name">
          <el-input v-model="runForm.name" placeholder="例如：ML策略测试-2024Q1" />
        </el-form-item>
        <el-form-item label="策略类型" prop="strategy_type">
          <el-select v-model="runForm.strategy_type" style="width: 100%">
            <el-option label="ML 尾盘选股" value="ml_stock_picker" />
          </el-select>
        </el-form-item>
        <el-form-item label="市场">
          <el-select v-model="runForm.market" style="width: 100%">
            <el-option label="A股" value="A" />
            <el-option label="港股" value="HK" />
            <el-option label="美股" value="US" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">回测参数</el-divider>
        <el-form-item label="初始资金">
          <el-input-number v-model="runForm.initial_capital" :min="10000" :step="100000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="佣金费率">
          <el-input-number v-model="runForm.commission" :min="0" :max="0.01" :step="0.0001" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-form-item label="印花税率">
          <el-input-number v-model="runForm.stamp_tax" :min="0" :max="0.01" :step="0.0001" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-form-item label="滑点">
          <el-input-number v-model="runForm.slippage" :min="0" :max="0.01" :step="0.0001" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-divider content-position="left">策略参数</el-divider>
        <el-form-item label="每日选股数">
          <el-input-number v-model="runForm.top_n" :min="1" :max="20" style="width: 100%" />
        </el-form-item>
        <el-form-item label="最低概率">
          <el-slider v-model="runForm.min_prob" :min="0.1" :max="0.99" :step="0.05" show-input />
        </el-form-item>
        <el-form-item label="模型类型">
          <el-radio-group v-model="runForm.model_type">
            <el-radio value="gbm">GBM</el-radio>
            <el-radio value="rf">Random Forest</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="调参次数">
          <el-input-number v-model="runForm.n_trials" :min="1" :max="200" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRunDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRun" :loading="store.running">开始回测</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { useBacktestStore } from '@/stores/backtest'

const store = useBacktestStore()

// 列表状态
const currentPage = ref(1)
const pageSize = 20

// 详情状态
const currentResult = ref(null)

// 图表 refs
const equityChartRef = ref(null)
const drawdownChartRef = ref(null)
const featureChartRef = ref(null)
const pnlDistChartRef = ref(null)
let charts = []

// 新建回测
const showRunDialog = ref(false)
const formRef = ref(null)
const runForm = reactive({
  name: '',
  strategy_type: 'ml_stock_picker',
  market: 'A',
  initial_capital: 1000000,
  commission: 0.0003,
  stamp_tax: 0.001,
  slippage: 0.001,
  top_n: 3,
  min_prob: 0.5,
  max_position_pct: 0.2,
  model_type: 'gbm',
  n_trials: 20,
})
const formRules = {
  name: [{ required: true, message: '请输入回测名称', trigger: 'blur' }],
  strategy_type: [{ required: true, message: '请选择策略类型', trigger: 'change' }],
}

// 指标卡片
const metrics = computed(() => {
  const r = currentResult.value
  if (!r) return []
  return [
    { label: '总收益率', value: formatPct(r.total_return), cls: r.total_return >= 0 ? 'profit' : 'loss' },
    { label: '年化收益率', value: formatPct(r.annual_return), cls: r.annual_return >= 0 ? 'profit' : 'loss' },
    { label: '最大回撤', value: formatPct(r.max_drawdown), cls: 'loss' },
    { label: '夏普比率', value: r.sharpe_ratio?.toFixed(2) ?? '-', cls: r.sharpe_ratio >= 1 ? 'profit' : '' },
    { label: '胜率', value: r.win_rate != null ? (r.win_rate * 100).toFixed(1) + '%' : '-', cls: '' },
    { label: '盈亏比', value: r.profit_loss_ratio != null && isFinite(r.profit_loss_ratio) ? r.profit_loss_ratio.toFixed(2) : '-', cls: '' },
  ]
})

// 工具函数
function formatPct(v) {
  if (v == null) return '-'
  return (v * 100).toFixed(2) + '%'
}
function formatDate(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN')
}
function statusType(s) {
  return s === 'completed' ? 'success' : s === 'failed' ? 'danger' : 'warning'
}
function statusText(s) {
  return s === 'completed' ? '完成' : s === 'failed' ? '失败' : '运行中'
}

// 加载列表
async function loadResults() {
  await store.fetchResults({ page: currentPage.value, page_size: pageSize })
}

// 查看详情
async function viewDetail(id) {
  try {
    const data = await store.fetchDetail(id)
    currentResult.value = data
    await nextTick()
    initCharts()
  } catch (e) {
    ElMessage.error('加载回测详情失败')
  }
}

// 删除
async function handleDelete(id) {
  try {
    await store.removeBacktest(id)
    ElMessage.success('已删除')
    if (store.results.length === 0 && currentPage.value > 1) {
      currentPage.value--
    }
    await loadResults()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 运行回测
async function handleRun() {
  try {
    await formRef.value?.validate()
  } catch { return }

  try {
    const result = await store.runNewBacktest(runForm)
    ElMessage.success('回测完成')
    showRunDialog.value = false
    runForm.name = ''
    await loadResults()
    // 自动查看新结果
    await viewDetail(result.id)
  } catch (e) {
    ElMessage.error('回测执行失败: ' + (e?.response?.data?.detail || e.message))
  }
}

// 初始化图表
function initCharts() {
  disposeCharts()
  const r = currentResult.value
  if (!r) return

  // 解析每日数据
  let dailyData = []
  try {
    dailyData = r.daily_values ? JSON.parse(r.daily_values) : []
  } catch { dailyData = [] }

  if (dailyData.length > 0) {
    initEquityChart(dailyData)
    initDrawdownChart(dailyData)
  }

  // 特征重要性
  let features = []
  try {
    features = r.feature_importance ? JSON.parse(r.feature_importance) : []
  } catch { features = [] }
  if (features.length > 0) {
    initFeatureChart(features)
  }

  // 盈亏分布
  const sells = (r.trades || []).filter(t => t.action === 'sell' && t.pnl != null)
  if (sells.length > 0) {
    initPnlDistChart(sells)
  }
}

function initEquityChart(data) {
  if (!equityChartRef.value) return
  const chart = echarts.init(equityChartRef.value)
  charts.push(chart)

  const dates = data.map(d => d.date)
  const values = data.map(d => d.total_value)
  const initial = values[0] || 1

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        const p = params[0]
        const val = p.value
        const ret = ((val - initial) / initial * 100).toFixed(2)
        return `${p.name}<br/>总资产: ${val.toLocaleString()}<br/>收益率: ${ret}%`
      }
    },
    legend: { data: ['总资产', '基准线'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: v => (v / 10000).toFixed(0) + '万' }
    },
    series: [
      {
        name: '总资产',
        type: 'line',
        data: values,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.02)' }
          ])
        }
      },
      {
        name: '基准线',
        type: 'line',
        data: dates.map(() => initial),
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#999', width: 1 }
      }
    ]
  })
}

function initDrawdownChart(data) {
  if (!drawdownChartRef.value) return
  const chart = echarts.init(drawdownChartRef.value)
  charts.push(chart)

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: p => `${p[0].name}<br/>回撤: ${(p[0].value * 100).toFixed(2)}%`
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: data.map(d => d.date), boundaryGap: false },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: v => (v * 100).toFixed(1) + '%' }
    },
    series: [{
      type: 'line',
      data: data.map(d => d.drawdown),
      symbol: 'none',
      lineStyle: { width: 2, color: '#E6A23C' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(230, 162, 60, 0.05)' },
          { offset: 1, color: 'rgba(230, 162, 60, 0.35)' }
        ])
      }
    }]
  })
}

function initFeatureChart(features) {
  if (!featureChartRef.value) return
  const chart = echarts.init(featureChartRef.value)
  charts.push(chart)

  const sorted = [...features].sort((a, b) => a.importance - b.importance)
  const names = sorted.map(f => f.feature)
  const values = sorted.map(f => f.importance)

  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '10%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: names },
    series: [{
      type: 'bar',
      data: values,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#409EFF' },
          { offset: 1, color: '#67C23A' }
        ])
      },
      label: { show: true, position: 'right', formatter: '{c}', fontSize: 11 }
    }]
  })
}

function initPnlDistChart(sells) {
  if (!pnlDistChartRef.value) return
  const chart = echarts.init(pnlDistChartRef.value)
  charts.push(chart)

  const pnls = sells.map(t => t.pnl)
  const wins = sells.filter(t => t.pnl > 0).length
  const losses = sells.filter(t => t.pnl <= 0).length

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: p => `盈亏: ${p[0].value.toFixed(2)}`
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: pnls.map((_, i) => `#${i + 1}`) },
    yAxis: { type: 'value', name: '盈亏金额' },
    series: [{
      type: 'bar',
      data: pnls.map(v => ({
        value: v,
        itemStyle: { color: v >= 0 ? '#67C23A' : '#F56C6C' }
      })),
      label: {
        show: true,
        position: pnls.length > 20 ? 'inside' : 'top',
        formatter: p => p.value.toFixed(0),
        fontSize: 10
      }
    }]
  })
}

function disposeCharts() {
  charts.forEach(c => c?.dispose())
  charts = []
}

function handleResize() {
  charts.forEach(c => c?.resize())
}

onMounted(() => {
  loadResults()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  disposeCharts()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.backtest-view {
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
.result-list-card {
  margin-bottom: 20px;
}
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.detail-header h3 {
  margin: 0;
  flex: 1;
}
.metrics-row {
  margin-bottom: 20px;
}
.metric-card {
  text-align: center;
  padding: 4px 0;
}
.metric-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.metric-value {
  font-size: 20px;
  font-weight: 600;
}
.charts-row {
  margin-bottom: 20px;
}
.trades-card {
  margin-bottom: 20px;
}
.profit {
  color: #67C23A;
  font-weight: 600;
}
.loss {
  color: #F56C6C;
  font-weight: 600;
}
</style>
