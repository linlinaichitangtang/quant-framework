<template>
  <div class="ml-model-view">
    <!-- 顶部标题栏 -->
    <div class="page-header">
      <h2>深度学习策略引擎</h2>
      <div class="header-actions">
        <el-button type="success" @click="showCreateDialog = true" :icon="Plus">创建模型</el-button>
      </div>
    </div>

    <!-- Tab 页签切换 -->
    <el-tabs v-model="activeTab" type="border-card" @tab-change="handleTabChange">
      <!-- Tab 1: 模型列表 -->
      <el-tab-pane label="模型管理" name="models">
        <el-table :data="store.models" v-loading="store.loading" stripe style="width: 100%">
          <el-table-column prop="name" label="模型名称" min-width="160" />
          <el-table-column prop="model_type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="modelTypeColor(row.model_type)" size="small">
                {{ modelTypeLabel(row.model_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="准确率" width="100" align="right">
            <template #default="{ row }">
              <span v-if="row.metrics">{{ parseMetrics(row.metrics).accuracy }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="version" label="版本" width="80" align="center" />
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click="openTrainDialog(row)">训练</el-button>
              <el-button size="small" type="success" link @click="openPredictDialog(row)">预测</el-button>
              <el-button size="small" type="info" link @click="viewModelDetail(row)">详情</el-button>
              <el-popconfirm title="确定归档此模型？" @confirm="handleDeleteModel(row.id)">
                <template #reference>
                  <el-button size="small" type="danger" link>归档</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 2: 模型训练 -->
      <el-tab-pane label="模型训练" name="training">
        <el-row :gutter="16">
          <!-- 训练配置面板 -->
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>训练配置</template>
              <el-form :model="trainForm" label-width="100px" size="default">
                <el-form-item label="选择模型">
                  <el-select v-model="trainForm.model_id" placeholder="请选择模型" style="width: 100%" filterable>
                    <el-option
                      v-for="m in store.activeModels"
                      :key="m.id"
                      :label="`${m.name} (${modelTypeLabel(m.model_type)})`"
                      :value="m.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="股票代码">
                  <el-input v-model="trainForm.symbol" placeholder="例如：000001" />
                </el-form-item>
                <el-form-item label="训练轮数">
                  <el-input-number v-model="trainForm.epochs" :min="10" :max="500" :step="10" style="width: 100%" />
                </el-form-item>
                <el-form-item label="批次大小">
                  <el-input-number v-model="trainForm.batch_size" :min="8" :max="256" :step="8" style="width: 100%" />
                </el-form-item>
                <el-form-item label="学习率">
                  <el-input-number v-model="trainForm.learning_rate" :min="0.0001" :max="0.1" :step="0.0001" :precision="4" style="width: 100%" />
                </el-form-item>
                <el-form-item label="序列长度">
                  <el-input-number v-model="trainForm.seq_length" :min="10" :max="120" :step="5" style="width: 100%" />
                </el-form-item>
                <el-form-item label="验证集比例">
                  <el-slider v-model="trainForm.val_split" :min="0.1" :max="0.4" :step="0.05" show-input />
                </el-form-item>
                <el-form-item label="早停耐心">
                  <el-input-number v-model="trainForm.patience" :min="3" :max="50" style="width: 100%" />
                </el-form-item>
                <el-form-item label="初始资金">
                  <el-input-number v-model="trainForm.initial_capital" :min="10000" :step="10000" style="width: 100%" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="handleStartTraining" :loading="store.training" style="width: 100%">
                    启动训练
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-col>

          <!-- 训练进度与指标 -->
          <el-col :span="16">
            <!-- 训练进度 -->
            <el-card shadow="hover" class="training-progress-card">
              <template #header>
                <div class="card-header-row">
                  <span>训练进度</span>
                  <el-tag v-if="store.trainingStatus" :type="statusType(store.trainingStatus.status)">
                    {{ statusText(store.trainingStatus.status) }}
                  </el-tag>
                </div>
              </template>
              <div v-if="store.trainingStatus">
                <el-progress
                  :percentage="store.trainingProgress"
                  :status="store.trainingStatus.status === 'failed' ? 'exception' : store.trainingStatus.status === 'completed' ? 'success' : ''"
                  :stroke-width="20"
                  :text-inside="true"
                />
                <el-descriptions :column="3" border style="margin-top: 16px" size="small">
                  <el-descriptions-item label="当前轮次">
                    {{ store.trainingStatus.current_epoch || 0 }} / {{ store.trainingStatus.total_epochs || 0 }}
                  </el-descriptions-item>
                  <el-descriptions-item label="开始时间">
                    {{ store.trainingStatus.started_at || '-' }}
                  </el-descriptions-item>
                  <el-descriptions-item label="完成时间">
                    {{ store.trainingStatus.completed_at || '-' }}
                  </el-descriptions-item>
                </el-descriptions>
                <el-alert
                  v-if="store.trainingStatus.error_message"
                  :title="'训练失败: ' + store.trainingStatus.error_message"
                  type="error"
                  show-icon
                  style="margin-top: 12px"
                />
              </div>
              <el-empty v-else description="暂无训练任务，请配置参数后启动训练" />
            </el-card>

            <!-- 训练指标图表 -->
            <el-row :gutter="16" style="margin-top: 16px" v-if="store.trainingMetrics">
              <el-col :span="12">
                <el-card shadow="hover">
                  <template #header>Loss 曲线</template>
                  <div ref="lossChartRef" style="height: 320px;"></div>
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card shadow="hover">
                  <template #header>准确率曲线</template>
                  <div ref="accuracyChartRef" style="height: 320px;"></div>
                </el-card>
              </el-col>
            </el-row>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 3: 预测功能 -->
      <el-tab-pane label="预测分析" name="prediction">
        <el-row :gutter="16">
          <!-- 预测配置 -->
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>预测配置</template>
              <el-form :model="predictForm" label-width="100px" size="default">
                <el-form-item label="选择模型">
                  <el-select v-model="predictForm.model_id" placeholder="请选择模型" style="width: 100%" filterable>
                    <el-option
                      v-for="m in store.activeModels"
                      :key="m.id"
                      :label="`${m.name} (${modelTypeLabel(m.model_type)})`"
                      :value="m.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="股票代码">
                  <el-input v-model="predictForm.symbol" placeholder="例如：000001" />
                </el-form-item>
                <el-form-item label="历史天数">
                  <el-input-number v-model="predictForm.days" :min="60" :max="500" :step="10" style="width: 100%" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="handlePredict" :loading="store.predicting" style="width: 100%">
                    运行预测
                  </el-button>
                </el-form-item>
              </el-form>

              <!-- 预测结果 -->
              <el-card v-if="store.latestPrediction" shadow="never" class="prediction-result-card">
                <template #header>预测结果</template>
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="预测方向">
                    <el-tag :type="directionType(store.latestPrediction.direction)">
                      {{ directionLabel(store.latestPrediction.direction) }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="置信度">
                    <el-progress
                      :percentage="Math.round((store.latestPrediction.confidence || 0) * 100)"
                      :color="confidenceColor(store.latestPrediction.confidence)"
                      :stroke-width="16"
                      :text-inside="true"
                    />
                  </el-descriptions-item>
                  <el-descriptions-item label="预测收益率">
                    <span :class="store.latestPrediction.predicted_return >= 0 ? 'profit' : 'loss'">
                      {{ ((store.latestPrediction.predicted_return || 0) * 100).toFixed(2) }}%
                    </span>
                  </el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-card>
          </el-col>

          <!-- 预测历史 -->
          <el-col :span="16">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header-row">
                  <span>预测历史</span>
                  <el-button size="small" @click="handleLoadPredictions">刷新</el-button>
                </div>
              </template>
              <el-table :data="store.predictions" v-loading="store.loading" stripe max-height="500" style="width: 100%">
                <el-table-column prop="symbol" label="股票" width="100" />
                <el-table-column label="预测方向" width="100">
                  <template #default="{ row }">
                    <el-tag :type="directionType(row.predicted_direction)" size="small">
                      {{ directionLabel(row.predicted_direction) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="实际方向" width="100">
                  <template #default="{ row }">
                    <el-tag v-if="row.actual_direction" :type="directionType(row.actual_direction)" size="small">
                      {{ directionLabel(row.actual_direction) }}
                    </el-tag>
                    <span v-else class="text-muted">待验证</span>
                  </template>
                </el-table-column>
                <el-table-column label="置信度" width="120" align="right">
                  <template #default="{ row }">
                    {{ row.confidence != null ? (row.confidence * 100).toFixed(1) + '%' : '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="预测收益率" width="120" align="right">
                  <template #default="{ row }">
                    <span v-if="row.predicted_return != null" :class="row.predicted_return >= 0 ? 'profit' : 'loss'">
                      {{ (row.predicted_return * 100).toFixed(2) }}%
                    </span>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="实际收益率" width="120" align="right">
                  <template #default="{ row }">
                    <span v-if="row.actual_return != null" :class="row.actual_return >= 0 ? 'profit' : 'loss'">
                      {{ (row.actual_return * 100).toFixed(2) }}%
                    </span>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="预测时间" width="170">
                  <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
                </el-table-column>
              </el-table>

              <!-- 准确率统计 -->
              <div v-if="store.predictionAccuracy" class="accuracy-summary">
                <el-descriptions :column="4" border size="small" style="margin-top: 16px">
                  <el-descriptions-item label="总预测数">{{ store.predictionAccuracy.total }}</el-descriptions-item>
                  <el-descriptions-item label="正确数">{{ store.predictionAccuracy.correct }}</el-descriptions-item>
                  <el-descriptions-item label="准确率">
                    <span class="profit">{{ (store.predictionAccuracy.accuracy * 100).toFixed(1) }}%</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="上涨准确率">
                    <span v-if="store.predictionAccuracy.by_direction?.up">
                      {{ (store.predictionAccuracy.by_direction.up.accuracy * 100).toFixed(1) }}%
                    </span>
                    <span v-else>-</span>
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 4: 特征工程 -->
      <el-tab-pane label="特征工程" name="features">
        <el-row :gutter="16">
          <!-- 特征计算面板 -->
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>特征计算</template>
              <el-form :model="featureForm" label-width="100px" size="default">
                <el-form-item label="股票代码">
                  <el-input v-model="featureForm.symbol" placeholder="例如：000001" />
                </el-form-item>
                <el-form-item label="历史天数">
                  <el-input-number v-model="featureForm.days" :min="60" :max="500" :step="10" style="width: 100%" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="handleComputeFeatures" :loading="store.computing" style="width: 100%">
                    计算特征
                  </el-button>
                </el-form-item>
              </el-form>

              <!-- 计算结果概览 -->
              <el-card v-if="store.computedFeatures" shadow="never" class="computed-features-card">
                <template #header>计算结果</template>
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="特征数量">{{ store.computedFeatures.count }}</el-descriptions-item>
                  <el-descriptions-item label="数据总行数">{{ store.computedFeatures.total_rows }}</el-descriptions-item>
                </el-descriptions>
              </el-card>
            </el-card>
          </el-col>

          <!-- 特征列表 -->
          <el-col :span="16">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header-row">
                  <span>可用特征列表 ({{ store.features?.count || 0 }} 个)</span>
                  <el-button size="small" @click="handleLoadFeatures">刷新</el-button>
                </div>
              </template>
              <el-collapse v-if="store.featureCategories.length > 0">
                <el-collapse-item
                  v-for="cat in store.featureCategories"
                  :key="cat.name"
                  :title="categoryLabel(cat.name)"
                  :name="cat.name"
                >
                  <div class="feature-tags">
                    <el-tag
                      v-for="f in cat.features"
                      :key="f"
                      size="small"
                      class="feature-tag"
                    >
                      {{ f }}
                    </el-tag>
                  </div>
                </el-collapse-item>
              </el-collapse>
              <el-empty v-else description="点击刷新加载特征列表" />

              <!-- 计算结果详情 -->
              <div v-if="store.computedFeatures" class="computed-features-detail">
                <el-divider content-position="left">最新特征值</el-divider>
                <el-descriptions :column="3" border size="small">
                  <el-descriptions-item
                    v-for="(value, key) in store.computedFeatures.features"
                    :key="key"
                    :label="key"
                  >
                    <span :class="value != null && value > 0 ? 'profit' : value != null && value < 0 ? 'loss' : ''">
                      {{ value != null ? value.toFixed(4) : 'N/A' }}
                    </span>
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建模型对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建新模型" width="520px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" :rules="createRules" ref="createFormRef">
        <el-form-item label="模型名称" prop="name">
          <el-input v-model="createForm.name" placeholder="例如：LSTM-价格预测-v1" />
        </el-form-item>
        <el-form-item label="模型类型" prop="model_type">
          <el-select v-model="createForm.model_type" style="width: 100%">
            <el-option label="LSTM" value="lstm" />
            <el-option label="Transformer" value="transformer" />
            <el-option label="DQN" value="dqn" />
            <el-option label="PPO" value="ppo" />
            <el-option label="XGBoost" value="xgboost" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="模型用途描述" />
        </el-form-item>
        <el-divider content-position="left">超参数配置</el-divider>
        <el-form-item label="学习率">
          <el-input-number v-model="createForm.hyperparams.learning_rate" :min="0.0001" :max="0.1" :step="0.0001" :precision="4" style="width: 100%" />
        </el-form-item>
        <el-form-item label="隐藏层大小">
          <el-input-number v-model="createForm.hyperparams.hidden_size" :min="32" :max="512" :step="32" style="width: 100%" />
        </el-form-item>
        <el-form-item label="Dropout">
          <el-slider v-model="createForm.hyperparams.dropout" :min="0" :max="0.5" :step="0.05" show-input />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateModel" :loading="store.loading">创建</el-button>
      </template>
    </el-dialog>

    <!-- 模型详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="模型详情" width="600px" destroy-on-close>
      <template v-if="detailModel">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="模型名称">{{ detailModel.name }}</el-descriptions-item>
          <el-descriptions-item label="模型类型">
            <el-tag :type="modelTypeColor(detailModel.model_type)">{{ modelTypeLabel(detailModel.model_type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detailModel.status)">{{ statusText(detailModel.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="版本">{{ detailModel.version }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ detailModel.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(detailModel.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(detailModel.updated_at) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">模型指标</el-divider>
        <el-descriptions v-if="detailModel.metrics" :column="2" border size="small">
          <el-descriptions-item
            v-for="(value, key) in parseMetrics(detailModel.metrics)"
            :key="key"
            :label="key"
          >
            {{ value }}
          </el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="暂无指标数据" :image-size="60" />

        <el-divider content-position="left">超参数</el-divider>
        <el-descriptions v-if="detailModel.hyperparams" :column="2" border size="small">
          <el-descriptions-item
            v-for="(value, key) in parseMetrics(detailModel.hyperparams)"
            :key="key"
            :label="key"
          >
            {{ value }}
          </el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="暂无超参数" :image-size="60" />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { useMLStore } from '@/stores/ml'

const store = useMLStore()

// ========== 页面状态 ==========
const activeTab = ref('models')

// ========== 创建模型 ==========
const showCreateDialog = ref(false)
const createFormRef = ref(null)
const createForm = reactive({
  name: '',
  model_type: 'lstm',
  description: '',
  hyperparams: {
    learning_rate: 0.001,
    hidden_size: 128,
    dropout: 0.2,
  },
})
const createRules = {
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  model_type: [{ required: true, message: '请选择模型类型', trigger: 'change' }],
}

// ========== 训练表单 ==========
const trainForm = reactive({
  model_id: null,
  symbol: '000001',
  epochs: 100,
  batch_size: 32,
  learning_rate: 0.001,
  seq_length: 60,
  val_split: 0.2,
  patience: 10,
  initial_capital: 100000,
  commission: 0.0003,
})

// ========== 预测表单 ==========
const predictForm = reactive({
  model_id: null,
  symbol: '000001',
  days: 120,
})

// ========== 特征计算表单 ==========
const featureForm = reactive({
  symbol: '000001',
  days: 120,
})

// ========== 模型详情 ==========
const showDetailDialog = ref(false)
const detailModel = ref(null)

// ========== 图表 refs ==========
const lossChartRef = ref(null)
const accuracyChartRef = ref(null)
let charts = []

// ========== 工具函数 ==========

/** 模型类型标签 */
function modelTypeLabel(type) {
  const map = { lstm: 'LSTM', transformer: 'Transformer', dqn: 'DQN', ppo: 'PPO', xgboost: 'XGBoost' }
  return map[type] || type
}

/** 模型类型颜色 */
function modelTypeColor(type) {
  const map = { lstm: '', transformer: 'success', dqn: 'warning', ppo: 'danger', xgboost: 'info' }
  return map[type] || ''
}

/** 状态标签 */
function statusText(s) {
  const map = { active: '活跃', archived: '已归档', training: '训练中', pending: '等待中', running: '运行中', completed: '已完成', failed: '失败' }
  return map[s] || s
}

/** 状态颜色 */
function statusType(s) {
  const map = { active: 'success', archived: 'info', training: 'warning', pending: 'warning', running: '', completed: 'success', failed: 'danger' }
  return map[s] || ''
}

/** 预测方向标签 */
function directionLabel(d) {
  const map = { up: '上涨', down: '下跌', flat: '震荡' }
  return map[d] || d || '-'
}

/** 预测方向颜色 */
function directionType(d) {
  const map = { up: 'danger', down: 'success', flat: 'info' }
  return map[d] || ''
}

/** 置信度颜色 */
function confidenceColor(v) {
  if (v >= 0.8) return '#67C23A'
  if (v >= 0.6) return '#E6A23C'
  return '#F56C6C'
}

/** 特征分类标签 */
function categoryLabel(key) {
  const map = {
    price_based: '价格特征',
    moving_averages: '均线特征',
    volatility: '波动率特征',
    volume: '成交量特征',
    momentum: '动量特征',
    trend: '趋势特征',
    pattern: 'K线形态',
    statistical: '统计特征',
    cross_features: '交叉特征',
  }
  return `${map[key] || key} (${key})`
}

/** 格式化日期 */
function formatDate(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN')
}

/** 解析 JSON 指标 */
function parseMetrics(str) {
  if (!str) return {}
  try {
    return typeof str === 'string' ? JSON.parse(str) : str
  } catch {
    return {}
  }
}

// ========== 事件处理 ==========

/** Tab 切换 */
function handleTabChange(tab) {
  if (tab === 'models') {
    store.fetchModels()
  } else if (tab === 'training') {
    store.fetchModels()
  } else if (tab === 'prediction') {
    store.fetchModels()
    store.fetchPredictions()
    store.fetchPredictionAccuracy()
  } else if (tab === 'features') {
    store.fetchFeatures()
  }
}

/** 创建模型 */
async function handleCreateModel() {
  try {
    await createFormRef.value?.validate()
  } catch { return }

  try {
    await store.createNewModel({
      name: createForm.name,
      model_type: createForm.model_type,
      description: createForm.description,
      hyperparams: createForm.hyperparams,
    })
    ElMessage.success('模型创建成功')
    showCreateDialog.value = false
    createForm.name = ''
    createForm.description = ''
  } catch (e) {
    ElMessage.error('创建模型失败: ' + (e?.response?.data?.detail || e.message))
  }
}

/** 删除模型 */
async function handleDeleteModel(id) {
  try {
    await store.removeModel(id)
    ElMessage.success('模型已归档')
  } catch (e) {
    ElMessage.error('归档失败')
  }
}

/** 打开训练对话框 */
function openTrainDialog(model) {
  activeTab.value = 'training'
  trainForm.model_id = model.id
}

/** 打开预测对话框 */
function openPredictDialog(model) {
  activeTab.value = 'prediction'
  predictForm.model_id = model.id
}

/** 查看模型详情 */
function viewModelDetail(model) {
  detailModel.value = model
  showDetailDialog.value = true
}

/** 启动训练 */
async function handleStartTraining() {
  if (!trainForm.model_id) {
    ElMessage.warning('请先选择模型')
    return
  }
  try {
    const model = store.models.find(m => m.id === trainForm.model_id)
    const result = await store.startModelTraining({
      model_id: trainForm.model_id,
      model_type: model?.model_type || 'lstm',
      symbol: trainForm.symbol,
      epochs: trainForm.epochs,
      batch_size: trainForm.batch_size,
      learning_rate: trainForm.learning_rate,
      seq_length: trainForm.seq_length,
      val_split: trainForm.val_split,
      patience: trainForm.patience,
      initial_capital: trainForm.initial_capital,
      commission: trainForm.commission,
    })
    ElMessage.success('训练已启动')
  } catch (e) {
    ElMessage.error('启动训练失败: ' + (e?.response?.data?.detail || e.message))
  }
}

/** 运行预测 */
async function handlePredict() {
  if (!predictForm.model_id) {
    ElMessage.warning('请先选择模型')
    return
  }
  try {
    await store.runPrediction({
      model_id: predictForm.model_id,
      symbol: predictForm.symbol,
      days: predictForm.days,
    })
    ElMessage.success('预测完成')
    // 刷新预测历史和准确率
    store.fetchPredictions()
    store.fetchPredictionAccuracy()
  } catch (e) {
    ElMessage.error('预测失败: ' + (e?.response?.data?.detail || e.message))
  }
}

/** 加载预测历史 */
function handleLoadPredictions() {
  store.fetchPredictions()
  store.fetchPredictionAccuracy()
}

/** 计算特征 */
async function handleComputeFeatures() {
  try {
    await store.computeStockFeatures({
      symbol: featureForm.symbol,
      days: featureForm.days,
    })
    ElMessage.success('特征计算完成')
  } catch (e) {
    ElMessage.error('特征计算失败: ' + (e?.response?.data?.detail || e.message))
  }
}

/** 加载特征列表 */
function handleLoadFeatures() {
  store.fetchFeatures()
}

// ========== 图表 ==========

/** 初始化训练指标图表 */
function initTrainingCharts() {
  disposeCharts()
  const metrics = store.trainingMetrics
  if (!metrics || !metrics.train_metrics) return

  const trainMetrics = metrics.train_metrics
  const lossData = trainMetrics.loss || []
  const valLossData = trainMetrics.val_loss || []
  const accuracyData = trainMetrics.val_accuracy || []

  if (lossData.length > 0) {
    initLossChart(lossData, valLossData)
  }
  if (accuracyData.length > 0) {
    initAccuracyChart(accuracyData)
  }
}

function initLossChart(trainLoss, valLoss) {
  if (!lossChartRef.value) return
  const chart = echarts.init(lossChartRef.value)
  charts.push(chart)

  const epochs = trainLoss.map((_, i) => `Epoch ${i + 1}`)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['训练 Loss', '验证 Loss'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: epochs, boundaryGap: false },
    yAxis: { type: 'value', name: 'Loss' },
    series: [
      {
        name: '训练 Loss',
        type: 'line',
        data: trainLoss,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2 },
      },
      {
        name: '验证 Loss',
        type: 'line',
        data: valLoss,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, type: 'dashed' },
      },
    ],
  })
}

function initAccuracyChart(accuracy) {
  if (!accuracyChartRef.value) return
  const chart = echarts.init(accuracyChartRef.value)
  charts.push(chart)

  const epochs = accuracy.map((_, i) => `Epoch ${i + 1}`)
  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: p => `${p[0].name}<br/>准确率: ${(p[0].value * 100).toFixed(1)}%`
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: epochs, boundaryGap: false },
    yAxis: {
      type: 'value',
      name: '准确率',
      axisLabel: { formatter: v => (v * 100).toFixed(0) + '%' },
      min: 0,
      max: 1,
    },
    series: [{
      type: 'line',
      data: accuracy,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: '#67C23A' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
          { offset: 1, color: 'rgba(103, 194, 58, 0.02)' },
        ]),
      },
    }],
  })
}

function disposeCharts() {
  charts.forEach(c => c?.dispose())
  charts = []
}

function handleResize() {
  charts.forEach(c => c?.resize())
}

// 监听训练指标变化，更新图表
watch(() => store.trainingMetrics, (val) => {
  if (val) {
    nextTick(() => initTrainingCharts())
  }
})

// ========== 生命周期 ==========
onMounted(() => {
  store.fetchModels()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  store._stopPolling()
  disposeCharts()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.ml-model-view {
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
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.training-progress-card {
  margin-bottom: 16px;
}
.prediction-result-card {
  margin-top: 16px;
}
.computed-features-card {
  margin-top: 16px;
}
.computed-features-detail {
  margin-top: 16px;
}
.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.feature-tag {
  margin: 0;
}
.accuracy-summary {
  margin-top: 16px;
}
.profit {
  color: #67C23A;
  font-weight: 600;
}
.loss {
  color: #F56C6C;
  font-weight: 600;
}
.text-muted {
  color: #909399;
  font-size: 12px;
}
</style>
