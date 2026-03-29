<template>
  <div class="selections-page">
    <div class="page-card">
      <div class="filter-bar">
        <el-form :inline="true" :model="filters" class="demo-form-inline">
          <el-form-item label="选股日期">
            <el-date-picker
              v-model="filters.selection_date"
              type="date"
              placeholder="选择日期"
              value-format="YYYY-MM-DD"
              @change="handleFilterChange"
            />
          </el-form-item>
          <el-form-item label="市场">
            <el-select v-model="filters.market" placeholder="全部" @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="A股" value="A" />
              <el-option label="港股" value="HK" />
              <el-option label="美股" value="US" />
            </el-select>
          </el-form-item>
          <el-form-item label="策略">
            <el-select v-model="filters.strategy_id" placeholder="全部" @change="handleFilterChange">
              <el-option label="全部" value="" />
              <el-option label="A股尾盘策略" value="a-stock-close-swipe" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="fetchData">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="rank" label="排名" width="60" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.score_rank <= 3" type="danger">{{ row.score_rank }}</el-tag>
            <span v-else>{{ row.score_rank }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="股票代码" width="100" />
        <el-table-column prop="name" label="股票名称" width="120" />
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="industry" label="行业" width="120" />
        <el-table-column prop="score" label="评分" width="80" align="right">
          <template #default="{ row }">
            <b>{{ row.score?.toFixed(2) }}</b>
          </template>
        </el-table-column>
        <el-table-column prop="close" label="收盘价" width="80" />
        <el-table-column prop="change_pct" label="当日涨幅" width="100">
          <template #default="{ row }">
            <span :class="row.change_pct > 0 ? 'profit-positive' : 'profit-negative'">
              {{ row.change_pct?.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="volume_ratio" label="量比" width="80" />
        <el-table-column prop="turnover" label="换手率(%)" width="100" />
        <el-table-column prop="capitalization" label="流通市值(亿)" width="120">
          <template #default="{ row }">
            {{ (row.capitalization / 100000000).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="selection_date" label="选股日期" width="110" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="createSignal(row)">生成信号</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && list.length === 0" description="暂无选股结果" />

      <div class="pagination-wrapper" v-if="total > pageSize">
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
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSelections } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const pageSize = ref(20)

const filters = ref({
  selection_date: new Date().toISOString().split('T')[0],
  market: 'A',
  strategy_id: ''
})

const pagination = ref({
  page: 1,
  pageSize: 20
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
    if (filters.value.selection_date) {
      params.selection_date = filters.value.selection_date
    }
    if (filters.value.market) {
      params.market = filters.value.market
    }
    if (filters.value.strategy_id) {
      params.strategy_id = filters.value.strategy_id
    }

    const res = await getSelections(params)
    list.value = res.data || []
    total.value = res.total || 0
    pageSize.value = res.page_size || 20
  } catch (error) {
    console.error('Failed to fetch selections:', error)
    ElMessage.error('获取选股结果失败')
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  pagination.value.page = 1
}

function resetFilters() {
  filters.value = {
    selection_date: new Date().toISOString().split('T')[0],
    market: 'A',
    strategy_id: ''
  }
  pagination.value.page = 1
  fetchData()
}

function createSignal(row) {
  ElMessage.info(`已为 ${row.name}(${row.symbol}) 生成交易信号`)
  // TODO: 打开对话框创建交易信号
}
</script>

<style scoped>
.selections-page {
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
</style>
