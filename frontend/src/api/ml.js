import request from './request'

// ========== 深度学习模型管理 API ==========

// 获取模型列表
export function listModels(params) {
  return request({
    url: '/api/v1/ml/models',
    method: 'get',
    params
  })
}

// 获取模型详情
export function getModel(modelId) {
  return request({
    url: `/api/v1/ml/models/${modelId}`,
    method: 'get'
  })
}

// 创建新模型
export function createModel(data) {
  return request({
    url: '/api/v1/ml/models',
    method: 'post',
    data
  })
}

// 删除（归档）模型
export function deleteModel(modelId) {
  return request({
    url: `/api/v1/ml/models/${modelId}`,
    method: 'delete'
  })
}

// ========== 训练 API ==========

// 启动模型训练
export function startTraining(data) {
  return request({
    url: '/api/v1/ml/train',
    method: 'post',
    data
  })
}

// 获取训练状态
export function getTrainingStatus(recordId) {
  return request({
    url: `/api/v1/ml/train/${recordId}/status`,
    method: 'get'
  })
}

// 获取训练指标
export function getTrainingMetrics(recordId) {
  return request({
    url: `/api/v1/ml/train/${recordId}/metrics`,
    method: 'get'
  })
}

// ========== 预测 API ==========

// 运行预测
export function predict(data) {
  return request({
    url: '/api/v1/ml/predict',
    method: 'post',
    data
  })
}

// 获取预测历史
export function getPredictions(params) {
  return request({
    url: '/api/v1/ml/predictions',
    method: 'get',
    params
  })
}

// 获取预测准确率统计
export function getPredictionAccuracy(params) {
  return request({
    url: '/api/v1/ml/predictions/accuracy',
    method: 'get',
    params
  })
}

// ========== 特征工程 API ==========

// 获取可用特征列表
export function getFeatures() {
  return request({
    url: '/api/v1/ml/features',
    method: 'get'
  })
}

// 计算指定股票特征
export function computeFeatures(data) {
  return request({
    url: '/api/v1/ml/features/compute',
    method: 'post',
    data
  })
}

// ========== 在线学习 API ==========

// 获取在线学习状态
export function getOnlineLearningStatus() {
  return request({
    url: '/api/v1/ml/online-learning/status',
    method: 'get'
  })
}

// 启动在线学习
export function startOnlineLearning(data) {
  return request({
    url: '/api/v1/ml/online-learning/start',
    method: 'post',
    data
  })
}

// 停止在线学习
export function stopOnlineLearning() {
  return request({
    url: '/api/v1/ml/online-learning/stop',
    method: 'post'
  })
}

// ========== 模型监控 API ==========

// 获取模型监控指标
export function getModelMonitorMetrics(params) {
  return request({
    url: '/api/v1/ml/monitor/metrics',
    method: 'get',
    params
  })
}

// 获取模型告警列表
export function getModelAlerts(params) {
  return request({
    url: '/api/v1/ml/monitor/alerts',
    method: 'get',
    params
  })
}

// 触发模型重新训练
export function triggerRetrain(modelId) {
  return request({
    url: `/api/v1/ml/monitor/${modelId}/retrain`,
    method: 'post'
  })
}

// ========== GPU 信息 ==========

// 获取 GPU 信息
export function getGPUInfo() {
  return request({
    url: '/api/v1/ml/gpu/info',
    method: 'get'
  })
}
