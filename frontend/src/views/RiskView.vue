<template>
  <div class="risk-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>风控管理</h2>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- ==================== 交易账户 Tab ==================== -->
      <el-tab-pane label="交易账户" name="accounts">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>交易账户列表</span>
              <el-button type="primary" size="small" @click="openAccountDialog()">添加账户</el-button>
            </div>
          </template>
          <el-table :data="accounts" v-loading="accountsLoading" stripe style="width: 100%">
            <el-table-column prop="name" label="账户名称" min-width="140" />
            <el-table-column prop="market" label="市场" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="marketTagType(row.market)">{{ marketLabel(row.market) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                  {{ row.status === 'active' ? '活跃' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="默认" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="总盈亏" width="120" align="right">
              <template #default="{ row }">
                <span v-if="row.total_pnl != null" :class="row.total_pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.total_pnl.toFixed(2) }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="今日盈亏" width="110" align="right">
              <template #default="{ row }">
                <span v-if="row.today_pnl != null" :class="row.today_pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.today_pnl.toFixed(2) }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="total_trades" label="总交易数" width="100" align="right" />
            <el-table-column label="创建时间" width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="!row.is_default"
                  size="small"
                  type="warning"
                  link
                  @click="handleSetDefault(row.id)"
                >设为默认</el-button>
                <el-button size="small" type="primary" link @click="openAccountDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除此账户？" @confirm="handleDeleteAccount(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger" link>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ==================== 风控规则 Tab ==================== -->
      <el-tab-pane label="风控规则" name="rules">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>风控规则列表</span>
              <el-button type="primary" size="small" @click="openRuleDialog()">添加规则</el-button>
            </div>
          </template>
          <el-table :data="rules" v-loading="rulesLoading" stripe style="width: 100%">
            <el-table-column prop="name" label="规则名称" min-width="140" />
            <el-table-column prop="rule_type" label="规则类型" width="130">
              <template #default="{ row }">
                <el-tag size="small">{{ ruleTypeLabel(row.rule_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="market" label="市场" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="marketTagType(row.market)">{{ marketLabel(row.market) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="account" label="关联账户" width="120" />
            <el-table-column label="启用" width="80" align="center">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_enabled"
                  @change="handleToggleRule(row)"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="80" align="right" />
            <el-table-column label="创建时间" width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="openRuleDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除此规则？" @confirm="handleDeleteRule(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger" link>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ==================== 风控事件 Tab ==================== -->
      <el-tab-pane label="风控事件" name="events">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>风控事件列表</span>
              <div class="filter-group">
                <el-select v-model="eventFilter.severity" placeholder="严重程度" clearable size="small" style="width: 130px; margin-right: 10px;" @change="loadEvents">
                  <el-option label="高" value="high" />
                  <el-option label="中" value="medium" />
                  <el-option label="低" value="low" />
                </el-select>
                <el-select v-model="eventFilter.market" placeholder="市场" clearable size="small" style="width: 100px;" @change="loadEvents">
                  <el-option label="A股" value="A" />
                  <el-option label="港股" value="HK" />
                  <el-option label="美股" value="US" />
                </el-select>
              </div>
            </div>
          </template>

          <el-row :gutter="16" style="margin-bottom: 20px;">
            <el-col :span="8">
              <div ref="severityChartRef" style="height: 260px;"></div>
            </el-col>
            <el-col :span="16">
              <el-table :data="events" v-loading="eventsLoading" stripe max-height="260" style="width: 100%">
                <el-table-column prop="rule_name" label="规则名称" min-width="120" />
                <el-table-column prop="rule_type" label="规则类型" width="120">
                  <template #default="{ row }">
                    <el-tag size="small">{{ ruleTypeLabel(row.rule_type) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="market" label="市场" width="70">
                  <template #default="{ row }">
                    <el-tag size="small" :type="marketTagType(row.market)">{{ marketLabel(row.market) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="severity" label="严重程度" width="100">
                  <template #default="{ row }">
                    <el-tag :type="severityTagType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="action" label="触发动作" width="100" />
                <el-table-column prop="message" label="消息" min-width="180" show-overflow-tooltip />
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
                </el-table-column>
              </el-table>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- ==================== 账户对话框 ==================== -->
    <el-dialog
      v-model="accountDialogVisible"
      :title="editingAccount ? '编辑账户' : '添加账户'"
      width="560px"
      destroy-on-close
    >
      <el-form :model="accountForm" label-width="130px" :rules="accountRules" ref="accountFormRef">
        <el-form-item label="账户名称" prop="name">
          <el-input v-model="accountForm.name" placeholder="请输入账户名称" />
        </el-form-item>
        <el-form-item label="市场" prop="market">
          <el-select v-model="accountForm.market" style="width: 100%">
            <el-option label="A股" value="A" />
            <el-option label="港股" value="HK" />
            <el-option label="美股" value="US" />
          </el-select>
        </el-form-item>
        <el-form-item label="FMZ API Key">
          <el-input v-model="accountForm.fmz_api_key" placeholder="FMZ API Key" show-password />
        </el-form-item>
        <el-form-item label="FMZ Secret Key">
          <el-input v-model="accountForm.fmz_secret_key" placeholder="FMZ Secret Key" show-password />
        </el-form-item>
        <el-form-item label="风控参数 (JSON)">
          <el-input
            v-model="accountForm.risk_params"
            type="textarea"
            :rows="4"
            placeholder='{"max_position_pct": 0.2, "max_daily_loss": 50000}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="accountDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveAccount" :loading="accountSaving">
          {{ editingAccount ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ==================== 规则对话框 ==================== -->
    <el-dialog
      v-model="ruleDialogVisible"
      :title="editingRule ? '编辑规则' : '添加规则'"
      width="560px"
      destroy-on-close
    >
      <el-form :model="ruleForm" label-width="130px" :rules="ruleRules" ref="ruleFormRef">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="ruleForm.name" placeholder="请输入规则名称" />
        </el-form-item>
        <el-form-item label="规则类型" prop="rule_type">
          <el-select v-model="ruleForm.rule_type" style="width: 100%">
            <el-option label="持仓限制" value="position_limit" />
            <el-option label="止损" value="stop_loss" />
            <el-option label="日亏损限制" value="daily_loss" />
            <el-option label="板块限制" value="sector_limit" />
          </el-select>
        </el-form-item>
        <el-form-item label="市场" prop="market">
          <el-select v-model="ruleForm.market" style="width: 100%">
            <el-option label="A股" value="A" />
            <el-option label="港股" value="HK" />
            <el-option label="美股" value="US" />
          </el-select>
        </el-form-item>
        <el-form-item label="规则参数 (JSON)">
          <el-input
            v-model="ruleForm.params"
            type="textarea"
            :rows="4"
            placeholder='{"max_position_value": 100000, "stop_loss_pct": 0.05}'
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.is_enabled" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="ruleForm.priority" :min="1" :max="100" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveRule" :loading="ruleSaving">
          {{ editingRule ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  getAccounts, createAccount, updateAccount, deleteAccount, setDefaultAccount,
  getRiskRules, createRiskRule, updateRiskRule, deleteRiskRule,
  getRiskEvents
} from '@/api'

// ========== Tab 状态 ==========
const activeTab = ref('accounts')

// ========== 交易账户 ==========
const accounts = ref([])
const accountsLoading = ref(false)
const accountDialogVisible = ref(false)
const accountSaving = ref(false)
const editingAccount = ref(null)
const accountFormRef = ref(null)

const defaultAccountForm = () => ({
  name: '',
  market: 'A',
  fmz_api_key: '',
  fmz_secret_key: '',
  risk_params: ''
})
const accountForm = reactive(defaultAccountForm())
const accountRules = {
  name: [{ required: true, message: '请输入账户名称', trigger: 'blur' }],
  market: [{ required: true, message: '请选择市场', trigger: 'change' }]
}

async function loadAccounts() {
  accountsLoading.value = true
  try {
    const res = await getAccounts()
    accounts.value = res.data?.items || res.data || []
  } catch (e) {
    ElMessage.error('加载账户列表失败')
  } finally {
    accountsLoading.value = false
  }
}

function openAccountDialog(row) {
  editingAccount.value = row || null
  if (row) {
    Object.assign(accountForm, {
      name: row.name,
      market: row.market,
      fmz_api_key: row.fmz_api_key || '',
      fmz_secret_key: row.fmz_secret_key || '',
      risk_params: typeof row.risk_params === 'object' ? JSON.stringify(row.risk_params, null, 2) : (row.risk_params || '')
    })
  } else {
    Object.assign(accountForm, defaultAccountForm())
  }
  accountDialogVisible.value = true
}

async function handleSaveAccount() {
  try {
    await accountFormRef.value?.validate()
  } catch { return }

  let parsedRiskParams = accountForm.risk_params
  if (parsedRiskParams) {
    try {
      parsedRiskParams = JSON.parse(parsedRiskParams)
    } catch {
      ElMessage.error('风控参数 JSON 格式错误')
      return
    }
  }

  accountSaving.value = true
  try {
    const payload = {
      name: accountForm.name,
      market: accountForm.market,
      fmz_api_key: accountForm.fmz_api_key,
      fmz_secret_key: accountForm.fmz_secret_key,
      risk_params: parsedRiskParams
    }
    if (editingAccount.value) {
      await updateAccount(editingAccount.value.id, payload)
      ElMessage.success('账户已更新')
    } else {
      await createAccount(payload)
      ElMessage.success('账户已创建')
    }
    accountDialogVisible.value = false
    await loadAccounts()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e?.response?.data?.detail || e.message))
  } finally {
    accountSaving.value = false
  }
}

async function handleDeleteAccount(id) {
  try {
    await deleteAccount(id)
    ElMessage.success('账户已删除')
    await loadAccounts()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function handleSetDefault(id) {
  try {
    await setDefaultAccount(id)
    ElMessage.success('已设为默认账户')
    await loadAccounts()
  } catch (e) {
    ElMessage.error('设置默认账户失败')
  }
}

// ========== 风控规则 ==========
const rules = ref([])
const rulesLoading = ref(false)
const ruleDialogVisible = ref(false)
const ruleSaving = ref(false)
const editingRule = ref(null)
const ruleFormRef = ref(null)

const defaultRuleForm = () => ({
  name: '',
  rule_type: 'position_limit',
  market: 'A',
  params: '',
  is_enabled: true,
  priority: 10
})
const ruleForm = reactive(defaultRuleForm())
const ruleRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  rule_type: [{ required: true, message: '请选择规则类型', trigger: 'change' }],
  market: [{ required: true, message: '请选择市场', trigger: 'change' }]
}

async function loadRules() {
  rulesLoading.value = true
  try {
    const res = await getRiskRules()
    rules.value = res.data?.items || res.data || []
  } catch (e) {
    ElMessage.error('加载规则列表失败')
  } finally {
    rulesLoading.value = false
  }
}

function openRuleDialog(row) {
  editingRule.value = row || null
  if (row) {
    Object.assign(ruleForm, {
      name: row.name,
      rule_type: row.rule_type,
      market: row.market,
      params: typeof row.params === 'object' ? JSON.stringify(row.params, null, 2) : (row.params || ''),
      is_enabled: row.is_enabled,
      priority: row.priority
    })
  } else {
    Object.assign(ruleForm, defaultRuleForm())
  }
  ruleDialogVisible.value = true
}

async function handleSaveRule() {
  try {
    await ruleFormRef.value?.validate()
  } catch { return }

  let parsedParams = ruleForm.params
  if (parsedParams) {
    try {
      parsedParams = JSON.parse(parsedParams)
    } catch {
      ElMessage.error('规则参数 JSON 格式错误')
      return
    }
  }

  ruleSaving.value = true
  try {
    const payload = {
      name: ruleForm.name,
      rule_type: ruleForm.rule_type,
      market: ruleForm.market,
      params: parsedParams,
      is_enabled: ruleForm.is_enabled,
      priority: ruleForm.priority
    }
    if (editingRule.value) {
      await updateRiskRule(editingRule.value.id, payload)
      ElMessage.success('规则已更新')
    } else {
      await createRiskRule(payload)
      ElMessage.success('规则已创建')
    }
    ruleDialogVisible.value = false
    await loadRules()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e?.response?.data?.detail || e.message))
  } finally {
    ruleSaving.value = false
  }
}

async function handleToggleRule(row) {
  try {
    await updateRiskRule(row.id, { ...row, is_enabled: !row.is_enabled })
    ElMessage.success(row.is_enabled ? '规则已禁用' : '规则已启用')
    await loadRules()
  } catch (e) {
    ElMessage.error('切换规则状态失败')
  }
}

async function handleDeleteRule(id) {
  try {
    await deleteRiskRule(id)
    ElMessage.success('规则已删除')
    await loadRules()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// ========== 风控事件 ==========
const events = ref([])
const eventsLoading = ref(false)
const eventFilter = reactive({
  severity: '',
  market: ''
})
const severityChartRef = ref(null)
let severityChart = null

async function loadEvents() {
  eventsLoading.value = true
  try {
    const params = {}
    if (eventFilter.severity) params.severity = eventFilter.severity
    if (eventFilter.market) params.market = eventFilter.market
    const res = await getRiskEvents(params)
    events.value = res.data?.items || res.data || []
    await nextTick()
    initSeverityChart()
  } catch (e) {
    ElMessage.error('加载事件列表失败')
  } finally {
    eventsLoading.value = false
  }
}

function initSeverityChart() {
  if (!severityChartRef.value) return
  if (severityChart) {
    severityChart.dispose()
  }
  severityChart = echarts.init(severityChartRef.value)

  const highCount = events.value.filter(e => e.severity === 'high').length
  const mediumCount = events.value.filter(e => e.severity === 'medium').length
  const lowCount = events.value.filter(e => e.severity === 'low').length

  severityChart.setOption({
    title: {
      text: '事件严重程度分布',
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 500 }
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      top: 'middle',
      data: ['高', '中', '低']
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['60%', '55%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        formatter: '{b}\n{c}'
      },
      data: [
        { value: highCount, name: '高', itemStyle: { color: '#F56C6C' } },
        { value: mediumCount, name: '中', itemStyle: { color: '#E6A23C' } },
        { value: lowCount, name: '低', itemStyle: { color: '#67C23A' } }
      ]
    }]
  })
}

// ========== 工具函数 ==========
function formatDate(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN')
}

function marketLabel(m) {
  const map = { A: 'A股', HK: '港股', US: '美股' }
  return map[m] || m || '-'
}

function marketTagType(m) {
  const map = { A: '', HK: 'success', US: 'warning' }
  return map[m] || 'info'
}

function ruleTypeLabel(t) {
  const map = {
    position_limit: '持仓限制',
    stop_loss: '止损',
    daily_loss: '日亏损限制',
    sector_limit: '板块限制'
  }
  return map[t] || t || '-'
}

function severityTagType(s) {
  const map = { high: 'danger', medium: 'warning', low: 'success' }
  return map[s] || 'info'
}

function severityLabel(s) {
  const map = { high: '高', medium: '中', low: '低' }
  return map[s] || s || '-'
}

// ========== Tab 切换 ==========
function handleTabChange(tab) {
  if (tab === 'events') {
    loadEvents()
  }
}

// ========== 生命周期 ==========
function handleResize() {
  severityChart?.resize()
}

onMounted(() => {
  loadAccounts()
  loadRules()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  severityChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.risk-view {
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
.filter-group {
  display: flex;
  align-items: center;
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
