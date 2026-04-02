<template>
  <div class="ha-monitor-page">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab 1: 集群状态 -->
      <el-tab-pane label="集群状态" name="cluster">
        <div class="cluster-header">
          <el-tag :type="clusterStatusType" size="large" effect="dark">
            {{ clusterData.status === 'healthy' ? '集群健康' : clusterData.status === 'degraded' ? '集群降级' : '集群异常' }}
          </el-tag>
          <span class="cluster-info">
            在线: {{ clusterData.online_nodes }} / {{ clusterData.total_nodes }}
          </span>
          <el-button type="primary" size="small" @click="loadClusterStatus" :loading="clusterLoading">刷新</el-button>
        </div>

        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" v-for="node in clusterData.nodes" :key="node.node_id">
            <el-card shadow="never" class="node-card" :class="'node-' + node.status">
              <div class="node-header">
                <span class="status-dot" :class="'dot-' + node.status"></span>
                <span class="node-name">{{ node.node_id }}</span>
              </div>
              <el-descriptions :column="1" size="small">
                <el-descriptions-item label="类型">{{ nodeLabel(node.node_type) }}</el-descriptions-item>
                <el-descriptions-item label="地址">{{ node.host }}:{{ node.port }}</el-descriptions-item>
                <el-descriptions-item label="角色">{{ node.role || '-' }}</el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="nodeStatusType(node.status)" size="small">{{ nodeStatusLabel(node.status) }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="复制延迟" v-if="node.node_type === 'replica'">
                  {{ node.replication_lag }}秒
                </el-descriptions-item>
                <el-descriptions-item label="区域">{{ node.region || '-' }}</el-descriptions-item>
                <el-descriptions-item label="心跳">{{ formatTime(node.last_heartbeat) }}</el-descriptions-item>
              </el-descriptions>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 2: 数据库管理 -->
      <el-tab-pane label="数据库管理" name="database">
        <el-row :gutter="20">
          <!-- 左侧：备份操作 -->
          <el-col :span="14">
            <el-card shadow="never">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>数据库备份</span>
                  <div>
                    <el-button type="primary" size="small" @click="createBackup('full')" :loading="backupLoading">全量备份</el-button>
                    <el-button size="small" @click="createBackup('incremental')" :loading="backupLoading">增量备份</el-button>
                  </div>
                </div>
              </template>

              <el-table :data="backups" v-loading="backupsLoading" stripe size="small">
                <el-table-column prop="backup_id" label="备份ID" width="200" />
                <el-table-column prop="backup_type" label="类型" width="90">
                  <template #default="{ row }">
                    <el-tag :type="row.backup_type === 'full' ? '' : 'success'" size="small">{{ row.backup_type === 'full' ? '全量' : '增量' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="90">
                  <template #default="{ row }">
                    <el-tag :type="backupStatusType(row.status)" size="small">{{ backupStatusLabel(row.status) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="大小" width="100">
                  <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
                </el-table-column>
                <el-table-column label="耗时" width="80">
                  <template #default="{ row }">{{ row.duration_seconds ? row.duration_seconds + 's' : '-' }}</template>
                </el-table-column>
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatTime(row.completed_at || row.started_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="140" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="warning" :disabled="row.status !== 'completed'" @click="restoreBackup(row.backup_id)">恢复</el-button>
                    <el-button size="small" type="danger" @click="deleteBackup(row.backup_id)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>

          <!-- 右侧：复制状态 -->
          <el-col :span="10">
            <el-card shadow="never" style="margin-bottom: 16px">
              <template #header><span>主从复制状态</span></template>
              <div v-loading="replicationLoading">
                <div class="replication-master">
                  <div class="rep-role">主库 (Master)</div>
                  <div class="rep-info">
                    <span>{{ replicationData.master?.host }}:{{ replicationData.master?.port }}</span>
                    <el-tag :type="replicationData.master?.status === 'online' ? 'success' : 'danger'" size="small">
                      {{ replicationData.master?.status }}
                    </el-tag>
                  </div>
                </div>
                <el-divider />
                <div v-for="(replica, idx) in replicationData.replicas" :key="idx" class="replication-replica">
                  <div class="rep-role">从库 {{ idx + 1 }} (Slave)</div>
                  <div class="rep-info">
                    <span>{{ replica.host }}:{{ replica.port }}</span>
                    <el-tag :type="replica.status === 'online' ? 'success' : 'danger'" size="small">
                      {{ replica.status }}
                    </el-tag>
                  </div>
                  <div class="rep-detail">
                    IO线程: <el-tag :type="replica.io_running ? 'success' : 'danger'" size="small">{{ replica.io_running ? '运行中' : '停止' }}</el-tag>
                    SQL线程: <el-tag :type="replica.sql_running ? 'success' : 'danger'" size="small">{{ replica.sql_running ? '运行中' : '停止' }}</el-tag>
                    延迟: <span :style="{ color: replica.seconds_behind_master > 5 ? '#f56c6c' : '#67c23a' }">{{ replica.seconds_behind_master }}s</span>
                  </div>
                </div>
                <el-divider />
                <div style="text-align: center">
                  <el-button type="danger" size="small" @click="triggerFailover">执行故障转移</el-button>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 3: 系统监控 -->
      <el-tab-pane label="系统监控" name="monitor">
        <!-- 系统健康仪表盘 -->
        <el-row :gutter="16" style="margin-bottom: 20px">
          <el-col :span="6">
            <el-card shadow="never" class="health-card">
              <div ref="cpuGaugeRef" style="height: 200px"></div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="health-card">
              <div ref="memGaugeRef" style="height: 200px"></div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="health-card">
              <div ref="diskGaugeRef" style="height: 200px"></div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never" class="health-card">
              <div class="health-summary">
                <div class="health-status">
                  <el-tag :type="healthData.status === 'healthy' ? 'success' : healthData.status === 'degraded' ? 'warning' : 'danger'" effect="dark" size="large">
                    {{ healthData.status === 'healthy' ? '系统健康' : healthData.status === 'degraded' ? '系统降级' : '系统异常' }}
                  </el-tag>
                </div>
                <div class="health-detail">
                  <div class="hd-row"><span>数据库</span><el-tag :type="healthData.database === 'ok' ? 'success' : 'danger'" size="small">{{ healthData.database }}</el-tag></div>
                  <div class="hd-row"><span>缓存</span><el-tag :type="healthData.cache === 'ok' ? 'success' : 'danger'" size="small">{{ healthData.cache }}</el-tag></div>
                  <div class="hd-row"><span>活跃连接</span><span>{{ healthData.active_connections }}</span></div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 性能指标图表 -->
        <el-card shadow="never" style="margin-bottom: 20px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>性能指标趋势</span>
              <el-select v-model="metricsPeriod" size="small" style="width: 120px" @change="loadMetrics">
                <el-option label="5分钟" value="5m" />
                <el-option label="15分钟" value="15m" />
                <el-option label="1小时" value="1h" />
                <el-option label="6小时" value="6h" />
                <el-option label="24小时" value="24h" />
              </el-select>
            </div>
          </template>
          <div ref="metricsChartRef" style="height: 350px"></div>
        </el-card>

        <!-- 告警列表 -->
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>活跃告警</span>
              <el-button size="small" @click="loadAlerts">刷新</el-button>
            </div>
          </template>
          <el-table :data="alerts" v-loading="alertsLoading" stripe size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="rule_name" label="规则" width="160" />
            <el-table-column prop="severity" label="级别" width="90">
              <template #default="{ row }">
                <el-tag :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'firing' ? 'danger' : 'warning'" size="small">{{ row.status === 'firing' ? '触发中' : '已确认' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="fired_at" label="触发时间" width="160">
              <template #default="{ row }">{{ formatTime(row.fired_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" type="warning" :disabled="row.status !== 'firing'" @click="ackAlert(row.id)">确认</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  getClusterStatus, getDBReplication, triggerFailover as triggerFailoverApi,
  createBackup as createBackupApi, getBackups, restoreBackup as restoreBackupApi,
  deleteBackup as deleteBackupApi, getSystemHealth, getPerformanceMetrics,
  getAlertRules, getActiveAlerts, acknowledgeAlert
} from '@/api'

const activeTab = ref('cluster')

// ========== 集群状态 ==========
const clusterData = ref({ status: 'healthy', total_nodes: 0, online_nodes: 0, nodes: [] })
const clusterLoading = ref(false)

const clusterStatusType = ref('success')

async function loadClusterStatus() {
  clusterLoading.value = true
  try {
    const result = await getClusterStatus()
    clusterData.value = result.data || {}
    clusterStatusType.value = clusterData.value.status === 'healthy' ? 'success' : clusterData.value.status === 'degraded' ? 'warning' : 'danger'
  } catch (err) {
    ElMessage.error('获取集群状态失败')
  } finally {
    clusterLoading.value = false
  }
}

// ========== 数据库管理 ==========
const replicationData = ref({ master: {}, replicas: [] })
const replicationLoading = ref(false)
const backups = ref([])
const backupsLoading = ref(false)
const backupLoading = ref(false)

async function loadReplication() {
  replicationLoading.value = true
  try {
    const result = await getDBReplication()
    replicationData.value = result.data || {}
  } catch (err) {
    ElMessage.error('获取复制状态失败')
  } finally {
    replicationLoading.value = false
  }
}

async function loadBackups() {
  backupsLoading.value = true
  try {
    const result = await getBackups()
    backups.value = result.data?.backups || []
  } catch (err) {
    ElMessage.error('获取备份列表失败')
  } finally {
    backupsLoading.value = false
  }
}

async function createBackup(type) {
  backupLoading.value = true
  try {
    const result = await createBackupApi({ backup_type: type })
    if (result.data?.success) {
      ElMessage.success(`备份创建成功: ${result.data.backup_id}`)
      loadBackups()
    } else {
      ElMessage.error(result.data?.message || '备份失败')
    }
  } catch (err) {
    ElMessage.error('创建备份失败')
  } finally {
    backupLoading.value = false
  }
}

async function restoreBackup(backupId) {
  try {
    await ElMessageBox.confirm('确定要从该备份恢复数据库吗？此操作不可逆！', '确认恢复', { type: 'warning' })
    const result = await restoreBackupApi(backupId)
    if (result.data?.success) {
      ElMessage.success('数据库恢复成功')
    } else {
      ElMessage.error(result.data?.message || '恢复失败')
    }
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('恢复失败')
  }
}

async function deleteBackup(backupId) {
  try {
    await ElMessageBox.confirm('确定要删除该备份吗？', '确认删除', { type: 'warning' })
    const result = await deleteBackupApi(backupId)
    if (result.data?.success) {
      ElMessage.success('备份已删除')
      loadBackups()
    }
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('删除失败')
  }
}

async function triggerFailover() {
  try {
    await ElMessageBox.confirm('确定要执行故障转移吗？将从库提升为主库。', '确认故障转移', { type: 'error' })
    const result = await triggerFailoverApi()
    if (result.data?.success) {
      ElMessage.success('故障转移成功')
      loadReplication()
      loadClusterStatus()
    } else {
      ElMessage.error(result.data?.message || '故障转移失败')
    }
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('故障转移失败')
  }
}

// ========== 系统监控 ==========
const healthData = ref({ status: 'healthy', cpu_usage: 0, memory_usage: 0, disk_usage: 0, database: 'ok', cache: 'ok', active_connections: 0 })
const metricsPeriod = ref('1h')
const metricsData = ref({})
const alerts = ref([])
const alertsLoading = ref(false)
const cpuGaugeRef = ref(null)
const memGaugeRef = ref(null)
const diskGaugeRef = ref(null)
const metricsChartRef = ref(null)

let cpuChart = null
let memChart = null
let diskChart = null
let metricsChart = null

async function loadHealth() {
  try {
    const result = await getSystemHealth()
    healthData.value = result.data || {}
    await nextTick()
    renderGauges()
  } catch (err) {
    ElMessage.error('获取系统健康状态失败')
  }
}

async function loadMetrics() {
  try {
    const result = await getPerformanceMetrics({ period: metricsPeriod.value })
    metricsData.value = result.data || {}
    await nextTick()
    renderMetricsChart()
  } catch (err) {
    ElMessage.error('获取性能指标失败')
  }
}

async function loadAlerts() {
  alertsLoading.value = true
  try {
    const result = await getActiveAlerts()
    alerts.value = result.data?.alerts || []
  } catch (err) {
    ElMessage.error('获取告警失败')
  } finally {
    alertsLoading.value = false
  }
}

async function ackAlert(alertId) {
  try {
    const result = await acknowledgeAlert(alertId)
    if (result.data?.success) {
      ElMessage.success('告警已确认')
      loadAlerts()
    }
  } catch (err) {
    ElMessage.error('确认告警失败')
  }
}

function renderGauges() {
  const gaugeOption = (title, value, maxVal) => ({
    title: { text: title, left: 'center', top: '5%', textStyle: { fontSize: 14 } },
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: maxVal,
      detail: { formatter: '{value}%', fontSize: 18, offsetCenter: [0, '60%'] },
      data: [{ value: Math.round(value), name: '' }],
      axisLine: {
        lineStyle: {
          color: [[0.6, '#67c23a'], [0.8, '#e6a23c'], [1, '#f56c6c']]
        }
      },
      progress: { show: true, width: 12 },
    }]
  })

  if (cpuGaugeRef.value) {
    if (cpuChart) cpuChart.dispose()
    cpuChart = echarts.init(cpuGaugeRef.value)
    cpuChart.setOption(gaugeOption('CPU 使用率', healthData.value.cpu_usage, 100))
  }
  if (memGaugeRef.value) {
    if (memChart) memChart.dispose()
    memChart = echarts.init(memGaugeRef.value)
    memChart.setOption(gaugeOption('内存使用率', healthData.value.memory_usage, 100))
  }
  if (diskGaugeRef.value) {
    if (diskChart) diskChart.dispose()
    diskChart = echarts.init(diskGaugeRef.value)
    diskChart.setOption(gaugeOption('磁盘使用率', healthData.value.disk_usage, 100))
  }
}

function renderMetricsChart() {
  if (!metricsChartRef.value) return
  if (metricsChart) metricsChart.dispose()
  metricsChart = echarts.init(metricsChartRef.value)

  const m = metricsData.value
  metricsChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['QPS', '平均延迟(ms)', '错误率(%)'], top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: generateTimeLabels(m.period) },
    yAxis: [
      { type: 'value', name: 'QPS' },
      { type: 'value', name: 'ms / %' },
    ],
    series: [
      {
        name: 'QPS',
        type: 'line',
        smooth: true,
        data: generateTrendData(m.qps, 20),
        itemStyle: { color: '#409eff' },
      },
      {
        name: '平均延迟(ms)',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: generateTrendData(m.avg_latency_ms, 5),
        itemStyle: { color: '#e6a23c' },
      },
      {
        name: '错误率(%)',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: generateTrendData(m.error_rate, 0.1),
        itemStyle: { color: '#f56c6c' },
      },
    ]
  })
}

