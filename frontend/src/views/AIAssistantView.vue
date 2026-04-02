<template>
  <div class="ai-assistant-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>AI 智能分析助手</h2>
      <el-tag type="success" effect="dark" size="small">V1.5</el-tag>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- ==================== Tab 1: AI 对话 ==================== -->
      <el-tab-pane label="AI 对话" name="chat">
        <div class="chat-container">
          <!-- 左侧：历史会话列表 -->
          <div class="chat-sidebar">
            <div class="sidebar-header">
              <span>历史会话</span>
              <el-button type="primary" size="small" :icon="Plus" @click="createNewSession">新建</el-button>
            </div>
            <el-scrollbar class="session-list">
              <div
                v-for="session in sessions"
                :key="session.id"
                class="session-item"
                :class="{ active: currentSessionId === session.id }"
                @click="switchSession(session)"
              >
                <div class="session-title">{{ session.title || '新会话' }}</div>
                <div class="session-time">{{ formatDate(session.created_at) }}</div>
                <el-button
                  class="session-delete"
                  type="danger"
                  :icon="Delete"
                  size="small"
                  circle
                  plain
                  @click.stop="handleDeleteSession(session.id)"
                />
              </div>
              <el-empty v-if="sessions.length === 0" description="暂无会话" :image-size="60" />
            </el-scrollbar>
          </div>

          <!-- 右侧：聊天窗口 -->
          <div class="chat-main">
            <el-scrollbar ref="chatScrollbarRef" class="chat-messages">
              <div v-if="currentMessages.length === 0" class="chat-placeholder">
                <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
                <p>向 AI 助手提问，开始智能分析</p>
                <div class="quick-questions">
                  <el-button
                    v-for="q in quickQuestions"
                    :key="q"
                    size="small"
                    round
                    @click="sendQuickQuestion(q)"
                  >{{ q }}</el-button>
                </div>
              </div>
              <div
                v-for="(msg, idx) in currentMessages"
                :key="idx"
                class="message-item"
                :class="msg.role"
              >
                <div class="message-avatar">
                  <el-avatar v-if="msg.role === 'user'" :size="32" style="background-color: #409EFF;">U</el-avatar>
                  <el-avatar v-else :size="32" style="background-color: #67C23A;">AI</el-avatar>
                </div>
                <div class="message-content">
                  <div class="message-bubble" v-html="renderMarkdown(msg.content)"></div>
                  <div class="message-time">{{ msg.timestamp || '' }}</div>
                </div>
              </div>
              <!-- AI 正在输入 -->
              <div v-if="chatLoading" class="message-item assistant">
                <div class="message-avatar">
                  <el-avatar :size="32" style="background-color: #67C23A;">AI</el-avatar>
                </div>
                <div class="message-content">
                  <div class="message-bubble typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </div>
            </el-scrollbar>
            <!-- 输入区域 -->
            <div class="chat-input-area">
              <el-input
                v-model="chatInput"
                type="textarea"
                :rows="2"
                placeholder="输入问题，按 Enter 发送，Shift+Enter 换行..."
                resize="none"
                @keydown="handleChatKeydown"
              />
              <el-button
                type="primary"
                :icon="Promotion"
                :loading="chatLoading"
                :disabled="!chatInput.trim()"
                @click="sendMessage"
              >发送</el-button>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ==================== Tab 2: 市场情绪 ==================== -->
      <el-tab-pane label="市场情绪" name="sentiment">
        <!-- 市场选择 -->
        <div class="sentiment-toolbar">
          <el-radio-group v-model="sentimentMarket" @change="loadSentimentData">
            <el-radio-button value="A">A股</el-radio-button>
            <el-radio-button value="HK">港股</el-radio-button>
            <el-radio-button value="US">美股</el-radio-button>
          </el-radio-group>
          <el-button type="primary" :loading="sentimentLoading" @click="runSentimentAnalysis">
            <el-icon><DataAnalysis /></el-icon>分析
          </el-button>
        </div>

        <el-row :gutter="16">
          <!-- 情绪仪表盘 -->
          <el-col :span="8">
            <el-card shadow="hover" class="sentiment-card">
              <template #header>
                <div class="card-header"><span>情绪仪表盘</span></div>
              </template>
              <div ref="gaugeChartRef" style="height: 260px;"></div>
              <div class="sentiment-label-row">
                <el-tag :type="sentimentTagType" size="large" effect="dark">
                  {{ sentimentLabelText }}
                </el-tag>
                <span class="sentiment-score">分数: {{ sentimentScore.toFixed(2) }}</span>
              </div>
            </el-card>
          </el-col>

          <!-- 新闻情绪分布 -->
          <el-col :span="8">
            <el-card shadow="hover" class="sentiment-card">
              <template #header>
                <div class="card-header"><span>新闻情绪分布</span></div>
              </template>
              <div ref="pieChartRef" style="height: 260px;"></div>
            </el-card>
          </el-col>

          <!-- 关键因素 -->
          <el-col :span="8">
            <el-card shadow="hover" class="sentiment-card">
              <template #header>
                <div class="card-header"><span>关键因素</span></div>
              </template>
              <el-scrollbar style="max-height: 300px;">
                <div class="factor-list">
                  <div
                    v-for="(factor, idx) in sentimentFactors"
                    :key="idx"
                    class="factor-item"
                    :class="factor.type"
                  >
                    <el-icon v-if="factor.type === 'positive'" color="#67C23A"><Top /></el-icon>
                    <el-icon v-else color="#F56C6C"><Bottom /></el-icon>
                    <span>{{ factor.text }}</span>
                  </div>
                  <el-empty v-if="sentimentFactors.length === 0" description="暂无数据" :image-size="40" />
                </div>
              </el-scrollbar>
            </el-card>
          </el-col>
        </el-row>

        <!-- 情绪趋势图 -->
        <el-card shadow="hover" style="margin-top: 16px;">
          <template #header>
            <div class="card-header"><span>情绪趋势（近30天）</span></div>
          </template>
          <div ref="trendChartRef" style="height: 320px;"></div>
        </el-card>
      </el-tab-pane>

      <!-- ==================== Tab 3: 异常检测 ==================== -->
      <el-tab-pane label="异常检测" name="anomaly">
        <!-- 搜索栏 -->
        <div class="anomaly-toolbar">
          <el-form :inline="true" :model="anomalyForm">
            <el-form-item label="股票代码">
              <el-input v-model="anomalyForm.symbol" placeholder="如 600519" clearable style="width: 140px;" />
            </el-form-item>
            <el-form-item label="市场">
              <el-select v-model="anomalyForm.market" style="width: 100px;">
                <el-option label="A股" value="A" />
                <el-option label="港股" value="HK" />
                <el-option label="美股" value="US" />
              </el-select>
            </el-form-item>
            <el-form-item label="检测天数">
              <el-input-number v-model="anomalyForm.days" :min="1" :max="90" style="width: 120px;" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="anomalyLoading" @click="runAnomalyDetection">
                开始检测
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <!-- 统计卡片 -->
        <el-row :gutter="16" style="margin-bottom: 16px;">
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-title">今日检测数</div>
              <div class="stat-value">{{ anomalyStats.total }}</div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-title">异常数</div>
              <div class="stat-value anomaly-count">{{ anomalyStats.anomalies }}</div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-title">严重数</div>
              <div class="stat-value critical-count">{{ anomalyStats.critical }}</div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 异常列表 -->
        <el-card shadow="hover">
          <template #header>
            <div class="card-header"><span>异常交易记录</span></div>
          </template>
          <el-table
            :data="anomalyRecords"
            v-loading="anomalyLoading"
            stripe
            style="width: 100%"
            @row-click="showAnomalyDetail"
          >
            <el-table-column prop="symbol" label="股票代码" width="120" />
            <el-table-column prop="anomaly_type" label="异常类型" width="140">
              <template #default="{ row }">
                <el-tag size="small">{{ anomalyTypeLabel(row.anomaly_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="severity" label="严重程度" width="110">
              <template #default="{ row }">
                <el-tag :type="severityTagType(row.severity)" size="small" effect="dark">
                  {{ severityLabel(row.severity) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
            <el-table-column label="检测时间" width="170">
              <template #default="{ row }">{{ formatDate(row.detected_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 异常详情对话框 -->
        <el-dialog v-model="anomalyDetailVisible" title="异常详情" width="600px" destroy-on-close>
          <template v-if="selectedAnomaly">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="股票代码">{{ selectedAnomaly.symbol }}</el-descriptions-item>
              <el-descriptions-item label="异常类型">
                <el-tag size="small">{{ anomalyTypeLabel(selectedAnomaly.anomaly_type) }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="严重程度">
                <el-tag :type="severityTagType(selectedAnomaly.severity)" size="small" effect="dark">
                  {{ severityLabel(selectedAnomaly.severity) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="描述">{{ selectedAnomaly.description }}</el-descriptions-item>
              <el-descriptions-item label="检测时间">{{ formatDate(selectedAnomaly.detected_at) }}</el-descriptions-item>
              <el-descriptions-item label="详细信息" v-if="selectedAnomaly.details">
                <pre class="detail-pre">{{ selectedAnomaly.details }}</pre>
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ==================== Tab 4: 策略归因 ==================== -->
      <el-tab-pane label="策略归因" name="attribution">
        <div class="attribution-toolbar">
          <el-form :inline="true" :model="attributionForm">
            <el-form-item label="策略选择">
              <el-select v-model="attributionForm.strategy_id" placeholder="请选择策略" style="width: 200px;">
                <el-option
                  v-for="s in strategyOptions"
                  :key="s.value"
                  :label="s.label"
                  :value="s.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="attributionLoading" @click="runAttributionAnalysis">
                开始分析
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <template v-if="attributionResult">
          <!-- 指标卡片 -->
          <el-row :gutter="16" style="margin-bottom: 16px;">
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-title">择时能力评分</div>
                <div class="stat-value">{{ attributionResult.timing_score || '-' }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-title">年化波动率</div>
                <div class="stat-value">{{ attributionResult.volatility || '-' }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-title">Sortino 比率</div>
                <div class="stat-value">{{ attributionResult.sortino || '-' }}</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-title">Calmar 比率</div>
                <div class="stat-value">{{ attributionResult.calmar || '-' }}</div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 综合评级 -->
          <el-card shadow="hover" style="margin-bottom: 16px;">
            <div class="rating-row">
              <span class="rating-label">综合评级：</span>
              <el-tag
                :type="ratingTagType(attributionResult.overall_rating)"
                size="large"
                effect="dark"
              >{{ attributionResult.overall_rating || '-' }}</el-tag>
            </div>
          </el-card>

          <!-- 图表区域 -->
          <el-row :gutter="16" style="margin-bottom: 16px;">
            <el-col :span="12">
              <el-card shadow="hover">
                <template #header>
                  <div class="card-header"><span>收益分解</span></div>
                </template>
                <div ref="returnPieRef" style="height: 320px;"></div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="hover">
                <template #header>
                  <div class="card-header"><span>行业贡献</span></div>
                </template>
                <div ref="sectorBarRef" style="height: 320px;"></div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 改进建议 -->
          <el-card shadow="hover">
            <template #header>
              <div class="card-header"><span>改进建议</span></div>
            </template>
            <el-timeline>
              <el-timeline-item
                v-for="(tip, idx) in attributionResult.suggestions || []"
                :key="idx"
                :icon="EditPen"
                placement="top"
                type="primary"
              >
                <el-card shadow="never" class="suggestion-card">
                  <p>{{ tip }}</p>
                </el-card>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-if="!attributionResult.suggestions?.length" description="暂无建议" :image-size="40" />
          </el-card>
        </template>

        <el-empty v-else description="请选择策略并开始分析" :image-size="100" />
      </el-tab-pane>

      <!-- ==================== Tab 5: 策略建议 ==================== -->
      <el-tab-pane label="策略建议" name="advice">
        <div class="advice-toolbar">
          <el-form :inline="true" :model="adviceForm">
            <el-form-item label="市场">
              <el-select v-model="adviceForm.market" style="width: 120px;">
                <el-option label="A股" value="A" />
                <el-option label="港股" value="HK" />
                <el-option label="美股" value="US" />
              </el-select>
            </el-form-item>
            <el-form-item label="风险等级">
              <el-select v-model="adviceForm.risk_level" style="width: 120px;">
                <el-option label="保守" value="conservative" />
                <el-option label="稳健" value="moderate" />
                <el-option label="激进" value="aggressive" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="adviceLoading" @click="fetchAdvice">
                获取建议
              </el-button>
            </el-form-item>
          </el-form>
        </div>

        <div v-if="adviceList.length > 0" class="advice-list">
          <el-card
            v-for="(item, idx) in adviceList"
            :key="idx"
            shadow="hover"
            class="advice-card"
          >
            <template #header>
              <div class="advice-card-header">
                <span class="advice-title">{{ item.title }}</span>
                <el-tag :type="riskLevelTagType(item.risk_level)" size="small">{{ riskLevelLabel(item.risk_level) }}</el-tag>
              </div>
            </template>
            <div class="advice-body">
              <p class="advice-content">{{ item.content }}</p>
              <el-alert
                v-if="item.risk_warning"
                :title="item.risk_warning"
                type="warning"
                show-icon
                :closable="false"
                style="margin-bottom: 12px;"
              />
              <div class="advice-actions">
                <span class="actions-label">建议操作：</span>
                <el-tag
                  v-for="(action, aIdx) in item.actions || []"
                  :key="aIdx"
                  size="small"
                  type="info"
                  style="margin: 2px 4px;"
                >{{ action }}</el-tag>
              </div>
            </div>
          </el-card>
        </div>
        <el-empty v-else description="请选择条件并获取建议" :image-size="100" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete, Promotion, ChatDotRound, DataAnalysis, Top, Bottom, EditPen } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  aiChat, getAIChatSessions, getAIChatSession, deleteAIChatSession,
  analyzeSentiment, getSentimentHistory,
  detectAnomalies, getAnomalyRecords,
  analyzeAttribution, getStrategyAdvice
} from '@/api'

// ========== Tab 状态 ==========
const activeTab = ref('chat')

// ========== Tab 1: AI 对话 ==========
const sessions = ref([])
const currentSessionId = ref(null)
const currentMessages = ref([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatScrollbarRef = ref(null)

const quickQuestions = [
  '当前市场整体趋势如何？',
  '帮我分析一下持仓风险',
  '最近有哪些异常交易信号？',
  '推荐适合当前行情的策略'
]

async function loadSessions() {
  try {
    const res = await getAIChatSessions()
    sessions.value = res.data?.items || res.data || []
    if (sessions.value.length > 0 && !currentSessionId.value) {
      await switchSession(sessions.value[0])
    }
  } catch (e) {
    // 静默处理
  }
}

async function createNewSession() {
  currentSessionId.value = null
  currentMessages.value = []
}

async function switchSession(session) {
  currentSessionId.value = session.id
  try {
    const res = await getAIChatSession(session.id)
    currentMessages.value = res.data?.messages || []
  } catch (e) {
    currentMessages.value = []
  }
}

async function handleDeleteSession(sessionId) {
  try {
    await deleteAIChatSession(sessionId)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
      currentMessages.value = []
      if (sessions.value.length > 0) {
        await switchSession(sessions.value[0])
      }
    }
    ElMessage.success('会话已删除')
  } catch (e) {
    ElMessage.error('删除会话失败')
  }
}

function handleChatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function sendQuickQuestion(q) {
  chatInput.value = q
  sendMessage()
}

async function sendMessage() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value) return

  // 添加用户消息
  currentMessages.value.push({
    role: 'user',
    content: text,
    timestamp: new Date().toLocaleTimeString('zh-CN')
  })
  chatInput.value = ''
  chatLoading.value = true

  await nextTick()
  scrollToBottom()

  try {
    const res = await aiChat({
      session_id: currentSessionId.value,
      message: text
    })
    const reply = res.data?.reply || res.data?.message || '暂无回复'
    const sessionId = res.data?.session_id

    if (sessionId && !currentSessionId.value) {
      currentSessionId.value = sessionId
      await loadSessions()
    }

    currentMessages.value.push({
      role: 'assistant',
      content: reply,
      timestamp: new Date().toLocaleTimeString('zh-CN')
    })
  } catch (e) {
    currentMessages.value.push({
      role: 'assistant',
      content: '抱歉，请求失败，请稍后重试。',
      timestamp: new Date().toLocaleTimeString('zh-CN')
    })
  } finally {
    chatLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  const scrollbar = chatScrollbarRef.value
  if (scrollbar) {
    scrollbar.setScrollTop(99999)
  }
}

// 简单 Markdown 渲染
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    // 代码块
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="md-code-block"><code>$2</code></pre>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
    // 粗体
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 无序列表
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    // 有序列表
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // 标题
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    // 换行
    .replace(/\n/g, '<br/>')

  // 包裹列表
  html = html.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>')
  // 合并相邻的 ul
  html = html.replace(/<\/ul>\s*<ul>/g, '')
  return html
}

// ========== Tab 2: 市场情绪 ==========
const sentimentMarket = ref('A')
const sentimentLoading = ref(false)
const sentimentScore = ref(0)
const sentimentFactors = ref([])
const gaugeChartRef = ref(null)
const pieChartRef = ref(null)
const trendChartRef = ref(null)
let gaugeChart = null
let pieChart = null
let trendChart = null

const sentimentTagType = ref('info')
const sentimentLabelText = ref('中性')

function updateSentimentLabel(score) {
  if (score > 0.3) {
    sentimentTagType.value = 'success'
    sentimentLabelText.value = '看涨'
  } else if (score > 0.1) {
    sentimentTagType.value = ''
    sentimentLabelText.value = '偏乐观'
  } else if (score > -0.1) {
    sentimentTagType.value = 'info'
    sentimentLabelText.value = '中性'
  } else if (score > -0.3) {
    sentimentTagType.value = 'warning'
    sentimentLabelText.value = '偏悲观'
  } else {
    sentimentTagType.value = 'danger'
    sentimentLabelText.value = '看跌'
  }
}

async function runSentimentAnalysis() {
  sentimentLoading.value = true
  try {
    const res = await analyzeSentiment({ market: sentimentMarket.value })
    const data = res.data || {}
    sentimentScore.value = data.score ?? 0
    updateSentimentLabel(sentimentScore.value)
    sentimentFactors.value = data.factors || []
    await nextTick()
    initGaugeChart()
    initPieChart(data.news_distribution)
  } catch (e) {
    ElMessage.error('情绪分析失败')
  } finally {
    sentimentLoading.value = false
  }
}

async function loadSentimentData() {
  try {
    const res = await getSentimentHistory({ market: sentimentMarket.value })
    const data = res.data || {}
    sentimentScore.value = data.current_score ?? 0
    updateSentimentLabel(sentimentScore.value)
    sentimentFactors.value = data.factors || []
    await nextTick()
    initGaugeChart()
    initPieChart(data.news_distribution)
    initTrendChart(data.history)
  } catch (e) {
    // 静默处理
  }
}

function initGaugeChart() {
  if (!gaugeChartRef.value) return
  if (gaugeChart) gaugeChart.dispose()
  gaugeChart = echarts.init(gaugeChartRef.value)
  gaugeChart.setOption({
    series: [{
      type: 'gauge',
      min: -1,
      max: 1,
      splitNumber: 10,
      axisLine: {
        lineStyle: {
          width: 20,
          color: [
            [0.3, '#F56C6C'],
            [0.45, '#E6A23C'],
            [0.55, '#909399'],
            [0.7, '#67C23A'],
            [1, '#409EFF']
          ]
        }
      },
      pointer: { width: 5 },
      axisTick: { length: 8, lineStyle: { color: 'auto' } },
      splitLine: { length: 15, lineStyle: { color: 'auto' } },
      axisLabel: { distance: 20, color: '#666', fontSize: 12 },
      detail: {
        valueAnimation: true,
        formatter: '{value}',
        fontSize: 24,
        offsetCenter: [0, '70%']
      },
      data: [{ value: sentimentScore.value, name: '情绪指数' }]
    }]
  })
}

function initPieChart(distribution) {
  if (!pieChartRef.value) return
  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(pieChartRef.value)
  const positive = distribution?.positive || 0
  const negative = distribution?.negative || 0
  const neutral = distribution?.neutral || 0
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, data: ['正面', '负面', '中性'] },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{d}%' },
      data: [
        { value: positive, name: '正面', itemStyle: { color: '#67C23A' } },
        { value: negative, name: '负面', itemStyle: { color: '#F56C6C' } },
        { value: neutral, name: '中性', itemStyle: { color: '#909399' } }
      ]
    }]
  })
}

function initTrendChart(history) {
  if (!trendChartRef.value) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value)
  const dates = (history || []).map(h => h.date)
  const scores = (history || []).map(h => h.score)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: {
      type: 'value',
      min: -1,
      max: 1,
      axisLabel: { formatter: '{value}' }
    },
    series: [{
      name: '情绪分数',
      type: 'line',
      data: scores,
      smooth: true,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64,158,255,0.3)' },
          { offset: 1, color: 'rgba(64,158,255,0.02)' }
        ])
      },
      lineStyle: { color: '#409EFF', width: 2 },
      itemStyle: { color: '#409EFF' },
      markLine: {
        silent: true,
        data: [
          { yAxis: 0, lineStyle: { color: '#909399', type: 'dashed' }, label: { formatter: '中性线' } }
        ]
      }
    }]
  })
}

