<template>
  <div class="tenant-manage-view">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab 1: 租户管理 -->
      <el-tab-pane label="租户管理" name="tenants">
        <div class="tab-header">
          <el-button type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon> 创建租户
          </el-button>
        </div>
        <el-table :data="tenants" v-loading="loading" stripe border style="width: 100%">
          <el-table-column prop="name" label="租户名称" min-width="120" />
          <el-table-column prop="identifier" label="标识" min-width="100" />
          <el-table-column prop="plan" label="计划" width="100">
            <template #default="{ row }">
              <el-tag :type="planTagType(row.plan)" size="small">{{ row.plan }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">
                {{ row.status === 'active' ? '活跃' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user_count" label="用户数" width="80" align="center" />
          <el-table-column prop="api_calls" label="API调用数" width="110" align="center" />
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="info" @click="showUsageDialog(row)">用量</el-button>
              <el-button size="small" type="warning" @click="showWhitelabelDialog(row)">白标</el-button>
              <el-button size="small" type="success" @click="showSubscribeDialog(row)">订阅</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="tenantPage"
            :page-size="10"
            :total="tenantTotal"
            layout="total, prev, pager, next"
            @current-change="fetchTenants"
          />
        </div>
      </el-tab-pane>

      <!-- Tab 2: 白标配置 -->
      <el-tab-pane label="白标配置" name="whitelabel">
        <el-row :gutter="24">
          <el-col :xs="24" :md="12">
            <el-card shadow="hover">
              <template #header><span>品牌定制配置</span></template>
              <el-form :model="whitelabelForm" label-width="120px">
                <el-form-item label="品牌名称">
                  <el-input v-model="whitelabelForm.brand_name" placeholder="输入品牌名称" />
                </el-form-item>
                <el-form-item label="Logo">
                  <el-upload
                    class="logo-uploader"
                    action="#"
                    :auto-upload="false"
                    :show-file-list="false"
                    :on-change="handleLogoChange"
                    accept="image/*"
                  >
                    <img v-if="whitelabelForm.logo_url" :src="whitelabelForm.logo_url" class="logo-preview" />
                    <el-icon v-else class="logo-uploader-icon"><Plus /></el-icon>
                  </el-upload>
                </el-form-item>
                <el-form-item label="主色调">
                  <el-color-picker v-model="whitelabelForm.primary_color" show-alpha />
                  <span class="color-value">{{ whitelabelForm.primary_color }}</span>
                </el-form-item>
                <el-form-item label="自定义域名">
                  <el-input v-model="whitelabelForm.custom_domain" placeholder="example.openclaw.com" />
                </el-form-item>
                <el-form-item label="自定义CSS">
                  <el-input
                    v-model="whitelabelForm.custom_css"
                    type="textarea"
                    :rows="8"
                    placeholder="输入自定义 CSS 样式"
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="saveWhitelabel" :loading="saving">保存配置</el-button>
                  <el-button @click="resetWhitelabel">重置</el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-card shadow="hover">
              <template #header><span>实时预览</span></template>
              <div class="preview-container" :style="previewStyle">
                <div class="preview-header" :style="{ backgroundColor: whitelabelForm.primary_color || '#409EFF' }">
                  <img v-if="whitelabelForm.logo_url" :src="whitelabelForm.logo_url" class="preview-logo" />
                  <span v-else class="preview-brand">{{ whitelabelForm.brand_name || 'OpenClaw' }}</span>
                </div>
                <div class="preview-body">
                  <div class="preview-nav">
                    <span class="preview-nav-item active">仪表盘</span>
                    <span class="preview-nav-item">交易</span>
                    <span class="preview-nav-item">分析</span>
                  </div>
                  <div class="preview-content">
                    <div class="preview-card"></div>
                    <div class="preview-card"></div>
                    <div class="preview-card"></div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 3: 用量统计 -->
      <el-tab-pane label="用量统计" name="usage">
        <el-row :gutter="20" class="usage-row">
          <el-col :xs="24" :lg="12">
            <el-card shadow="hover">
              <template #header><span>API 调用趋势</span></template>
              <div ref="apiTrendChartRef" style="height: 350px"></div>
            </el-card>
          </el-col>
          <el-col :xs="24" :lg="12">
            <el-card shadow="hover">
              <template #header><span>各租户用量排名</span></template>
              <div ref="tenantUsageChartRef" style="height: 350px"></div>
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="20" class="usage-row">
          <el-col :xs="24" :lg="12">
            <el-card shadow="hover">
              <template #header><span>用量配额使用率</span></template>
              <div ref="quotaGaugeRef" style="height: 350px"></div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建/编辑租户对话框 -->
    <el-dialog
      v-model="tenantDialogVisible"
      :title="isEditing ? '编辑租户' : '创建租户'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="tenantForm" label-width="100px" :rules="tenantRules" ref="tenantFormRef">
        <el-form-item label="租户名称" prop="name">
          <el-input v-model="tenantForm.name" placeholder="输入租户名称" />
        </el-form-item>
        <el-form-item label="标识" prop="identifier">
          <el-input v-model="tenantForm.identifier" placeholder="输入唯一标识" :disabled="isEditing" />
        </el-form-item>
        <el-form-item label="计划" prop="plan">
          <el-select v-model="tenantForm.plan" placeholder="选择计划">
            <el-option label="Free" value="free" />
            <el-option label="Basic" value="basic" />
            <el-option label="Pro" value="pro" />
            <el-option label="Enterprise" value="enterprise" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="tenantForm.status" active-value="active" inactive-value="inactive" />
        </el-form-item>
        <el-form-item label="联系邮箱">
          <el-input v-model="tenantForm.contact_email" placeholder="输入联系邮箱" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="tenantForm.remark" type="textarea" :rows="3" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tenantDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTenant" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 用量详情对话框 -->
    <el-dialog v-model="usageDialogVisible" title="用量详情" width="600px" destroy-on-close>
      <div v-if="usageData" v-loading="usageLoading">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="租户名称">{{ usageData.tenant_name }}</el-descriptions-item>
          <el-descriptions-item label="当前计划">{{ usageData.plan }}</el-descriptions-item>
          <el-descriptions-item label="API 调用总数">{{ usageData.total_api_calls }}</el-descriptions-item>
          <el-descriptions-item label="今日调用">{{ usageData.daily_api_calls }}</el-descriptions-item>
          <el-descriptions-item label="月度调用">{{ usageData.monthly_api_calls }}</el-descriptions-item>
          <el-descriptions-item label="配额上限">{{ usageData.api_calls_limit }}</el-descriptions-item>
          <el-descriptions-item label="使用率">
            <el-progress :percentage="usageData.usage_percent" :color="usageColor(usageData.usage_percent)" />
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>

    <!-- 订阅管理对话框 -->
    <el-dialog v-model="subscribeDialogVisible" title="订阅管理" width="450px" destroy-on-close>
      <el-form :model="subscribeForm" label-width="100px">
        <el-form-item label="当前计划">
          <el-tag>{{ subscribeForm.current_plan }}</el-tag>
        </el-form-item>
        <el-form-item label="变更计划">
          <el-select v-model="subscribeForm.new_plan" placeholder="选择计划">
            <el-option label="Free" value="free" />
            <el-option label="Basic" value="basic" />
            <el-option label="Pro" value="pro" />
            <el-option label="Enterprise" value="enterprise" />
          </el-select>
        </el-form-item>
        <el-form-item label="生效时间">
          <el-date-picker v-model="subscribeForm.effective_date" type="date" placeholder="选择日期" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subscribeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSubscribe" :loading="submitting">确认变更</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  getTenants,
  createTenant,
  updateTenant,
  getTenantUsage,
  updateWhitelabel,
  subscribeTenant,
} from '@/api'

const activeTab = ref('tenants')
const loading = ref(false)
const submitting = ref(false)
const saving = ref(false)
const tenants = ref([])
const tenantPage = ref(1)
const tenantTotal = ref(0)

// 租户对话框
const tenantDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const tenantFormRef = ref(null)
const tenantForm = reactive({
  name: '',
  identifier: '',
  plan: 'free',
  status: 'active',
  contact_email: '',
  remark: '',
})
const tenantRules = {
  name: [{ required: true, message: '请输入租户名称', trigger: 'blur' }],
  identifier: [{ required: true, message: '请输入租户标识', trigger: 'blur' }],
  plan: [{ required: true, message: '请选择计划', trigger: 'change' }],
}

// 白标配置
const whitelabelForm = reactive({
  brand_name: '',
  logo_url: '',
  primary_color: '#409EFF',
  custom_domain: '',
  custom_css: '',
  tenant_id: null,
})

// 用量详情
const usageDialogVisible = ref(false)
const usageLoading = ref(false)
const usageData = ref(null)

// 订阅管理
const subscribeDialogVisible = ref(false)
const subscribeForm = reactive({
  tenant_id: null,
  current_plan: '',
  new_plan: '',
  effective_date: '',
})

// 图表 refs
const apiTrendChartRef = ref(null)
const tenantUsageChartRef = ref(null)
const quotaGaugeRef = ref(null)
let apiTrendChart = null
let tenantUsageChart = null
let quotaGaugeChart = null

const planTagType = (plan) => {
  const map = { free: 'info', basic: '', pro: 'warning', enterprise: 'danger' }
  return map[plan] || ''
}

const usageColor = (percent) => {
  if (percent >= 90) return '#F56C6C'
  if (percent >= 70) return '#E6A23C'
  return '#67C23A'
}

// 获取租户列表
const fetchTenants = async () => {
  loading.value = true
  try {
    const res = await getTenants({ page: tenantPage.value, page_size: 10 })
    tenants.value = res.data?.items || res.data || []
    tenantTotal.value = res.data?.total || tenants.value.length
  } catch (e) {
    console.error('获取租户列表失败:', e)
    tenants.value = generateMockTenants()
  } finally {
    loading.value = false
  }
}

// 模拟数据
function generateMockTenants() {
  return [
    { id: '1', name: '示例科技', identifier: 'demo-tech', plan: 'pro', status: 'active', user_count: 25, api_calls: 15820, created_at: '2025-01-15 10:00:00' },
    { id: '2', name: '量化研究院', identifier: 'quant-lab', plan: 'enterprise', status: 'active', user_count: 50, api_calls: 89340, created_at: '2025-02-01 09:30:00' },
    { id: '3', name: '投资俱乐部', identifier: 'invest-club', plan: 'basic', status: 'active', user_count: 10, api_calls: 3200, created_at: '2025-03-10 14:00:00' },
    { id: '4', name: '测试租户', identifier: 'test-tenant', plan: 'free', status: 'inactive', user_count: 2, api_calls: 150, created_at: '2025-04-01 08:00:00' },
  ]
}

// 创建租户
const showCreateDialog = () => {
  isEditing.value = false
  editingId.value = null
  Object.assign(tenantForm, { name: '', identifier: '', plan: 'free', status: 'active', contact_email: '', remark: '' })
  tenantDialogVisible.value = true
}

// 编辑租户
const showEditDialog = (row) => {
  isEditing.value = true
  editingId.value = row.id
  Object.assign(tenantForm, { name: row.name, identifier: row.identifier, plan: row.plan, status: row.status })
  tenantDialogVisible.value = true
}

// 提交租户
const submitTenant = async () => {
  if (tenantFormRef.value) await tenantFormRef.value.validate()
  submitting.value = true
  try {
    if (isEditing.value) {
      await updateTenant(editingId.value, tenantForm)
      ElMessage.success('租户更新成功')
    } else {
      await createTenant(tenantForm)
      ElMessage.success('租户创建成功')
    }
    tenantDialogVisible.value = false
    fetchTenants()
  } catch (e) {
    console.error('提交失败:', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 用量详情
const showUsageDialog = async (row) => {
  usageDialogVisible.value = true
  usageLoading.value = true
  try {
    const res = await getTenantUsage(row.id, { period: 'month' })
    usageData.value = res.data || { tenant_name: row.name, plan: row.plan, total_api_calls: row.api_calls, daily_api_calls: 520, monthly_api_calls: 15820, api_calls_limit: 50000, usage_percent: 31.6 }
  } catch {
    usageData.value = { tenant_name: row.name, plan: row.plan, total_api_calls: row.api_calls, daily_api_calls: 520, monthly_api_calls: 15820, api_calls_limit: 50000, usage_percent: 31.6 }
  } finally {
    usageLoading.value = false
  }
}

// 白标配置
const showWhitelabelDialog = (row) => {
  whitelabelForm.tenant_id = row.id
  activeTab.value = 'whitelabel'
}

const handleLogoChange = (file) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    whitelabelForm.logo_url = e.target.result
  }
  reader.readAsDataURL(file.raw)
}

const previewStyle = () => ({})

const saveWhitelabel = async () => {
  saving.value = true
  try {
    await updateWhitelabel(whitelabelForm.tenant_id, whitelabelForm)
    ElMessage.success('白标配置保存成功')
  } catch (e) {
    console.error('保存失败:', e)
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const resetWhitelabel = () => {
  Object.assign(whitelabelForm, { brand_name: '', logo_url: '', primary_color: '#409EFF', custom_domain: '', custom_css: '' })
}

// 订阅管理
const showSubscribeDialog = (row) => {
  subscribeForm.tenant_id = row.id
  subscribeForm.current_plan = row.plan
  subscribeForm.new_plan = row.plan
  subscribeForm.effective_date = ''
  subscribeDialogVisible.value = true
}

const submitSubscribe = async () => {
  submitting.value = true
  try {
    await subscribeTenant(subscribeForm.tenant_id, { plan: subscribeForm.new_plan, effective_date: subscribeForm.effective_date })
    ElMessage.success('订阅变更成功')
    subscribeDialogVisible.value = false
    fetchTenants()
  } catch (e) {
    console.error('订阅变更失败:', e)
    ElMessage.error('订阅变更失败')
  } finally {
    submitting.value = false
  }
}

// 初始化图表
const initCharts = () => {
  // API 调用趋势
  if (apiTrendChartRef.value) {
    apiTrendChart = echarts.init(apiTrendChartRef.value)
    const days = Array.from({ length: 30 }, (_, i) => {
      const d = new Date()
      d.setDate(d.getDate() - 29 + i)
      return `${d.getMonth() + 1}/${d.getDate()}`
    })
    apiTrendChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: days, boundaryGap: false },
      yAxis: { type: 'value', name: '调用次数' },
      series: [
        { name: 'API 调用', type: 'line', data: days.map(() => Math.floor(Math.random() * 2000 + 500)), smooth: true, areaStyle: { opacity: 0.15 }, itemStyle: { color: '#409EFF' } },
      ],
      grid: { left: 60, right: 20, top: 40, bottom: 30 },
    })
  }

  // 租户用量排名
  if (tenantUsageChartRef.value) {
    tenantUsageChart = echarts.init(tenantUsageChartRef.value)
    const tenantNames = ['量化研究院', '示例科技', '投资俱乐部', '测试租户', '新锐基金']
    const usageValues = [89340, 15820, 3200, 150, 890]
    tenantUsageChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'value', name: 'API 调用数' },
      yAxis: { type: 'category', data: tenantNames.reverse() },
      series: [{ type: 'bar', data: usageValues.reverse(), itemStyle: { color: '#67C23A' }, barWidth: 20 }],
      grid: { left: 100, right: 30, top: 20, bottom: 30 },
    })
  }

  // 配额使用率
  if (quotaGaugeRef.value) {
    quotaGaugeChart = echarts.init(quotaGaugeRef.value)
    quotaGaugeChart.setOption({
      series: [
        {
          type: 'gauge',
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: 100,
          splitNumber: 10,
          itemStyle: { color: '#409EFF' },
          progress: { show: true, width: 18 },
          pointer: { show: false },
          axisLine: { lineStyle: { width: 18, color: [[0.7, '#67C23A'], [0.9, '#E6A23C'], [1, '#F56C6C']] } },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          title: { fontSize: 14, offsetCenter: [0, '60%'] },
          detail: { valueAnimation: true, fontSize: 28, offsetCenter: [0, '10%'], formatter: '{value}%' },
          data: [{ value: 65, name: '总配额使用率' }],
        },
      ],
    })
  }
}

