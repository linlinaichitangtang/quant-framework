import request from './request'

// ========== 认证 API ==========

// 用户登录
export function login(data) {
  return request({
    url: '/api/v1/auth/login',
    method: 'post',
    data
  })
}

// 用户注册
export function register(data) {
  return request({
    url: '/api/v1/auth/register',
    method: 'post',
    data
  })
}

// 刷新 Token
export function refreshToken(data) {
  return request({
    url: '/api/v1/auth/refresh',
    method: 'post',
    data
  })
}

// 获取当前用户信息
export function getCurrentUser() {
  return request({
    url: '/api/v1/auth/me',
    method: 'get'
  })
}

// 修改密码
export function changePassword(data) {
  return request({
    url: '/api/v1/auth/change-password',
    method: 'post',
    data
  })
}

// ========== 概览统计 ==========
export function getOverview() {
  return request({
    url: '/api/v1/overview',
    method: 'get'
  })
}

// 获取持仓列表
export function getPositions(params) {
  return request({
    url: '/api/v1/positions',
    method: 'get',
    params
  })
}

// 获取选股结果
export function getSelections(params) {
  return request({
    url: '/api/v1/selections',
    method: 'get',
    params
  })
}

// 获取交易信号
export function getSignals(params) {
  return request({
    url: '/api/v1/signals',
    method: 'get',
    params
  })
}

// 创建交易信号
export function createSignal(data) {
  return request({
    url: '/api/v1/signals',
    method: 'post',
    data
  })
}

// 获取交易记录
export function getTrades(params) {
  return request({
    url: '/api/v1/trades',
    method: 'get',
    params
  })
}

// 获取系统日志
export function getLogs(params) {
  return request({
    url: '/api/v1/logs',
    method: 'get',
    params
  })
}

// 执行交易信号
export function executeSignal(signalId, data) {
  return request({
    url: `/api/v1/fmz/execute/${signalId}`,
    method: 'post',
    data
  })
}

// 获取FMZ账户信息
export function getFmzAccount() {
  return request({
    url: '/api/v1/fmz/account',
    method: 'get'
  })
}

// 健康检查
export function healthCheck() {
  return request({
    url: '/api/v1/health',
    method: 'get'
  })
}

// ========== 项目分享与协作 API ==========

// 项目导出
export function exportProject(data) {
  return request({
    url: '/api/v1/project/export',
    method: 'post',
    data
  })
}

// 获取导出历史
export function getExportHistory() {
  return request({
    url: '/api/v1/project/exports',
    method: 'get'
  })
}

// 下载导出文件
export function downloadExportFile(exportId) {
  return request({
    url: `/api/v1/project/exports/${exportId}/download`,
    method: 'get',
    responseType: 'blob'
  })
}

// 删除导出文件
export function deleteExportFile(exportId) {
  return request({
    url: `/api/v1/project/exports/${exportId}`,
    method: 'delete'
  })
}

// 项目导入
export function importProject(data) {
  return request({
    url: '/api/v1/project/import',
    method: 'post',
    data
  })
}

// ========== 项目模板 API ==========

// 获取我的模板
export function getMyTemplates(params) {
  return request({
    url: '/api/v1/templates',
    method: 'get',
    params
  })
}

// 保存为模板
export function saveTemplate(data) {
  return request({
    url: '/api/v1/templates',
    method: 'post',
    data
  })
}

// 更新模板
export function updateTemplate(id, data) {
  return request({
    url: `/api/v1/templates/${id}`,
    method: 'put',
    data
  })
}

// 删除模板
export function deleteTemplate(id) {
  return request({
    url: `/api/v1/templates/${id}`,
    method: 'delete'
  })
}

// 使用模板创建项目
export function useTemplate(templateId) {
  return request({
    url: `/api/v1/templates/${templateId}/use`,
    method: 'post'
  })
}

// 获取模板市场列表
export function getMarketTemplates(params) {
  return request({
    url: '/api/v1/templates/market',
    method: 'get',
    params
  })
}

// 安装市场模板
export function installTemplate(templateId) {
  return request({
    url: `/api/v1/templates/market/${templateId}/install`,
    method: 'post'
  })
}