// ========== Tab 3: 异常检测 ==========
const anomalyForm = reactive({
  symbol: '',
  market: 'A',
  days: 7
})
const anomalyLoading = ref(false)
const anomalyRecords = ref([])
const anomalyStats = reactive({
  total: 0,
  anomalies: 0,
  critical: 0
})
const anomalyDetailVisible = ref(false)
const selectedAnomaly = ref(null)

async function runAnomalyDetection() {
  anomalyLoading.value = true
  try {
    const res = await detectAnomalies({
      symbol: anomalyForm.symbol,
      market: anomalyForm.market,
      days: anomalyForm.days
    })
    const data = res.data || {}
    anomalyRecords.value = data.records || []
    anomalyStats.total = data.total_checked || 0
    anomalyStats.anomalies = data.anomaly_count || 0
    anomalyStats.critical = data.critical_count || 0
    ElMessage.success(`检测完成，发现 ${anomalyStats.anomalies} 条异常`)
  } catch (e) {
    ElMessage.error('异常检测失败')
  } finally {
    anomalyLoading.value = false
  }
}

function showAnomalyDetail(row) {
  selectedAnomaly.value = row
  anomalyDetailVisible.value = true
}

function anomalyTypeLabel(type) {
  const map = {
    volume_spike: '成交量异常',
    price_jump: '价格跳变',
    unusual_pattern: '异常形态',
    insider_trading: '疑似内幕',
    wash_trade: '疑似洗盘',
    pump_dump: '疑似拉抬'
  }
  return map[type] || type || '-'
}

