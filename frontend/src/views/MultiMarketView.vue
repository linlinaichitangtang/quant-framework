<template>
  <div class="multi-market-view">
    <div class="page-header">
      <h2>多市场</h2>
    </div>

    <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
      <!-- Tab 1: 全球市场概览 -->
      <el-tab-pane label="全球市场概览" name="overview">
        <!-- 各市场状态卡片 -->
        <el-row :gutter="12" class="market-status-row">
          <el-col :xs="12" :sm="8" :md="6" :lg="4" v-for="m in marketStatusList" :key="m.market">
            <el-card shadow="hover" class="market-status-card" :class="'status-' + m.status">
              <div class="status-dot" :class="'dot-' + m.status"></div>
              <div class="market-name">{{ getMarketLabel(m.market) }}</div>
              <div class="market-timezone">{{ m.timezone }}</div>
              <div class="market-time">{{ m.current_time }}</div>
              <el-tag :type="getStatusType(m.status)" size="small">{{ getStatusLabel(m.status) }}</el-tag>
            </el-card>
          </el-col>
        </el-row>

        <!-- 各市场主要指数 -->
        <el-card shadow="hover" class="indices-card">
          <template #header>全球主要指数</template>
          <el-row :gutter="12">
            <el-col :xs="12" :sm="8" :md="6" v-for="idx in globalIndices" :key="idx.symbol">
              <div class="index-card" :class="idx.change_pct >= 0 ? 'up' : 'down'">
                <div class="index-name">{{ idx.name }}</div>
                <div class="index-market">{{ getMarketLabel(idx.market) }}</div>
                <div class="index-price">{{ formatNumber(idx.price) }}</div>
                <div class="index-change">{{ idx.change_pct >= 0 ? '+' : '' }}{{ idx.change_pct.toFixed(2) }}%</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 套利机会概览 -->
        <el-card shadow="hover" class="arbitrage-overview-card" v-if="arbitrageOpportunities.length > 0">
          <template #header>跨市场套利机会</template>
          <el-table :data="arbitrageOpportunities" stripe size="small">
            <el-table-column prop="name" label="名称" min-width="150" />
            <el-table-column label="标的A" min-width="120">
              <template #default="{ row }">{{ row.symbol_a }} ({{ row.market_a }})</template>
            </el-table-column>
            <el-table-column label="标的B" min-width="120">
              <template #default="{ row }">{{ row.symbol_b }} ({{ row.market_b }})</template>
            </el-table-column>
            <el-table-column prop="spread_pct" label="价差%" width="90" align="right">
              <template #default="{ row }">
                <span :class="row.spread_pct >= 0 ? 'text-up' : 'text-down'">
                  {{ row.spread_pct >= 0 ? '+' : '' }}{{ row.spread_pct.toFixed(3) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="z_score" label="Z-Score" width="90" align="right">
              <template #default="{ row }">{{ row.z_score?.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column prop="is_profitable" label="有利可图" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_profitable ? 'success' : 'info'" size="small">
                  {{ row.is_profitable ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="estimated_pnl" label="预估盈亏" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.estimated_pnl >= 0 ? 'text-up' : 'text-down'">
                  {{ row.estimated_pnl?.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Tab 2: 期货市场 -->
      <el-tab-pane label="期货市场" name="futures">
        <!-- 交易所筛选 -->
        <el-card shadow="hover" class="filter-card">
          <el-form :inline="true">
            <el-form-item label="交易所">
              <el-select v-model="futuresFilter.exchange" placeholder="全部" clearable style="width: 140px" @change="fetchFuturesContracts">
                <el-option label="中金所" value="CFFE" />
                <el-option label="上期所" value="SHFE" />
                <el-option label="大商所" value="DCE" />
                <el-option label="郑商所" value="CZCE" />
              </el-select>
            </el-form-item>
            <el-form-item label="标的">
              <el-input v-model="futuresFilter.underlying" placeholder="如 IF" style="width: 100px" clearable @clear="fetchFuturesContracts" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="fetchFuturesContracts" :loading="futuresLoading">查询</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 期货合约表格 -->
        <el-card shadow="hover" class="table-card">
          <template #header>期货合约列表 ({{ futuresContracts.length }})</template>
          <el-table :data="futuresContracts" stripe size="small" max-height="500">
            <el-table-column prop="symbol" label="合约代码" width="130" fixed />
            <el-table-column prop="name" label="合约名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="exchange" label="交易所" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.exchange }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_price" label="最新价" width="100" align="right">
              <template #default="{ row }">{{ row.last_price?.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column prop="change_pct" label="涨跌幅" width="90" align="right">
              <template #default="{ row }">
                <span :class="row.change_pct >= 0 ? 'text-up' : 'text-down'">
                  {{ row.change_pct >= 0 ? '+' : '' }}{{ row.change_pct?.toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="volume" label="成交量" width="100" align="right">
              <template #default="{ row }">{{ formatVolume(row.volume) }}</template>
            </el-table-column>
            <el-table-column prop="open_interest" label="持仓量" width="100" align="right">
              <template #default="{ row }">{{ formatVolume(row.open_interest) }}</template>
            </el-table-column>
            <el-table-column prop="multiplier" label="乘数" width="80" align="right" />
            <el-table-column prop="margin_rate" label="保证金率" width="90" align="right">
              <template #default="{ row }">{{ (row.margin_rate * 100).toFixed(1) }}%</template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 保证金计算器 -->
        <el-card shadow="hover" class="calc-card">
          <template #header>保证金计算器</template>
          <el-form :inline="true" :model="marginForm" label-width="80px">
            <el-form-item label="合约代码">
              <el-input v-model="marginForm.symbol" placeholder="IF202606" style="width: 130px" />
            </el-form-item>
            <el-form-item label="手数">
              <el-input-number v-model="marginForm.quantity" :min="1" :step="1" style="width: 120px" />
            </el-form-item>
            <el-form-item label="价格">
              <el-input-number v-model="marginForm.price" :min="0" :step="10" :precision="2" style="width: 140px" />
            </el-form-item>
            <el-form-item label="杠杆">
              <el-input-number v-model="marginForm.leverage" :min="1" :max="20" :step="1" style="width: 120px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="calcMargin" :loading="marginLoading">计算</el-button>
            </el-form-item>
          </el-form>
          <div v-if="marginResult" class="margin-result">
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="合约代码">{{ marginResult.symbol }}</el-descriptions-item>
              <el-descriptions-item label="名义价值">{{ formatMoney(marginResult.notional_value) }}</el-descriptions-item>
              <el-descriptions-item label="所需保证金">{{ formatMoney(marginResult.margin_required) }}</el-descriptions-item>
              <el-descriptions-item label="杠杆倍数">{{ marginResult.leverage }}x</el-descriptions-item>
              <el-descriptions-item label="保证金率">{{ (marginResult.margin_rate * 100).toFixed(1) }}%</el-descriptions-item>
              <el-descriptions-item label="合约乘数">{{ marginResult.multiplier }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- Tab 3: 加密货币 -->
      <el-tab-pane label="加密货币" name="crypto">
        <!-- 主流币行情卡片 -->
        <el-row :gutter="12" class="crypto-cards">
          <el-col :xs="12" :sm="8" :md="6" v-for="coin in cryptoMarkets" :key="coin.symbol">
            <el-card shadow="hover" class="crypto-card" :class="coin.change_24h >= 0 ? 'up' : 'down'">
              <div class="coin-header">
                <span class="coin-name">{{ coin.name }}</span>
                <el-tag size="small" type="info">{{ coin.base_currency }}</el-tag>
              </div>
              <div class="coin-price">{{ formatCryptoPrice(coin.last_price) }}</div>
              <div class="coin-change">{{ coin.change_24h >= 0 ? '+' : '' }}{{ coin.change_24h?.toFixed(2) }}%</div>
              <div class="coin-extra">
                <span>市值: {{ formatMoney(coin.market_cap) }}</span>
              </div>
              <div class="coin-extra">
                <span>24h量: {{ formatMoney(coin.volume_24h) }}</span>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- K线图表 -->
        <el-card shadow="hover" class="kline-card">
          <template #header>
            <div class="kline-header">
              <span>K线图表</span>
              <div>
                <el-select v-model="klineParams.symbol" style="width: 150px; margin-right: 8px" @change="fetchKlines">
                  <el-option v-for="coin in cryptoMarkets" :key="coin.symbol" :label="coin.symbol" :value="coin.symbol" />
                </el-select>
                <el-radio-group v-model="klineParams.interval" size="small" @change="fetchKlines">
                  <el-radio-button value="1m">1分</el-radio-button>
                  <el-radio-button value="5m">5分</el-radio-button>
                  <el-radio-button value="1h">1时</el-radio-button>
                  <el-radio-button value="1d">日线</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </template>
          <div ref="klineChartRef" style="height: 400px; width: 100%"></div>
        </el-card>

        <!-- 市场深度图 -->
        <el-card shadow="hover" class="depth-card">
          <template #header>市场深度（模拟）</template>
          <div ref="depthChartRef" style="height: 300px; width: 100%"></div>
        </el-card>
      </el-tab-pane>

      <!-- Tab 4: ETF 基金 -->
      <el-tab-pane label="ETF 基金" name="etf">
        <!-- 市场筛选 -->
        <el-card shadow="hover" class="filter-card">
          <el-form :inline="true">
            <el-form-item label="市场">
              <el-radio-group v-model="etfFilter.market" @change="fetchEtfList">
                <el-radio-button value="">全部</el-radio-button>
                <el-radio-button value="A">A股</el-radio-button>
                <el-radio-button value="HK">港股</el-radio-button>
                <el-radio-button value="US">美股</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- ETF 列表 -->
        <el-card shadow="hover" class="table-card">
          <template #header>ETF 基金列表 ({{ etfList.length }})</template>
          <el-table :data="etfList" stripe size="small">
            <el-table-column prop="symbol" label="代码" width="110" />
            <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="market" label="市场" width="70" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.market === 'A' ? '' : row.market === 'HK' ? 'warning' : 'success'">
                  {{ row.market }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="nav" label="净值" width="80" align="right">
              <template #default="{ row }">{{ row.nav?.toFixed(3) }}</template>
            </el-table-column>
            <el-table-column prop="price" label="市价" width="80" align="right">
              <template #default="{ row }">{{ row.price?.toFixed(3) }}</template>
            </el-table-column>
            <el-table-column prop="premium_rate" label="溢价率" width="90" align="right">
              <template #default="{ row }">
                <span :class="row.premium_rate >= 0 ? 'text-up' : 'text-down'">
                  {{ row.premium_rate >= 0 ? '+' : '' }}{{ row.premium_rate?.toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="total_assets" label="总资产(亿)" width="100" align="right">
              <template #default="{ row }">{{ row.total_assets }}</template>
            </el-table-column>
            <el-table-column prop="expense_ratio" label="费率" width="70" align="right">
              <template #default="{ row }">{{ row.expense_ratio }}%</template>
            </el-table-column>
            <el-table-column prop="tracking_index" label="跟踪指数" min-width="120" show-overflow-tooltip />
            <el-table-column label="操作" width="80" align="center" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="showEtfDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- ETF 详情对话框 -->
        <el-dialog v-model="etfDetailVisible" :title="etfDetail?.name || 'ETF 详情'" width="700px" destroy-on-close>
          <div v-if="etfDetail">
            <el-descriptions :column="2" border size="small" class="etf-desc">
              <el-descriptions-item label="代码">{{ etfDetail.symbol }}</el-descriptions-item>
              <el-descriptions-item label="市场">{{ etfDetail.market }}</el-descriptions-item>
              <el-descriptions-item label="净值">{{ etfDetail.nav?.toFixed(3) }}</el-descriptions-item>
              <el-descriptions-item label="市价">{{ etfDetail.price?.toFixed(3) }}</el-descriptions-item>
              <el-descriptions-item label="溢价率">{{ etfDetail.premium_rate?.toFixed(2) }}%</el-descriptions-item>
              <el-descriptions-item label="总资产(亿)">{{ etfDetail.total_assets }}</el-descriptions-item>
              <el-descriptions-item label="管理费率">{{ etfDetail.expense_ratio }}%</el-descriptions-item>
              <el-descriptions-item label="跟踪指数">{{ etfDetail.tracking_index }}</el-descriptions-item>
            </el-descriptions>

            <!-- 持仓分布饼图 -->
            <div class="chart-row">
              <div class="chart-half">
                <h4>前十大持仓</h4>
                <div ref="holdingsChartRef" style="height: 300px; width: 100%"></div>
              </div>
              <div class="chart-half">
                <h4>行业配置</h4>
                <div ref="sectorChartRef" style="height: 300px; width: 100%"></div>
              </div>
            </div>
          </div>
        </el-dialog>
      </el-tab-pane>

      <!-- Tab 5: 跨市场套利 -->
      <el-tab-pane label="跨市场套利" name="arbitrage">
        <!-- 套利机会列表 -->
        <el-card shadow="hover" class="table-card">
          <template #header>套利机会列表</template>
          <el-table :data="arbitrageList" stripe size="small">
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column label="标的A" min-width="110">
              <template #default="{ row }">{{ row.symbol_a }} ({{ row.market_a }})</template>
            </el-table-column>
            <el-table-column label="标的B" min-width="110">
              <template #default="{ row }">{{ row.symbol_b }} ({{ row.market_b }})</template>
            </el-table-column>
            <el-table-column prop="spread" label="价差" width="90" align="right">
              <template #default="{ row }">{{ row.spread?.toFixed(3) }}</template>
            </el-table-column>
            <el-table-column prop="spread_pct" label="价差%" width="90" align="right">
              <template #default="{ row }">
                <span :class="row.spread_pct >= 0 ? 'text-up' : 'text-down'">
                  {{ row.spread_pct >= 0 ? '+' : '' }}{{ row.spread_pct?.toFixed(3) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="z_score" label="Z-Score" width="90" align="right">
              <template #default="{ row }">
                <span :class="Math.abs(row.z_score || 0) > 1.5 ? 'text-up' : ''">
                  {{ row.z_score?.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="is_profitable" label="有利可图" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_profitable ? 'success' : 'info'" size="small">
                  {{ row.is_profitable ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="estimated_pnl" label="预估盈亏" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.estimated_pnl >= 0 ? 'text-up' : 'text-down'">
                  {{ row.estimated_pnl?.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" width="80" align="right">
              <template #default="{ row }">{{ row.confidence?.toFixed(1) }}%</template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 相关性热力图 -->
        <el-card shadow="hover" class="heatmap-card">
          <template #header>跨市场相关性热力图</template>
          <div ref="heatmapChartRef" style="height: 450px; width: 100%"></div>
        </el-card>

        <!-- 套利计算器 -->
        <el-card shadow="hover" class="calc-card">
          <template #header>套利盈亏计算器</template>
          <el-form :inline="true" :model="arbCalcForm" label-width="80px">
            <el-form-item label="标的A数量">
              <el-input-number v-model="arbCalcForm.quantity_a" :min="1" style="width: 130px" />
            </el-form-item>
            <el-form-item label="标的A价格">
              <el-input-number v-model="arbCalcForm.price_a" :min="0" :precision="2" style="width: 140px" />
            </el-form-item>
            <el-form-item label="标的B数量">
              <el-input-number v-model="arbCalcForm.quantity_b" :min="1" style="width: 130px" />
            </el-form-item>
            <el-form-item label="标的B价格">
              <el-input-number v-model="arbCalcForm.price_b" :min="0" :precision="2" style="width: 140px" />
            </el-form-item>
            <el-form-item label="手续费率">
              <el-input-number v-model="arbCalcForm.commission_rate" :min="0" :max="0.01" :step="0.0001" :precision="4" style="width: 140px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="calcArbitrage" :loading="arbCalcLoading">计算</el-button>
            </el-form-item>
          </el-form>
          <div v-if="arbCalcResult" class="arb-result">
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="标的A成本">{{ formatMoney(arbCalcResult.cost_a) }}</el-descriptions-item>
              <el-descriptions-item label="标的B成本">{{ formatMoney(arbCalcResult.cost_b) }}</el-descriptions-item>
              <el-descriptions-item label="总手续费">{{ formatMoney(arbCalcResult.total_commission) }}</el-descriptions-item>
              <el-descriptions-item label="价差">{{ formatMoney(arbCalcResult.spread) }}</el-descriptions-item>
              <el-descriptions-item label="盈亏">
                <span :class="arbCalcResult.pnl >= 0 ? 'text-up' : 'text-down'">
                  {{ formatMoney(arbCalcResult.pnl) }}
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="盈亏比例">
                <span :class="arbCalcResult.pnl_pct >= 0 ? 'text-up' : 'text-down'">
                  {{ arbCalcResult.pnl_pct >= 0 ? '+' : '' }}{{ arbCalcResult.pnl_pct }}%
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="是否盈利">
                <el-tag :type="arbCalcResult.is_profitable ? 'success' : 'danger'" size="small">
                  {{ arbCalcResult.is_profitable ? '盈利' : '亏损' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="风险等级">
                <el-tag :type="arbCalcResult.risk_level === 'low' ? 'success' : arbCalcResult.risk_level === 'medium' ? 'warning' : 'danger'" size="small">
                  {{ { low: '低', medium: '中', high: '高' }[arbCalcResult.risk_level] }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import {
  getFuturesContracts, calculateFuturesMargin,
  getCryptoMarkets, getCryptoKlines,
  getEtfList, getEtfDetail,
  getMarketStatus, getGlobalOverview,
  getArbitrageOpportunities, calculateArbitrage,
  getCrossMarketCorrelation
} from '@/api'

// ==================== 状态 ====================
const activeTab = ref('overview')
const loading = ref(false)

// Tab 1: 全球市场概览
const marketStatusList = ref([])
const globalIndices = ref([])
const arbitrageOpportunities = ref([])

// Tab 2: 期货市场
const futuresLoading = ref(false)
const futuresContracts = ref([])
const futuresFilter = reactive({ exchange: '', underlying: '' })
const marginLoading = ref(false)
const marginResult = ref(null)
const marginForm = reactive({ symbol: 'IF202606', quantity: 1, price: 3800, leverage: 1 })

// Tab 3: 加密货币
const cryptoMarkets = ref([])
const klineParams = reactive({ symbol: 'BTC/USDT', interval: '1h' })
const klineChartRef = ref(null)
const depthChartRef = ref(null)
let klineChart = null
let depthChart = null

// Tab 4: ETF
const etfFilter = reactive({ market: '' })
const etfList = ref([])
const etfDetailVisible = ref(false)
const etfDetail = ref(null)
const holdingsChartRef = ref(null)
const sectorChartRef = ref(null)
let holdingsChart = null
let sectorChart = null

// Tab 5: 跨市场套利
const arbitrageList = ref([])
const heatmapChartRef = ref(null)
let heatmapChart = null
const arbCalcLoading = ref(false)
const arbCalcResult = ref(null)
const arbCalcForm = reactive({ quantity_a: 100, price_a: 4.15, quantity_b: 100, price_b: 18.6, commission_rate: 0.001 })

// ==================== 工具函数 ====================
function getMarketLabel(market) {
  const map = { A: 'A股', HK: '港股', US: '美股', UK: '伦敦', JP: '日本', DE: '德国', CRYPTO: '加密货币' }
  return map[market] || market
}

function getStatusType(status) {
  const map = { open: 'success', closed: 'info', pre_market: 'warning', after_hours: 'warning' }
  return map[status] || 'info'
}

function getStatusLabel(status) {
  const map = { open: '交易中', closed: '已休市', pre_market: '盘前', after_hours: '盘后' }
  return map[status] || status
}

function formatNumber(num) {
  if (num == null) return '-'
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function formatMoney(num) {
  if (num == null) return '-'
  if (Math.abs(num) >= 1e8) return (num / 1e8).toFixed(2) + '亿'
  if (Math.abs(num) >= 1e4) return (num / 1e4).toFixed(2) + '万'
  return num.toFixed(2)
}

function formatVolume(num) {
  if (num == null) return '-'
  if (num >= 1e4) return (num / 1e4).toFixed(1) + '万'
  return num.toFixed(0)
}

function formatCryptoPrice(price) {
  if (price == null) return '-'
  if (price < 1) return '$' + price.toFixed(4)
  if (price < 100) return '$' + price.toFixed(2)
  return '$' + price.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

// ==================== Tab 切换 ====================
function onTabChange(tab) {
  nextTick(() => {
    if (tab === 'overview') loadOverview()
    else if (tab === 'futures') { fetchFuturesContracts(); initMarginDefaults() }
    else if (tab === 'crypto') { fetchCryptoMarkets(); fetchKlines(); renderDepthChart() }
    else if (tab === 'etf') fetchEtfList()
    else if (tab === 'arbitrage') { fetchArbitrageList(); fetchCorrelation() }
  })
}

// ==================== Tab 1: 全球市场概览 ====================
async function loadOverview() {
  loading.value = true
  try {
    const res = await getGlobalOverview()
    const data = res.data || res
    marketStatusList.value = data.market_status || []
    globalIndices.value = data.indices || []
    arbitrageOpportunities.value = data.arbitrage_opportunities || []
  } catch (e) {
    console.error('获取全球概览失败:', e)
  } finally {
    loading.value = false
  }
}

// ==================== Tab 2: 期货市场 ====================
async function fetchFuturesContracts() {
  futuresLoading.value = true
  try {
    const params = {}
    if (futuresFilter.exchange) params.exchange = futuresFilter.exchange
    if (futuresFilter.underlying) params.underlying = futuresFilter.underlying
    const res = await getFuturesContracts(params)
    futuresContracts.value = res.data?.contracts || res.contracts || []
  } catch (e) {
    console.error('获取期货合约失败:', e)
  } finally {
    futuresLoading.value = false
  }
}

function initMarginDefaults() {
  // 默认值已在 reactive 中设置
}

async function calcMargin() {
  marginLoading.value = true
  try {
    const res = await calculateFuturesMargin(marginForm)
    marginResult.value = res.data || res
  } catch (e) {
    console.error('计算保证金失败:', e)
  } finally {
    marginLoading.value = false
  }
}

// ==================== Tab 3: 加密货币 ====================
async function fetchCryptoMarkets() {
  try {
    const res = await getCryptoMarkets()
    cryptoMarkets.value = res.data?.markets || res.markets || []
    if (cryptoMarkets.value.length > 0 && !klineParams.symbol) {
      klineParams.symbol = cryptoMarkets.value[0].symbol
    }
  } catch (e) {
    console.error('获取加密货币市场失败:', e)
  }
}

async function fetchKlines() {
  try {
    const res = await getCryptoKlines(klineParams.symbol, { interval: klineParams.interval, limit: 100 })
    const klines = res.data?.klines || res.klines || []
    renderKlineChart(klines)
  } catch (e) {
    console.error('获取K线失败:', e)
  }
}

function renderKlineChart(klines) {
  if (!klineChartRef.value) return
  if (!klineChart) klineChart = echarts.init(klineChartRef.value)
  const dates = klines.map(k => k.datetime)
  const ohlc = klines.map(k => [k.open, k.close, k.low, k.high])
  const volumes = klines.map(k => k.volume)

  klineChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', '成交量'] },
    grid: [{ left: '8%', right: '3%', top: '10%', height: '55%' }, { left: '8%', right: '3%', top: '72%', height: '18%' }],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, axisLabel: { fontSize: 10 } },
      { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } }
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitArea: { show: true } },
      { scale: true, gridIndex: 1, splitNumber: 2 }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: '2%' }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: { color: '#ef232a', color0: '#14b143', borderColor: '#ef232a', borderColor0: '#14b143' }
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: '#5793f3' }
      }
    ]
  }, true)
}

function renderDepthChart() {
  if (!depthChartRef.value) return
  if (!depthChart) depthChart = echarts.init(depthChartRef.value)

  // 模拟买卖盘深度数据
  const bids = []
  const asks = []
  let bidPrice = 67000
  let askPrice = 67050
  for (let i = 0; i < 20; i++) {
    bids.push([bidPrice, Math.round(Math.random() * 50 + 5)])
    asks.push([askPrice, Math.round(Math.random() * 50 + 5)])
    bidPrice -= 50
    askPrice += 50
  }

  depthChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['买单', '卖单'] },
    grid: { left: '8%', right: '3%', top: '10%', bottom: '10%' },
    xAxis: { type: 'category', data: [...bids.map(b => b[0]), ...asks.map(a => a[0])], axisLabel: { fontSize: 10, rotate: 45 } },
    yAxis: { type: 'value', name: '数量' },
    series: [
      { name: '买单', type: 'bar', data: [...bids.map(b => b[1]), ...Array(asks.length).fill(null)], itemStyle: { color: '#14b143' } },
      { name: '卖单', type: 'bar', data: [...Array(bids.length).fill(null), ...asks.map(a => a[1])], itemStyle: { color: '#ef232a' } }
    ]
  }, true)
}

// ==================== Tab 4: ETF ====================
async function fetchEtfList() {
  try {
    const params = {}
    if (etfFilter.market) params.market = etfFilter.market
    const res = await getEtfList(params)
    etfList.value = res.data?.etfs || res.etfs || []
  } catch (e) {
    console.error('获取ETF列表失败:', e)
  }
}

async function showEtfDetail(row) {
  try {
    const res = await getEtfDetail(row.symbol, { market: row.market })
    etfDetail.value = res.data || res
    etfDetailVisible.value = true
    await nextTick()
    renderHoldingsChart()
    renderSectorChart()
  } catch (e) {
    console.error('获取ETF详情失败:', e)
  }
}

function renderHoldingsChart() {
  if (!holdingsChartRef.value || !etfDetail.value?.top_holdings) return
  if (holdingsChart) holdingsChart.dispose()
  holdingsChart = echarts.init(holdingsChartRef.value)

  const data = etfDetail.value.top_holdings.map(h => ({ name: h.name, value: h.weight }))

  holdingsChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}% ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      data,
      label: { formatter: '{b}\n{c}%', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
    }]
  })
}

function renderSectorChart() {
  if (!sectorChartRef.value || !etfDetail.value?.sector_allocation) return
  if (sectorChart) sectorChart.dispose()
  sectorChart = echarts.init(sectorChartRef.value)

  const alloc = etfDetail.value.sector_allocation
  const categories = Object.keys(alloc)
  const values = Object.values(alloc)

  sectorChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '5%', top: '10%', bottom: '5%', containLabel: true },
    xAxis: { type: 'category', data: categories, axisLabel: { fontSize: 11, rotate: 30 } },
    yAxis: { type: 'value', name: '占比(%)' },
    series: [{
      type: 'bar',
      data: values,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#409EFF' },
          { offset: 1, color: '#79bbff' }
        ])
      },
      label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11 }
    }]
  })
}

// ==================== Tab 5: 跨市场套利 ====================
async function fetchArbitrageList() {
  try {
    const res = await getArbitrageOpportunities()
    arbitrageList.value = res.data?.opportunities || res.opportunities || []
  } catch (e) {
    console.error('获取套利机会失败:', e)
  }
}

async function fetchCorrelation() {
  try {
    const res = await getCrossMarketCorrelation({ period: '30d' })
    const data = res.data || res
    renderHeatmap(data)
  } catch (e) {
    console.error('获取相关性矩阵失败:', e)
  }
}

function renderHeatmap(data) {
  if (!heatmapChartRef.value || !data?.matrix) return
  if (heatmapChart) heatmapChart.dispose()
  heatmapChart = echarts.init(heatmapChartRef.value)

  const symbols = data.symbols || []
  const matrix = data.matrix || []
  const heatData = []
  for (let i = 0; i < matrix.length; i++) {
    for (let j = 0; j < matrix[i].length; j++) {
      heatData.push([i, j, matrix[i][j]])
    }
  }

  heatmapChart.setOption({
    tooltip: {
      formatter: (p) => `${symbols[p.data[0]]} vs ${symbols[p.data[1]]}: ${p.data[2].toFixed(3)}`
    },
    grid: { left: '12%', right: '8%', top: '5%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: symbols,
      axisLabel: { fontSize: 10, rotate: 45 },
      splitArea: { show: true }
    },
    yAxis: {
      type: 'category',
      data: symbols,
      axisLabel: { fontSize: 10 },
      splitArea: { show: true }
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: { color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'] }
    },
    series: [{
      type: 'heatmap',
      data: heatData,
      label: { show: true, formatter: (p) => p.data[2].toFixed(2), fontSize: 9 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
    }]
  })
}

async function calcArbitrage() {
  arbCalcLoading.value = true
  try {
    const res = await calculateArbitrage(arbCalcForm)
    arbCalcResult.value = res.data || res
  } catch (e) {
    console.error('计算套利盈亏失败:', e)
  } finally {
    arbCalcLoading.value = false
  }
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadOverview()
})

// 监听 ETF 详情对话框关闭时销毁图表
watch(etfDetailVisible, (val) => {
  if (!val) {
    if (holdingsChart) { holdingsChart.dispose(); holdingsChart = null }
    if (sectorChart) { sectorChart.dispose(); sectorChart = null }
  }
})
</script>

<style lang="scss" scoped>
.multi-market-view {
  .page-header {
    margin-bottom: 16px;
    h2 {
      margin: 0;
      font-size: 20px;
      color: #303133;
    }
  }

  .filter-card, .table-card, .calc-card, .indices-card,
  .arbitrage-overview-card, .kline-card, .depth-card, .heatmap-card {
    margin-bottom: 16px;
  }

  // 涨跌颜色
  .text-up { color: #ef232a; }
  .text-down { color: #14b143; }

  // Tab 1: 市场状态卡片
  .market-status-row {
    margin-bottom: 16px;
  }
  .market-status-card {
    text-align: center;
    padding: 8px;
    cursor: default;
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin: 0 auto 6px;
      &.dot-open { background: #14b143; box-shadow: 0 0 6px #14b143; }
      &.dot-closed { background: #909399; }
      &.dot-pre_market, &.dot-after_hours { background: #e6a23c; box-shadow: 0 0 6px #e6a23c; }
    }
    .market-name { font-size: 14px; font-weight: 500; margin-bottom: 2px; }
    .market-timezone { font-size: 11px; color: #909399; margin-bottom: 2px; }
    .market-time { font-size: 12px; color: #606266; margin-bottom: 4px; }
  }

  // Tab 1: 指数卡片
  .index-card {
    padding: 12px;
    margin-bottom: 8px;
    border-radius: 6px;
    background: #f5f7fa;
    &.up { border-left: 3px solid #ef232a; }
    &.down { border-left: 3px solid #14b143; }
    .index-name { font-size: 13px; font-weight: 500; }
    .index-market { font-size: 11px; color: #909399; }
    .index-price { font-size: 18px; font-weight: 600; margin: 4px 0; }
    .index-change { font-size: 13px; font-weight: 500; }
    .index-change.text-up { color: #ef232a; }
    .index-change.text-down { color: #14b143; }
  }

  // Tab 3: 加密货币卡片
  .crypto-cards { margin-bottom: 16px; }
  .crypto-card {
    margin-bottom: 8px;
    &.up { border-top: 2px solid #ef232a; }
    &.down { border-top: 2px solid #14b143; }
    .coin-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .coin-name { font-size: 14px; font-weight: 500; }
    .coin-price { font-size: 20px; font-weight: 600; margin: 4px 0; }
    .coin-change { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
    .coin-extra { font-size: 11px; color: #909399; }
  }

  // K线头部
  .kline-header, .chain-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  // 保证金/套利计算结果
  .margin-result, .arb-result {
    margin-top: 12px;
    padding: 12px;
    background: #f5f7fa;
    border-radius: 6px;
  }

  // ETF 详情
  .etf-desc { margin-bottom: 16px; }
  .chart-row {
    display: flex;
    gap: 16px;
    .chart-half { flex: 1; h4 { margin: 0 0 8px; font-size: 14px; color: #303133; } }
  }
}
</style>