// 上传模板封面
export function uploadTemplateCover(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/api/v1/templates/cover',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// ========== 协作功能 API ==========

// 获取项目权限
export function getProjectPermission() {
  return request({
    url: '/api/v1/project/permission',
    method: 'get'
  })
}

// 更新项目权限
export function updateProjectPermission(data) {
  return request({
    url: '/api/v1/project/permission',
    method: 'put',
    data
  })
}

// 获取分享链接列表
export function getShareLinks() {
  return request({
    url: '/api/v1/project/share-links',
    method: 'get'
  })
}

// 创建分享链接
export function createShareLink(data) {
  return request({
    url: '/api/v1/project/share-links',
    method: 'post',
    data
  })
}

// 撤销分享链接
export function revokeShareLink(linkId) {
  return request({
    url: `/api/v1/project/share-links/${linkId}`,
    method: 'delete'
  })
}

// 获取访问统计
export function getAccessStats() {
  return request({
    url: '/api/v1/project/access-stats',
    method: 'get'
  })
}

// 获取最近访问记录
export function getRecentAccess(params) {
  return request({
    url: '/api/v1/project/recent-access',
    method: 'get',
    params
  })
}

// ========== 回测 API ==========

// 获取回测结果列表
export function getBacktestResults(params) {
  return request({
    url: '/api/v1/backtest/results',
    method: 'get',
    params
  })
}

// 获取回测结果详情
export function getBacktestDetail(backtestId) {
  return request({
    url: `/api/v1/backtest/results/${backtestId}`,
    method: 'get'
  })
}

// 获取回测交易明细
export function getBacktestTrades(backtestId) {
  return request({
    url: `/api/v1/backtest/results/${backtestId}/trades`,
    method: 'get'
  })
}

// 运行新回测
export function runBacktest(data) {
  return request({
    url: '/api/v1/backtest/run',
    method: 'post',
    data
  })
}

// 删除回测结果
export function deleteBacktest(backtestId) {
  return request({
    url: `/api/v1/backtest/results/${backtestId}`,
    method: 'delete'
  })
}

// ========== 期权 API ==========

// 获取期权链
export function getOptionChain(params) {
  return request({
    url: '/api/v1/options/chain',
    method: 'get',
    params
  })
}

// 计算希腊字母
export function getOptionGreeks(params) {
  return request({
    url: '/api/v1/options/greeks',
    method: 'get',
    params
  })
}

// 计算隐含波动率
export function getOptionIV(params) {
  return request({
    url: '/api/v1/options/iv',
    method: 'get',
    params
  })
}

// 计算组合盈亏
export function getOptionStrategyPnl(data, params) {
  return request({
    url: '/api/v1/options/strategy/pnl',
    method: 'post',
    data,
    params
  })
}

// 获取期权持仓列表
export function getOptionPositions(params) {
  return request({
    url: '/api/v1/options/positions',
    method: 'get',
    params
  })
}

// 创建期权持仓
export function createOptionPosition(data) {
  return request({
    url: '/api/v1/options/positions',
    method: 'post',
    data
  })
}

// 删除期权持仓
export function deleteOptionPosition(positionId) {
  return request({
    url: `/api/v1/options/positions/${positionId}`,
    method: 'delete'
  })
}

// ========== 交易账户 API ==========

// 获取账户列表
export function getAccounts(params) {
  return request({
    url: '/api/v1/accounts',
    method: 'get',
    params
  })
}

// 创建账户
export function createAccount(data) {
  return request({
    url: '/api/v1/accounts',
    method: 'post',
    data
  })
}

// 更新账户
export function updateAccount(id, data) {
  return request({
    url: `/api/v1/accounts/${id}`,
    method: 'put',
    data
  })
}

// 删除账户
export function deleteAccount(id) {
  return request({
    url: `/api/v1/accounts/${id}`,
    method: 'delete'
  })
}

// 设置默认账户
export function setDefaultAccount(id) {
  return request({
    url: `/api/v1/accounts/${id}/set-default`,
    method: 'post'
  })
}

// ========== 风控 API ==========

// 获取风控规则列表
export function getRiskRules(params) {
  return request({
    url: '/api/v1/risk/rules',
    method: 'get',
    params
  })
}

// 创建风控规则
export function createRiskRule(data) {
  return request({
    url: '/api/v1/risk/rules',
    method: 'post',
    data
  })
}

// 更新风控规则
export function updateRiskRule(id, data) {
  return request({
    url: `/api/v1/risk/rules/${id}`,
    method: 'put',
    data
  })
}

// 删除风控规则
export function deleteRiskRule(id) {
  return request({
    url: `/api/v1/risk/rules/${id}`,
    method: 'delete'
  })
}

// 获取风控事件列表
export function getRiskEvents(params) {
  return request({
    url: '/api/v1/risk/events',
    method: 'get',
    params
  })
}

// 风控检查
export function checkRisk(data) {
  return request({
    url: '/api/v1/risk/check',
    method: 'post',
    data
  })
}

// ========== 多租户管理 ==========
export const getTenants = (params) => request.get('/tenant', { params })
export const getTenant = (tenantId) => request.get(`/tenant/${tenantId}`)
export const createTenant = (data) => request.post('/tenant', data)
export const updateTenant = (tenantId, data) => request.put(`/tenant/${tenantId}`, data)
export const deleteTenant = (tenantId) => request.delete(`/tenant/${tenantId}`)
export const getTenantUsage = (tenantId, params) => request.get(`/tenant/${tenantId}/usage`, { params })
export const updateWhitelabel = (tenantId, data) => request.put(`/tenant/${tenantId}/whitelabel`, data)
export const subscribeTenant = (tenantId, data) => request.post(`/tenant/${tenantId}/subscribe`, data)

// ========== 插件市场 ==========
export const getPlugins = (params) => request.get('/plugins', { params })
export const getPlugin = (pluginId) => request.get(`/plugins/${pluginId}`)
export const publishPlugin = (data) => request.post('/plugins', data)
export const updatePlugin = (pluginId, data) => request.put(`/plugins/${pluginId}`, data)
export const deletePlugin = (pluginId) => request.delete(`/plugins/${pluginId}`)
export const installPlugin = (pluginId, data) => request.post(`/plugins/${pluginId}/install`, data)
export const uninstallPlugin = (pluginId) => request.delete(`/plugins/${pluginId}/install`)
export const executePlugin = (pluginId, data) => request.post(`/plugins/${pluginId}/execute`, data)
export const ratePlugin = (pluginId, data) => request.post(`/plugins/${pluginId}/rate`, data)

// ========== 计费管理 ==========
export const getBillingPlans = () => request.get('/billing/plans')
export const getCurrentSubscription = () => request.get('/billing/current')
export const subscribePlan = (data) => request.post('/billing/subscribe', data)
export const cancelSubscription = () => request.post('/billing/cancel')
export const getBillingUsage = (params) => request.get('/billing/usage', { params })
export const getInvoices = (params) => request.get('/billing/invoices', { params })
export const getInvoice = (invoiceId) => request.get(`/billing/invoices/${invoiceId}`)

// ========== 开放 API ==========
export const getOpenAPIKeys = () => request.get('/openapi/keys')
export const createOpenAPIKey = (data) => request.post('/openapi/keys', data)
export const revokeOpenAPIKey = (keyId) => request.delete(`/openapi/keys/${keyId}`)
export const rotateOpenAPIKey = (keyId) => request.post(`/openapi/keys/${keyId}/rotate`)

// ========== AI 智能分析 ==========

// AI 对话
export function aiChat(data) {
  return request({
    url: '/api/v1/ai/chat',
    method: 'post',
    data
  })
}

// 获取 AI 会话列表
export function getAIChatSessions(params) {
  return request({
    url: '/api/v1/ai/sessions',
    method: 'get',
    params
  })
}

// 获取 AI 会话详情
export function getAIChatSession(sessionId) {
  return request({
    url: `/api/v1/ai/sessions/${sessionId}`,
    method: 'get'
  })
}

// 删除 AI 会话
export function deleteAIChatSession(sessionId) {
  return request({
    url: `/api/v1/ai/sessions/${sessionId}`,
    method: 'delete'
  })
}

// 市场情绪分析
export function analyzeSentiment(data) {
  return request({
    url: '/api/v1/ai/sentiment',
    method: 'post',
    data
  })
}

// 获取情绪历史
export function getSentimentHistory(params) {
  return request({
    url: '/api/v1/ai/sentiment/history',
    method: 'get',
    params
  })
}

// 异常检测
export function detectAnomalies(data) {
  return request({
    url: '/api/v1/ai/anomaly/detect',
    method: 'post',
    data
  })
}

// 获取异常记录
export function getAnomalyRecords(params) {
  return request({
    url: '/api/v1/ai/anomaly/records',
    method: 'get',
    params
  })
}

// 策略归因分析
export function analyzeAttribution(data) {
  return request({
    url: '/api/v1/ai/attribution',
    method: 'post',
    data
  })
}

// 自然语言查询
export function naturalLanguageQuery(data) {
  return request({
    url: '/api/v1/ai/query',
    method: 'post',
    data
  })
}

// 获取策略建议
export function getStrategyAdvice(data) {
  return request({
    url: '/api/v1/ai/advice',
    method: 'post',
    data
  })
}

// ========== 算法交易 ==========
export const createTWAPOrder = (data) => request.post('/algo/orders/twap', data)
export const createVWAPOrder = (data) => request.post('/algo/orders/vwap', data)
export const createIcebergOrder = (data) => request.post('/algo/orders/iceberg', data)
export const createSmartOrder = (data) => request.post('/algo/orders/smart', data)
export const getAlgoOrders = (params) => request.get('/algo/orders', { params })
export const getAlgoOrder = (orderId) => request.get(`/algo/orders/${orderId}`)
export const getAlgoOrderStatus = (orderId) => request.get(`/algo/orders/${orderId}/status`)
export const cancelAlgoOrder = (orderId) => request.post(`/algo/orders/${orderId}/cancel`)
export const getExecutionQuality = (orderId) => request.get(`/algo/orders/${orderId}/quality`)
export const getExecutionHistory = (params) => request.get('/algo/executions/history', { params })

// ========== 高可用与灾备 ==========
export const getClusterStatus = () => request.get('/ha/cluster/status')
export const getDBReplication = () => request.get('/ha/database/replication')
export const triggerFailover = () => request.post('/ha/database/failover')
export const createBackup = (data) => request.post('/ha/database/backup', data)
export const getBackups = () => request.get('/ha/database/backups')
export const restoreBackup = (backupId) => request.post(`/ha/database/restore/${backupId}`)
export const deleteBackup = (backupId) => request.delete(`/ha/database/backup/${backupId}`)
export const getSystemHealth = () => request.get('/ha/system/health')
export const getPerformanceMetrics = (params) => request.get('/ha/system/metrics', { params })
export const getAlertRules = () => request.get('/ha/alerts/rules')
export const getActiveAlerts = () => request.get('/ha/alerts/active')
export const acknowledgeAlert = (alertId) => request.post(`/ha/alerts/${alertId}/acknowledge`)

// ========== 多市场扩展 ==========
export const getFuturesContracts = (params) => request.get('/multi-market/futures/contracts', { params })
export const getFuturesQuote = (symbol) => request.get(`/multi-market/futures/quote/${symbol}`)
export const calculateFuturesMargin = (data) => request.post('/multi-market/futures/margin', data)
export const getCryptoMarkets = () => request.get('/multi-market/crypto/markets')
export const getCryptoQuote = (symbol) => request.get(`/multi-market/crypto/quote/${symbol}`)
export const getCryptoKlines = (symbol, params) => request.get(`/multi-market/crypto/klines/${symbol}`, { params })
export const getEtfList = (params) => request.get('/multi-market/etf/list', { params })
export const getEtfDetail = (symbol, params) => request.get(`/multi-market/etf/detail/${symbol}`, { params })
export const getMarketHours = (market) => request.get(`/multi-market/market-hours/${market}`)
export const getMarketStatus = () => request.get('/multi-market/market-status')
export const getArbitrageOpportunities = (params) => request.get('/multi-market/arbitrage/opportunities', { params })
export const calculateArbitrage = (data) => request.post('/multi-market/arbitrage/calculate', data)
export const getCrossMarketCorrelation = (params) => request.get('/multi-market/correlation', { params })
export const getGlobalOverview = () => request.get('/multi-market/global-overview')

// ========== 社区与协作 ==========
export const getUserProfile = (userId) => request.get(`/community/profile/${userId}`)
export const getMyProfile = () => request.get('/community/profile/me')
export const updateUserProfile = (data) => request.put('/community/profile', data)
export const followUser = (userId) => request.post(`/community/follow/${userId}`)
export const unfollowUser = (userId) => request.delete(`/community/follow/${userId}`)
export const getFollowers = (userId, params) => request.get(`/community/followers/${userId}`, { params })
export const getFollowing = (userId, params) => request.get(`/community/following/${userId}`, { params })
export const createPost = (data) => request.post('/community/posts', data)
export const getPosts = (params) => request.get('/community/posts', { params })
export const getPost = (postId) => request.get(`/community/posts/${postId}`)
export const likePost = (postId) => request.post(`/community/posts/${postId}/like`)
export const createComment = (postId, data) => request.post(`/community/posts/${postId}/comments`, data)
export const getComments = (postId, params) => request.get(`/community/posts/${postId}/comments`, { params })
export const shareTrade = (data) => request.post('/community/trades/share', data)
export const getSharedTrades = (params) => request.get('/community/trades/shared', { params })
export const getLeaderboard = (params) => request.get('/community/leaderboard', { params })
export const sendMessage = (data) => request.post('/community/messages', data)
export const getMessages = (userId, params) => request.get(`/community/messages/${userId}`, { params })
export const getConversations = () => request.get('/community/conversations')
export const searchUsers = (params) => request.get('/community/search/users', { params })
