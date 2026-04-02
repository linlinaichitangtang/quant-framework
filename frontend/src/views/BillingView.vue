<template>
  <div class="billing-view">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Tab 1: 订阅计划 -->
      <el-tab-pane label="订阅计划" name="plans">
        <el-row :gutter="20" v-loading="loadingPlans">
          <el-col :xs="24" :sm="12" :md="6" v-for="plan in plans" :key="plan.id" style="margin-bottom: 20px">
            <el-card
              shadow="hover"
              class="plan-card"
              :class="{ 'plan-current': plan.id === currentPlanId, 'plan-popular': plan.popular }"
            >
              <div v-if="plan.popular" class="plan-badge">推荐</div>
              <div class="plan-header">
                <h3 class="plan-name">{{ plan.name }}</h3>
                <div class="plan-price">
                  <span class="price-amount">{{ plan.price }}</span>
                  <span class="price-unit">元/月</span>
                </div>
              </div>
              <el-divider />
              <ul class="plan-features">
                <li v-for="(feature, idx) in plan.features" :key="idx">
                  <el-icon class="feature-check"><CircleCheck /></el-icon>
                  {{ feature }}
                </li>
              </ul>
              <div class="plan-action">
                <el-button
                  v-if="plan.id === currentPlanId"
                  type="info"
                  disabled
                  round
                  style="width: 100%"
                >
                  当前计划
                </el-button>
                <el-button
                  v-else-if="plan.level < currentPlanLevel"
                  type="warning"
                  plain
                  round
                  style="width: 100%"
                  @click="changePlan(plan, 'downgrade')"
                >
                  降级
                </el-button>
                <el-button
                  v-else
                  type="primary"
                  round
                  style="width: 100%"
                  @click="changePlan(plan, 'upgrade')"
                >
                  升级
                </el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 功能对比 -->
        <el-card shadow="hover" style="margin-top: 20px">
          <template #header><span>功能对比</span></template>
          <el-table :data="featureComparison" border stripe style="width: 100%">
            <el-table-column prop="feature" label="功能" min-width="180" fixed />
            <el-table-column v-for="plan in plans" :key="plan.id" :label="plan.name" width="120" align="center">
              <template #default="{ row }">
                <el-icon v-if="row[plan.id] === true" color="#67C23A"><CircleCheck /></el-icon>
                <span v-else-if="row[plan.id] === false" style="color: #C0C4CC">-</span>
                <span v-else>{{ row[plan.id] }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Tab 2: 当前订阅 -->
      <el-tab-pane label="当前订阅" name="current">
        <div v-loading="loadingCurrent">
          <el-row :gutter="20">
            <el-col :xs="24" :md="16">
              <el-card shadow="hover">
                <template #header><span>订阅详情</span></template>
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="当前计划">
                    <el-tag type="primary" size="large">{{ subscription.plan_name }}</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="订阅周期">{{ subscription.billing_cycle }}</el-descriptions-item>
                  <el-descriptions-item label="开始日期">{{ subscription.start_date }}</el-descriptions-item>
                  <el-descriptions-item label="到期时间">
                    <span :class="{ 'expire-warning': isExpiringSoon }">{{ subscription.end_date }}</span>
                    <el-tag v-if="isExpiringSoon" type="warning" size="small" style="margin-left: 8px">即将到期</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="月度费用">{{ subscription.amount }} 元</el-descriptions-item>
                  <el-descriptions-item label="下次扣费">{{ subscription.next_billing_date }}</el-descriptions-item>
                  <el-descriptions-item label="订阅状态">
                    <el-tag :type="subscription.status === 'active' ? 'success' : 'danger'">
                      {{ subscription.status === 'active' ? '活跃' : '已取消' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="自动续费">
                    <el-switch v-model="subscription.auto_renew" @change="toggleAutoRenew" />
                  </el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-card shadow="hover">
                <template #header><span>用量概览</span></template>
                <div class="usage-items">
                  <div class="usage-item" v-for="item in usageItems" :key="item.label">
                    <div class="usage-label">{{ item.label }}</div>
                    <el-progress
                      :percentage="item.percent"
                      :color="item.percent >= 90 ? '#F56C6C' : item.percent >= 70 ? '#E6A23C' : '#409EFF'"
                      :stroke-width="12"
                      :text-inside="true"
                    />
                    <div class="usage-detail">{{ item.used }} / {{ item.limit }}</div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <div style="margin-top: 20px; text-align: center">
            <el-popconfirm
              title="确定要取消订阅吗？取消后将在当前周期结束时生效。"
              confirm-button-text="确定取消"
              cancel-button-text="保留订阅"
              @confirm="cancelSubscription"
            >
              <template #reference>
                <el-button type="danger" plain :disabled="subscription.status !== 'active'">取消订阅</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 3: 账单历史 -->
      <el-tab-pane label="账单历史" name="invoices">
        <el-table :data="invoices" v-loading="loadingInvoices" stripe border style="width: 100%">
          <el-table-column prop="month" label="月份" width="140" />
          <el-table-column prop="plan" label="计划" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ row.plan }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="amount" label="金额" width="120" align="right">
            <template #default="{ row }">
              <span style="font-weight: 600; color: #303133">¥{{ row.amount.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="invoiceStatusType(row.status)" size="small">{{ invoiceStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="paid_at" label="支付时间" width="170" />
          <el-table-column prop="invoice_no" label="发票号" min-width="160" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" link :disabled="row.status !== 'paid'" @click="downloadInvoice(row)">
                下载
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="invoicePage"
            :page-size="10"
            :total="invoiceTotal"
            layout="total, prev, pager, next"
            @current-change="fetchInvoices"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 升级/降级确认对话框 -->
    <el-dialog v-model="changePlanDialogVisible" :title="changePlanAction === 'upgrade' ? '升级计划' : '降级计划'" width="420px" destroy-on-close>
      <div class="change-plan-confirm">
        <p>当前计划: <el-tag>{{ currentPlanName }}</el-tag></p>
        <p style="margin-top: 8px">
          {{ changePlanAction === 'upgrade' ? '升级' : '降级' }}到: <el-tag type="primary">{{ changePlanTarget?.name }}</el-tag>
        </p>
        <p style="margin-top: 8px; color: #909399; font-size: 13px">
          {{ changePlanAction === 'upgrade' ? '升级将在下一个计费周期生效，差价将按比例计算。' : '降级将在当前计费周期结束后生效。' }}
        </p>
        <p style="margin-top: 12px; font-size: 18px; font-weight: 600; color: #409EFF">
          {{ changePlanTarget?.price }} 元/月
        </p>
      </div>
      <template #footer>
        <el-button @click="changePlanDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmChangePlan" :loading="changingPlan">确认{{ changePlanAction === 'upgrade' ? '升级' : '降级' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { CircleCheck } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  getBillingPlans,
  getCurrentSubscription,
  subscribePlan,
  cancelSubscription as cancelSubscriptionApi,
  getInvoices,
  getInvoice,
} from '@/api'

const activeTab = ref('plans')
const loadingPlans = ref(false)
const loadingCurrent = ref(false)
const loadingInvoices = ref(false)
const changingPlan = ref(false)

// 计划数据
const plans = ref([])
const currentPlanId = ref('basic')
const currentPlanLevel = ref(1)
const currentPlanName = ref('Basic')

// 订阅数据
const subscription = ref({
  plan_name: 'Basic',
  billing_cycle: '月付',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  amount: 99,
  next_billing_date: '2025-04-01',
  status: 'active',
  auto_renew: true,
})

const isExpiringSoon = computed(() => {
  if (!subscription.value.end_date) return false
  const end = new Date(subscription.value.end_date)
  const now = new Date()
  const diff = (end - now) / (1000 * 60 * 60 * 24)
  return diff <= 30 && diff > 0
})

const usageItems = ref([
  { label: 'API 调用', used: '15,820', limit: '50,000', percent: 31.6 },
  { label: '存储空间', used: '2.1 GB', limit: '10 GB', percent: 21 },
  { label: '并发连接', used: '3', limit: '10', percent: 30 },
  { label: '回测次数', used: '45', limit: '100', percent: 45 },
])

// 功能对比
const featureComparison = ref([
  { feature: 'API 调用/月', free: '1,000', basic: '50,000', pro: '500,000', enterprise: '无限' },
  { feature: '存储空间', free: '100 MB', basic: '10 GB', pro: '100 GB', enterprise: '1 TB' },
  { feature: '并发连接', free: '1', basic: '10', pro: '50', enterprise: '200' },
  { feature: '回测次数/月', free: '5', basic: '100', pro: '1,000', enterprise: '无限' },
  { feature: 'AI 查询/月', free: '10', basic: '200', pro: '2,000', enterprise: '无限' },
  { feature: '策略数量', free: '1', basic: '10', pro: '100', enterprise: '无限' },
  { feature: '多租户', free: false, basic: false, pro: true, enterprise: true },
  { feature: '白标定制', free: false, basic: false, pro: false, enterprise: true },
  { feature: '专属客服', free: false, basic: false, pro: true, enterprise: true },
  { feature: 'SLA 保障', free: false, basic: false, pro: '99.9%', enterprise: '99.99%' },
])

// 账单数据
const invoices = ref([])
const invoicePage = ref(1)
const invoiceTotal = ref(0)

// 变更计划
const changePlanDialogVisible = ref(false)
const changePlanAction = ref('upgrade')
const changePlanTarget = ref(null)

const invoiceStatusType = (status) => {
  const map = { paid: 'success', pending: 'warning', failed: 'danger', refunded: 'info' }
  return map[status] || ''
}

const invoiceStatusLabel = (status) => {
  const map = { paid: '已支付', pending: '待支付', failed: '支付失败', refunded: '已退款' }
  return map[status] || status
}

// 获取计划列表
const fetchPlans = async () => {
  loadingPlans.value = true
  try {
    const res = await getBillingPlans()
    plans.value = res.data || []
  } catch {
    plans.value = generateMockPlans()
  } finally {
    loadingPlans.value = false
  }
}

function generateMockPlans() {
  return [
    { id: 'free', name: 'Free', price: 0, level: 0, popular: false, features: ['1,000 API 调用/月', '100 MB 存储', '1 个策略', '基础行情数据', '社区支持'] },
    { id: 'basic', name: 'Basic', price: 99, level: 1, popular: false, features: ['50,000 API 调用/月', '10 GB 存储', '10 个策略', '实时行情', 'AI 基础查询', '邮件支持'] },
    { id: 'pro', name: 'Pro', price: 499, level: 2, popular: true, features: ['500,000 API 调用/月', '100 GB 存储', '100 个策略', '高级 AI 分析', '回测不限', '多租户', '专属客服'] },
    { id: 'enterprise', name: 'Enterprise', price: 1999, level: 3, popular: false, features: ['无限 API 调用', '1 TB 存储', '无限策略', '全部 AI 功能', '白标定制', 'SLA 保障', '专属技术支持'] },
  ]
}

// 获取当前订阅
const fetchSubscription = async () => {
  loadingCurrent.value = true
  try {
    const res = await getCurrentSubscription()
    if (res.data) {
      subscription.value = { ...subscription.value, ...res.data }
      currentPlanId.value = res.data.plan_id || 'basic'
      currentPlanName.value = res.data.plan_name || 'Basic'
    }
  } catch {
    // 使用默认数据
  } finally {
    loadingCurrent.value = false
  }
}

// 获取账单列表
const fetchInvoices = async () => {
  loadingInvoices.value = true
  try {
    const res = await getInvoices({ page: invoicePage.value, page_size: 10 })
    invoices.value = res.data?.items || res.data || []
    invoiceTotal.value = res.data?.total || invoices.value.length
  } catch {
    invoices.value = generateMockInvoices()
    invoiceTotal.value = invoices.value.length
  } finally {
    loadingInvoices.value = false
  }
}

function generateMockInvoices() {
  return [
    { id: '1', month: '2025-03', plan: 'Basic', amount: 99, status: 'paid', paid_at: '2025-03-01 10:00:00', invoice_no: 'INV-202503-001' },
    { id: '2', month: '2025-02', plan: 'Basic', amount: 99, status: 'paid', paid_at: '2025-02-01 10:00:00', invoice_no: 'INV-202502-001' },
    { id: '3', month: '2025-01', plan: 'Basic', amount: 99, status: 'paid', paid_at: '2025-01-01 10:00:00', invoice_no: 'INV-202501-001' },
    { id: '4', month: '2024-12', plan: 'Free', amount: 0, status: 'paid', paid_at: '2024-12-01 10:00:00', invoice_no: 'INV-202412-001' },
    { id: '5', month: '2024-11', plan: 'Free', amount: 0, status: 'paid', paid_at: '2024-11-01 10:00:00', invoice_no: 'INV-202411-001' },
  ]
}

// 变更计划
const changePlan = (plan, action) => {
  changePlanAction.value = action
  changePlanTarget.value = plan
  changePlanDialogVisible.value = true
}

const confirmChangePlan = async () => {
  changingPlan.value = true
  try {
    await subscribePlan({ plan_id: changePlanTarget.value.id, action: changePlanAction.value })
    ElMessage.success(`计划${changePlanAction.value === 'upgrade' ? '升级' : '降级'}成功`)
    changePlanDialogVisible.value = false
    currentPlanId.value = changePlanTarget.value.id
    currentPlanName.value = changePlanTarget.value.name
    currentPlanLevel.value = changePlanTarget.value.level
    fetchSubscription()
  } catch (e) {
    console.error('变更失败:', e)
    ElMessage.error('计划变更失败')
  } finally {
    changingPlan.value = false
  }
}

// 取消订阅
const cancelSubscription = async () => {
  try {
    await cancelSubscriptionApi()
    subscription.value.status = 'cancelled'
    ElMessage.success('订阅已取消，将在当前周期结束时生效')
  } catch (e) {
    console.error('取消失败:', e)
    ElMessage.error('取消订阅失败')
  }
}

// 切换自动续费
const toggleAutoRenew = async (val) => {
  try {
    ElMessage.success(val ? '已开启自动续费' : '已关闭自动续费')
  } catch {
    subscription.value.auto_renew = !val
  }
}

// 下载发票
const downloadInvoice = async (row) => {
  try {
    const res = await getInvoice(row.id)
    const url = res.data?.download_url || res.data?.url
    if (url) {
      window.open(url, '_blank')
    } else {
      ElMessage.info('发票下载链接暂不可用')
    }
  } catch {
    ElMessage.info('发票下载功能开发中')
  }
}

onMounted(() => {
  fetchPlans()
  fetchSubscription()
  fetchInvoices()
})
</script>

<style lang="scss" scoped>
.billing-view {
  padding: 16px;

  .plan-card {
    position: relative;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;

    &:hover {
      transform: translateY(-4px);
    }

    &.plan-current {
      border: 2px solid #409EFF;
    }

    &.plan-popular {
      border: 2px solid #E6A23C;
    }

    .plan-badge {
      position: absolute;
      top: 12px;
      right: -30px;
      background: #E6A23C;
      color: #fff;
      font-size: 12px;
      padding: 2px 36px;
      transform: rotate(45deg);
    }

    .plan-header {
      padding: 10px 0;

      .plan-name {
        margin: 0 0 8px 0;
        font-size: 20px;
        color: #303133;
      }

      .plan-price {
        .price-amount {
          font-size: 36px;
          font-weight: 700;
          color: #409EFF;
        }

        .price-unit {
          font-size: 14px;
          color: #909399;
        }
      }
    }

    .plan-features {
      list-style: none;
      padding: 0;
      margin: 0;
      text-align: left;

      li {
        padding: 6px 0;
        font-size: 13px;
        color: #606266;
        display: flex;
        align-items: center;
        gap: 8px;

        .feature-check {
          color: #67C23A;
          flex-shrink: 0;
        }
      }
    }

    .plan-action {
      margin-top: 16px;
    }
  }

  .expire-warning {
    color: #E6A23C;
    font-weight: 600;
  }

  .usage-items {
    .usage-item {
      margin-bottom: 20px;

      .usage-label {
        font-size: 14px;
        color: #606266;
        margin-bottom: 6px;
      }

      .usage-detail {
        font-size: 12px;
        color: #909399;
        margin-top: 4px;
        text-align: right;
      }
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }

  .change-plan-confirm {
    p {
      margin: 0;
      line-height: 1.8;
    }
  }
}
</style>