watch(activeTab, (val) => {
  if (val === 'usage') {
    nextTick(() => initCharts())
  }
})

onMounted(() => {
  fetchTenants()
})
</script>

<style lang="scss" scoped>
.tenant-manage-view {
  padding: 16px;

  .tab-header {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }

  .usage-row {
    margin-bottom: 20px;
  }

  .logo-uploader {
    :deep(.el-upload) {
      border: 1px dashed #d9d9d9;
      border-radius: 6px;
      cursor: pointer;
      width: 120px;
      height: 120px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;

      &:hover {
        border-color: #409EFF;
      }
    }
  }

  .logo-preview {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .logo-uploader-icon {
    font-size: 28px;
    color: #8c939d;
  }

  .color-value {
    margin-left: 12px;
    color: #909399;
    font-size: 13px;
  }

  .preview-container {
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    overflow: hidden;
    min-height: 300px;

    .preview-header {
      height: 50px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 16px;
      font-weight: 600;
    }

    .preview-logo {
      height: 30px;
    }

    .preview-body {
      padding: 12px;

      .preview-nav {
        display: flex;
        gap: 16px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #eee;

        .preview-nav-item {
          font-size: 13px;
          color: #909399;
          cursor: default;

          &.active {
            color: #409EFF;
            font-weight: 500;
          }
        }
      }

      .preview-content {
        display: flex;
        flex-direction: column;
        gap: 8px;

        .preview-card {
          height: 60px;
          background: #f5f7fa;
          border-radius: 6px;
          border: 1px solid #ebeef5;
        }
      }
    }
  }
}
</style>
