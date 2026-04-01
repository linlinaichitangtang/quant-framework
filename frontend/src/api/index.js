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
