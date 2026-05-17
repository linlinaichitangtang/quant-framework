import { defineStore } from 'pinia'
import {
  listModels, getModel, createModel, deleteModel,
  startTraining, getTrainingStatus, getTrainingMetrics,
  predict, getPredictions, getPredictionAccuracy,
  getFeatures, computeFeatures,
  getOnlineLearningStatus, startOnlineLearning, stopOnlineLearning,
  getModelMonitorMetrics, getModelAlerts, triggerRetrain,
  getGPUInfo
} from '@/api/ml'

export const useMLStore = defineStore('ml', {
  state: () => ({
    // 模型列表
    models: [],
    currentModel: null,
    loading: false,

    // 训练状态
    trainingStatus: null,       // 当前训练记录状态
    trainingMetrics: null,      // 当前训练指标
    training: false,            // 是否正在训练
    pollingTimer: null,         // 训练轮询定时器

    // 预测结果
    predictions: [],
    predictionAccuracy: null,
    latestPrediction: null,
    predicting: false,

    // 特征工程
    features: null,             // 可用特征列表
    computedFeatures: null,     // 计算结果
    computing: false,

    // 在线学习
    onlineLearningStatus: null,

    // 模型监控
    monitorMetrics: null,
    alerts: [],
  }),

  getters: {
    /** 活跃模型列表 */
    activeModels(state) {
      return state.models.filter(m => m.status === 'active')
    },

    /** 训练中的模型 */
    trainingModels(state) {
      return state.models.filter(m => m.status === 'training')
    },

    /** 训练进度百分比 */
    trainingProgress(state) {
      if (!state.trainingStatus) return 0
      return state.trainingStatus.progress || 0
    },

    /** 预测准确率 */
    overallAccuracy(state) {
      if (!state.predictionAccuracy) return 0
      return state.predictionAccuracy.accuracy || 0
    },

    /** 特征分类列表 */
    featureCategories(state) {
      if (!state.features || !state.features.categories) return []
      return Object.entries(state.features.categories).map(([key, items]) => ({
        name: key,
        features: items
      }))
    },
  },

  actions: {
    // ========== 模型管理 ==========

    /** 获取模型列表 */
    async fetchModels(params = {}) {
      this.loading = true
      try {
        const data = await listModels(params)
        this.models = data.data || []
        return data
      } catch (error) {
        console.error('获取模型列表失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    /** 获取模型详情 */
    async fetchModel(modelId) {
      this.loading = true
      try {
        const data = await getModel(modelId)
        this.currentModel = data.data
        return data.data
      } catch (error) {
        console.error('获取模型详情失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    /** 创建新模型 */
    async createNewModel(modelData) {
      this.loading = true
      try {
        const data = await createModel(modelData)
        await this.fetchModels()
        return data
      } catch (error) {
        console.error('创建模型失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    /** 删除（归档）模型 */
    async removeModel(modelId) {
      try {
        await deleteModel(modelId)
        this.models = this.models.filter(m => m.id !== modelId)
        if (this.currentModel?.id === modelId) {
          this.currentModel = null
        }
      } catch (error) {
        console.error('删除模型失败:', error)
        throw error
      }
    },

    // ========== 训练 ==========

    /** 启动训练 */
    async startModelTraining(config) {
      this.training = true
      try {
        const data = await startTraining(config)
        // 开始轮询训练状态
        this._startPolling(data.data.record_id)
        return data
      } catch (error) {
        console.error('启动训练失败:', error)
        this.training = false
        throw error
      }
    },

    /** 获取训练状态 */
    async fetchTrainingStatus(recordId) {
      try {
        const data = await getTrainingStatus(recordId)
        this.trainingStatus = data.data
        return data.data
      } catch (error) {
        console.error('获取训练状态失败:', error)
        throw error
      }
    },

    /** 获取训练指标 */
    async fetchTrainingMetrics(recordId) {
      try {
        const data = await getTrainingMetrics(recordId)
        this.trainingMetrics = data.data
        return data.data
      } catch (error) {
        console.error('获取训练指标失败:', error)
        throw error
      }
    },

    /** 开始轮询训练状态 */
    _startPolling(recordId) {
      this._stopPolling()
      this.pollingTimer = setInterval(async () => {
        try {
          const status = await this.fetchTrainingStatus(recordId)
          // 如果训练完成或失败，停止轮询
          if (status.status === 'completed' || status.status === 'failed') {
            this._stopPolling()
            this.training = false
            // 刷新模型列表
            await this.fetchModels()
            // 加载训练指标
            await this.fetchTrainingMetrics(recordId)
          }
        } catch (e) {
          console.error('轮询训练状态失败:', e)
        }
      }, 3000)
    },

    /** 停止轮询 */
    _stopPolling() {
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer)
        this.pollingTimer = null
      }
    },

    // ========== 预测 ==========

    /** 运行预测 */
    async runPrediction(config) {
      this.predicting = true
      try {
        const data = await predict(config)
        this.latestPrediction = data.data
        return data.data
      } catch (error) {
        console.error('运行预测失败:', error)
        throw error
      } finally {
        this.predicting = false
      }
    },

    /** 获取预测历史 */
    async fetchPredictions(params = {}) {
      this.loading = true
      try {
        const data = await getPredictions(params)
        this.predictions = data.data || []
        return data
      } catch (error) {
        console.error('获取预测历史失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    /** 获取预测准确率 */
    async fetchPredictionAccuracy(params = {}) {
      try {
        const data = await getPredictionAccuracy(params)
        this.predictionAccuracy = data.data
        return data.data
      } catch (error) {
        console.error('获取预测准确率失败:', error)
        throw error
      }
    },

    // ========== 特征工程 ==========

    /** 获取可用特征列表 */
    async fetchFeatures() {
      try {
        const data = await getFeatures()
        this.features = data.data
        return data.data
      } catch (error) {
        console.error('获取特征列表失败:', error)
        throw error
      }
    },

    /** 计算指定股票特征 */
    async computeStockFeatures(config) {
      this.computing = true
      try {
        const data = await computeFeatures(config)
        this.computedFeatures = data.data
        return data.data
      } catch (error) {
        console.error('计算特征失败:', error)
        throw error
      } finally {
        this.computing = false
      }
    },

    // ========== 在线学习 ==========

    /** 获取在线学习状态 */
    async fetchOnlineLearningStatus() {
      try {
        const data = await getOnlineLearningStatus()
        this.onlineLearningStatus = data.data
        return data.data
      } catch (error) {
        console.error('获取在线学习状态失败:', error)
        throw error
      }
    },

    /** 启动在线学习 */
    async startOnline(config) {
      try {
        const data = await startOnlineLearning(config)
        return data
      } catch (error) {
        console.error('启动在线学习失败:', error)
        throw error
      }
    },

    /** 停止在线学习 */
    async stopOnline() {
      try {
        const data = await stopOnlineLearning()
        return data
      } catch (error) {
        console.error('停止在线学习失败:', error)
        throw error
      }
    },

    // ========== 模型监控 ==========

    /** 获取监控指标 */
    async fetchMonitorMetrics(params = {}) {
      try {
        const data = await getModelMonitorMetrics(params)
        this.monitorMetrics = data.data
        return data.data
      } catch (error) {
        console.error('获取监控指标失败:', error)
        throw error
      }
    },

    /** 获取告警列表 */
    async fetchAlerts(params = {}) {
      try {
        const data = await getModelAlerts(params)
        this.alerts = data.data || []
        return data
      } catch (error) {
        console.error('获取告警列表失败:', error)
        throw error
      }
    },

    /** 触发重新训练 */
    async retrainModel(modelId) {
      try {
        const data = await triggerRetrain(modelId)
        return data
      } catch (error) {
        console.error('触发重新训练失败:', error)
        throw error
      }
    },

    // ========== GPU ==========

    /** 获取 GPU 信息 */
    async fetchGPUInfo() {
      try {
        const data = await getGPUInfo()
        return data.data
      } catch (error) {
        console.error('获取 GPU 信息失败:', error)
        throw error
      }
    },
  },
})