function severityTagType(s) {
  const map = { critical: 'danger', high: 'warning', medium: '', low: 'info' }
  return map[s] || 'info'
}

function severityLabel(s) {
  const map = { critical: '严重', high: '高', medium: '中', low: '低' }
  return map[s] || s || '-'
}

// ========== Tab 4: 策略归因 ==========
const attributionForm = reactive({
  strategy_id: ''
})
const attributionLoading = ref(false)
const attributionResult = ref(null)
const strategyOptions = ref([
  { label: '均线交叉策略', value: 'ma_cross' },
  { label: '动量策略', value: 'momentum' },
  { label: '均值回归策略', value: 'mean_reversion' },
  { label: '多因子策略', value: 'multi_factor' },
  { label: '机器学习策略', value: 'ml_strategy' }
])
const returnPieRef = ref(null)
const sectorBarRef = ref(null)
let returnPieChart = null
let sectorBarChart = null

async function runAttributionAnalysis() {
  if (!attributionForm.strategy_id) {
    ElMessage.warning('请选择策略')
    return
  }
  attributionLoading.value = true
  try {
    const res = await analyzeAttribution({ strategy_id: attributionForm.strategy_id })
    attributionResult.value = res.data || {}
    await nextTick()
    initReturnPieChart()
    initSectorBarChart()
  } catch (e) {
    ElMessage.error('归因分析失败')
  } finally {
    attributionLoading.value = false
  }
}