function generateTimeLabels(period) {
  const count = 12
  const labels = []
  const now = new Date()
  for (let i = count - 1; i >= 0; i--) {
    const d = new Date(now)
    if (period === '5m' || period === '15m') d.setMinutes(d.getMinutes() - i)
    else if (period === '1h') d.setMinutes(d.getMinutes() - i * 5)
    else if (period === '6h') d.setMinutes(d.getMinutes() - i * 30)
    else d.setHours(d.getHours() - i * 2)
    labels.push(`${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`)
  }
  return labels
}

function generateTrendData(base, variance) {
  const data = []
  let val = base
  for (let i = 0; i < 12; i++) {
    val = base + (Math.random() - 0.5) * variance * 2
    data.push(Math.round(val * 100) / 100)
  }
  return data
}

// ========== 辅助函数 ==========
function nodeLabel(type) {
  const map = { primary: '主节点', replica: '从节点', worker: '工作节点' }
  return map[type] || type
}
function nodeStatusType(status) {
  const map = { online: 'success', offline: 'danger', degraded: 'warning', unknown: 'info' }
  return map[status] || 'info'
}
function nodeStatusLabel(status) {
  const map = { online: '在线', offline: '离线', degraded: '降级', unknown: '未知' }
  return map[status] || status
}
function backupStatusType(status) {
  const map = { completed: 'success', running: '', failed: 'danger', pending: 'warning' }
  return map[status] || 'info'
}
function backupStatusLabel(status) {
  const map = { completed: '完成', running: '运行中', failed: '失败', pending: '待执行' }
  return map[status] || status
}
function severityType(sev) {
  const map = { critical: 'danger', warning: 'warning', info: 'info' }
  return map[sev] || 'info'
}
function severityLabel(sev) {
  const map = { critical: '严重', warning: '警告', info: '信息' }
  return map[sev] || sev
}
function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}
function formatTime(t) {
  if (!t) return '-'
  try {
    const d = new Date(t)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch { return t }
}

// ========== 初始化 ==========
onMounted(() => {
  loadClusterStatus()
  loadReplication()
  loadBackups()
  loadHealth()
  loadMetrics()
  loadAlerts()
})
</script>

<style lang="scss" scoped>
.ha-monitor-page {
  padding: 0;
}

.cluster-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;

  .cluster-info { color: #606266; font-size: 14px; }
}

.node-card {
  margin-bottom: 16px;
  transition: box-shadow 0.3s;

  &:hover { box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1); }

  &.node-online { border-left: 3px solid #67c23a; }
  &.node-offline { border-left: 3px solid #f56c6c; }
  &.node-degraded { border-left: 3px solid #e6a23c; }
  &.node-unknown { border-left: 3px solid #909399; }
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;

    &.dot-online { background: #67c23a; box-shadow: 0 0 6px #67c23a; }
    &.dot-offline { background: #f56c6c; box-shadow: 0 0 6px #f56c6c; }
    &.dot-degraded { background: #e6a23c; box-shadow: 0 0 6px #e6a23c; }
    &.dot-unknown { background: #909399; }
  }

  .node-name { font-weight: 600; font-size: 14px; }
}

.replication-master, .replication-replica {
  margin-bottom: 12px;

  .rep-role { font-weight: 500; margin-bottom: 4px; font-size: 13px; }
  .rep-info { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
  .rep-detail { font-size: 12px; color: #909399; display: flex; gap: 12px; flex-wrap: wrap; }
}

.health-card {
  text-align: center;
}

.health-summary {
  padding: 20px 10px;

  .health-status { margin-bottom: 16px; }

  .health-detail {
    text-align: left;

    .hd-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid #f0f2f5;
      font-size: 13px;
    }
  }
}

/* 响应式 */
@media screen and (max-width: 767px) {
  .cluster-header { flex-wrap: wrap; }
}
</style>
