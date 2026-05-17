<template>
  <div class="mobile-table">
    <!-- 桌面端：正常表格 -->
    <el-table
      v-if="!isMobile"
      :data="data"
      v-loading="loading"
      :style="{ width: '100%' }"
    >
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth"
      >
        <template #default="scope">
          <slot :name="col.prop" :row="scope.row" :column="col">
            {{ scope.row[col.prop] }}
          </slot>
        </template>
      </el-table-column>
      <!-- 操作列 slot -->
      <slot name="actions" />
    </el-table>

    <!-- 移动端：卡片列表 -->
    <div v-else class="mobile-card-list" v-loading="loading">
      <div
        v-for="(row, index) in data"
        :key="index"
        class="mobile-card"
      >
        <div
          v-for="col in mobileColumns"
          :key="col.prop"
          class="mobile-card-item"
        >
          <span class="mobile-card-label">{{ col.label }}</span>
          <span class="mobile-card-value">
            <slot :name="col.prop" :row="row" :column="col">
              {{ formatValue(row[col.prop], col) }}
            </slot>
          </span>
        </div>
        <!-- 操作区 slot -->
        <div v-if="$slots['mobile-actions']" class="mobile-card-actions">
          <slot name="mobile-actions" :row="row" />
        </div>
      </div>

      <el-empty
        v-if="!loading && data.length === 0"
        description="暂无数据"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  columns: {
    type: Array,
    required: true,
    default: () => []
  },
  data: {
    type: Array,
    required: true,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const isMobile = ref(false)

function checkMobile() {
  isMobile.value = window.innerWidth < 768
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

/**
 * 移动端显示的列（过滤掉 mobile: false 的列）
 */
const mobileColumns = computed(() => {
  return props.columns.filter(col => col.mobile !== false)
})

/**
 * 格式化显示值
 */
function formatValue(value, col) {
  if (value === null || value === undefined) return '-'
  if (col.formatter) return col.formatter(value)
  return value
}
</script>

<style scoped>
.mobile-table {
  width: 100%;
}

.mobile-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 12px 16px;
}

.mobile-card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f2f5;
}

.mobile-card-item:last-of-type {
  border-bottom: none;
}

.mobile-card-label {
  font-size: 13px;
  color: #909399;
  flex-shrink: 0;
  margin-right: 12px;
}

.mobile-card-value {
  font-size: 14px;
  color: #303133;
  text-align: right;
  word-break: break-all;
}

.mobile-card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f2f5;
  margin-top: 4px;
}
</style>