function ratingTagType(rating) {
  const map = { A: 'success', B: '', C: 'warning', D: 'danger' }
  return map[rating] || 'info'
}

function initReturnPieChart() {
  if (!returnPieRef.value || !attributionResult.value) return
  if (returnPieChart) returnPieChart.dispose()
  returnPieChart = echarts.init(returnPieRef.value)
  const rd = attributionResult.value.return_decomposition || {}
  returnPieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}% ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}%' },
      data: [
        { value: rd.alpha || 0, name: 'Alpha 收益', itemStyle: { color: '#409EFF' } },
        { value: rd.beta || 0, name: 'Beta 收益', itemStyle: { color: '#67C23A' } },
        { value: rd.timing || 0, name: '择时收益', itemStyle: { color: '#E6A23C' } }
      ]
    }]
  })
}

function initSectorBarChart() {
  if (!sectorBarRef.value || !attributionResult.value) return
  if (sectorBarChart) sectorBarChart.dispose()
  sectorBarChart = echarts.init(sectorBarRef.value)
  const sectors = attributionResult.value.sector_contribution || []
  sectorBarChart.setOption({
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    grid: { left: 80, right: 30, top: 20, bottom: 40 },
    xAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    yAxis: {
      type: 'category',
      data: sectors.map(s => s.sector),
      inverse: true
    },
    series: [{
      type: 'bar',
      data: sectors.map(s => ({
        value: s.contribution,
        itemStyle: { color: s.contribution >= 0 ? '#67C23A' : '#F56C6C' }
      })),
      barWidth: 20,
      itemStyle: { borderRadius: [0, 4, 4, 0] }
    }]
  })
}

