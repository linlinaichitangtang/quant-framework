<template>
  <div class="trades-page">
    <div class="page-card">
      <div class="filter-bar">
        <el-form :inline="true" :model="filters">
          <el-form-item label="股票代码">
            <el-input v-model="filters.symbol" placeholder="请输入" clear @clear="fetchData" />
          </el-form-item>
          <el-form-item label="市场">
            <el-select v-model="filters.market" placeholder="全部" @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="A股" value="A" />
              <el-option label="港股" value="HK" />
              <el-option label="美股" value="US" />
            </el-select>
          </el-form-item>
          <el-form-item label>方向</el-form-item>
            <el-select v-model="filters.side" placeholder="全部" @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="买入" value="BUY" />
              <el-option label="卖出" value="SELL" />
            </el-select>
          <el-form-item label="状态">
            <el-select v-model="filters.status" placeholder="全部" @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="已成交" value="FILLED" />
              <el-option label="待成交" value="PENDING" />
              <el-option label="已取消" value="CANCELLED" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchData">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="order_id" label="订单ID" width="180" />
        <el-table-column prop="symbol" label="股票代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="market" label="市场" width="60" />
        <el-table-column prop="side" label="方向" width="70">
          <template #default="{ row }">
            <el-tag :type="row.side === 'BUY' ? 'danger' : 'success'">
              {{ row.side === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="80" />
        <el-table-column prop="price" label="成交价格" width="100" />
        <el-table-column prop="amount" label="成交金额" width="120">
          <template #default="{ row }">
            ¥{{ row.amount?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="commission" label="手续费" width="80">
          <template #default="{ row }">
            ¥{{ row.commission?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="strategy_name" label="策略" width="150" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="交易时间" width="170" />
        <el-table-column label="详情" width="80">
          <template #default="{ row }">
            <el-button type="primary" size="small" link>查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && list.length === 0" description="暂无交易记录" />

      <div class="pagination-wrapper" v-if="total > pagination.pageSize">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>

      <!-- 统计卡片 -->
      <div class="stats-summary" style="margin-top: 20px;">
        <el-row :gutter="16">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-title">今日成交笔数</div>
              <div class="stat-value">{{ todayStats.count }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-title">今日买入金额</div>
              <div class="stat-value">¥{{ todayStats.buyAmount?.toFixed(0) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-title">今日卖出金额</div>
              <div class="stat-value">¥{{ todayStats.sellAmount?.toFixed(0) }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-title">今日净买入</div>
              <div :class="['stat-value', (todayStats.buyAmount - todayStats.sellAmount) > 0 ? 'profit-positive' : 'profit-negative']">
                ¥{{ (todayStats.buyAmount - todayStats.sellAmount)?.toFixed(0) }}
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getTrades } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const list = ref([])
const total = ref(0)

const filters = ref({
  symbol: '',
  market: '',
  side: '',
  status: ''
})

const pagination = ref({
  page: 1,
  pageSize: 20
})

const todayStats = computed(() => {
  const today = new Date().toDateString()
  const todayTrades = list.value.filter(t => {
    return new Date(t.created_at).toDateString() === today
  })
  const buyAmount = todayTrades
    .filter(t => t.side === 'BUY' && t.status === 'FILLED')
    .reduce((sum, t) => sum + (t.amount || 0), 0)
  const sellAmount = todayTrades
    .filter(t => t.side === 'SELL' && t.status === 'FILLED')
    .reduce((sum, t) => sum + (t.amount || 0), 0)
  return {
    count: todayTrades.length,
    buyAmount,
    sellAmount
  }
})

onMounted(() => {
  fetchData()
})

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize
    }
    Object.keys(filters.value).forEach(key => {
      if (filters.value[key]) {
        params[key] = filters.value[key]
      }
    })

    const res = await getTrades(params)
    list.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    console.error('Failed to fetch trades:', error)
    ElMessage.error('获取交易记录失败')
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  pagination.value.page = 1
  fetchData()
}

function resetFilters() {
  filters.value = {
    symbol: '',
    market: '',
    side: '',
    status: ''
  }
  pagination.value.page = 1
  fetchData()
}

function getStatusType(status) {
  const map = {
    'FILLED': 'success',
    'PENDING': 'warning',
    'CANCELLED': 'info'
  }
  return map[status] || 'info'
}

function getStatusText(status) {
  const map = {
    'FILLED': '已成交',
    'PENDING': '待成交',
    'CANCELLED': '已取消'
  }
  return map[status] || status
}
</script>

<style scoped>
.trades-page {
  padding: 0;
}

.filter-bar {
  margin-bottom: 16px;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

@media screen and (max-width: 767px) {
  .trades-page .stats-summary {
    .el-row {
      .el-col {
        margin-bottom: 8px;
      }
    }
  }
}
</style>
