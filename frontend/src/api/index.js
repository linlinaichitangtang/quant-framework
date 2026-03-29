import request from './request'

// 概览统计
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