// ========== Tab 5: 策略建议 ==========
const adviceForm = reactive({
  market: 'A',
  risk_level: 'moderate'
})
const adviceLoading = ref(false)
const adviceList = ref([])

async function fetchAdvice() {
  adviceLoading.value = true
  try {
    const res = await getStrategyAdvice({
      market: adviceForm.market,
      risk_level: adviceForm.risk_level
    })
    adviceList.value = res.data?.advices || res.data || []
  } catch (e) {
    ElMessage.error('获取建议失败')
  } finally {
    adviceLoading.value = false
  }
}

function riskLevelTagType(level) {
  const map = { conservative: 'success', moderate: '', aggressive: 'danger' }
  return map[level] || 'info'
}

function riskLevelLabel(level) {
  const map = { conservative: '保守', moderate: '稳健', aggressive: '激进' }
  return map[level] || level || '-'
}

// ========== 工具函数 ==========
function formatDate(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN')
}

// ========== 生命周期 ==========
function handleResize() {
  gaugeChart?.resize()
  pieChart?.resize()
  trendChart?.resize()
  returnPieChart?.resize()
  sectorBarChart?.resize()
}

onMounted(() => {
  loadSessions()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  gaugeChart?.dispose()
  pieChart?.dispose()
  trendChart?.dispose()
  returnPieChart?.dispose()
  sectorBarChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.ai-assistant-view {
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ========== Tab 1: 聊天样式 ========== */
.chat-container {
  display: flex;
  height: 560px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.chat-sidebar {
  width: 240px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background-color: #fafafa;
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 500;
}

.session-list {
  flex: 1;
}

.session-item {
  position: relative;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s;
}

.session-item:hover {
  background-color: #ecf5ff;
}

.session-item.active {
  background-color: #d9ecff;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 24px;
}

.session-time {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}

.session-delete {
  position: absolute;
  top: 8px;
  right: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-delete {
  opacity: 1;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #fff;
}

.chat-messages {
  flex: 1;
  padding: 16px;
}

.chat-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.chat-placeholder p {
  margin: 12px 0 16px;
  font-size: 14px;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.message-item {
  display: flex;
  margin-bottom: 16px;
  gap: 10px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  max-width: 70%;
}

.message-bubble {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message-item.user .message-bubble {
  background-color: #409EFF;
  color: #fff;
  border-top-right-radius: 2px;
}

.message-item.assistant .message-bubble {
  background-color: #f4f4f5;
  color: #303133;
  border-top-left-radius: 2px;
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}

.message-item.user .message-time {
  text-align: right;
}

/* 打字动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 14px 18px !important;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #909399;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* Markdown 样式 */
.message-bubble :deep(.md-code-block) {
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 13px;
  margin: 8px 0;
}

.message-bubble :deep(.md-inline-code) {
  background-color: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
  font-family: 'Courier New', monospace;
}

.message-bubble :deep(h2),
.message-bubble :deep(h3),
.message-bubble :deep(h4) {
  margin: 8px 0 4px;
}

.message-bubble :deep(ul) {
  padding-left: 20px;
  margin: 4px 0;
}

.message-bubble :deep(li) {
  margin: 2px 0;
}

.chat-input-area {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
  align-items: flex-end;
  background-color: #fafafa;
}

.chat-input-area .el-textarea {
  flex: 1;
}

/* ========== Tab 2: 情绪分析 ========== */
.sentiment-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sentiment-card {
  height: 100%;
}

.sentiment-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.sentiment-score {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.factor-list {
  padding: 0 4px;
}

.factor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f2f5;
  font-size: 13px;
}

.factor-item.positive {
  color: #67C23A;
}

.factor-item.negative {
  color: #F56C6C;
}

/* ========== Tab 3: 异常检测 ========== */
.anomaly-toolbar {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 8px 0;
}

.stat-title {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
}

.anomaly-count {
  color: #E6A23C;
}

.critical-count {
  color: #F56C6C;
}

.detail-pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  background-color: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  margin: 0;
}

/* ========== Tab 4: 策略归因 ========== */
.attribution-toolbar {
  margin-bottom: 16px;
}

.rating-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.rating-label {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.suggestion-card {
  margin-bottom: 0;
}

.suggestion-card p {
  margin: 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

/* ========== Tab 5: 策略建议 ========== */
.advice-toolbar {
  margin-bottom: 16px;
}

.advice-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.advice-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.advice-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.advice-content {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
  margin: 0 0 12px;
}

.advice-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.actions-label {
  font-size: 13px;
  color: #909399;
  margin-right: 4px;
}

/* ========== 响应式 ========== */
@media screen and (max-width: 767px) {
  .chat-container {
    flex-direction: column;
    height: auto;
  }

  .chat-sidebar {
    width: 100%;
    max-height: 180px;
    border-right: none;
    border-bottom: 1px solid #e4e7ed;
  }

  .chat-main {
    min-height: 400px;
  }

  .message-content {
    max-width: 85%;
  }

  .sentiment-toolbar {
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
  }
}
</style>
