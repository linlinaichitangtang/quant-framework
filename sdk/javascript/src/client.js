/**
 * OpenClaw 量化交易平台 JavaScript SDK
 */

const crypto = require('crypto')
const {
  OpenClawError,
  AuthenticationError,
  RateLimitError,
  APIError,
  ConnectionError,
} = require('./exceptions')

const DEFAULT_TIMEOUT = 30000
const MAX_RETRIES = 3
const API_VERSION = 'v1'

class OpenClawClient {
  /**
   * 初始化 OpenClaw 客户端
   * @param {Object} config - 配置对象
   * @param {string} config.apiKey - API Key
   * @param {string} config.apiSecret - API Secret
   * @param {string} [config.baseUrl='http://localhost:8000'] - API 基础地址
   * @param {number} [config.timeout=30000] - 请求超时（毫秒）
   * @param {number} [config.maxRetries=3] - 最大重试次数
   */
  constructor({ apiKey, apiSecret, baseUrl = 'http://localhost:8000', timeout = DEFAULT_TIMEOUT, maxRetries = MAX_RETRIES }) {
    if (!apiKey) throw new OpenClawError('apiKey is required')
    if (!apiSecret) throw new OpenClawError('apiSecret is required')

    this.apiKey = apiKey
    this.apiSecret = apiSecret
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.timeout = timeout
    this.maxRetries = maxRetries
  }

  // ==================== 认证相关 ====================

  /**
   * 生成 HMAC-SHA256 签名
   * @param {string} method - HTTP 方法
   * @param {string} path - 请求路径
   * @param {number} timestamp - 时间戳
   * @param {string} [body=''] - 请求体
   * @returns {string} 签名字符串
   */
  _generateSignature(method, path, timestamp, body = '') {
    const message = `${method.toUpperCase()}\n${path}\n${timestamp}\n${body}`
    return crypto
      .createHmac('sha256', this.apiSecret)
      .update(message)
      .digest('hex')
  }

  /**
   * 构建请求头
   * @param {string} method - HTTP 方法
   * @param {string} path - 请求路径
   * @param {string} [body=''] - 请求体
   * @returns {Object} 请求头
   */
  _getHeaders(method, path, body = '') {
    const timestamp = Math.floor(Date.now() / 1000)
    const signature = this._generateSignature(method, path, timestamp, body)
    return {
      'Content-Type': 'application/json',
      'X-OC-API-Key': this.apiKey,
      'X-OC-Timestamp': String(timestamp),
      'X-OC-Signature': signature,
    }
  }

  /**
   * 统一请求方法（带重试）
   * @param {string} method - HTTP 方法
   * @param {string} path - API 路径
   * @param {Object} [options={}] - 请求选项
   * @param {Object} [options.params] - URL 查询参数
   * @param {Object} [options.data] - 请求体
   * @returns {Promise<Object>} 响应 JSON
   */
  async _request(method, path, options = {}) {
    const { params, data } = options
    const url = new URL(`${this.baseUrl}${path}`)
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.set(key, value)
        }
      })
    }

    const body = data ? JSON.stringify(data) : ''
    const headers = this._getHeaders(method, path, body)

    let lastError = null
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), this.timeout)

        const response = await fetch(url.toString(), {
          method: method.toUpperCase(),
          headers,
          body: body || undefined,
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        if (response.status === 401) {
          const text = await response.text()
          throw new AuthenticationError(text)
        }
        if (response.status === 429) {
          const retryAfter = response.headers.get('Retry-After')
          throw new RateLimitError(
            await response.text(),
            retryAfter ? parseInt(retryAfter, 10) : null
          )
        }
        if (response.status >= 400) {
          let message
          try {
            const errorData = await response.json()
            message = errorData.detail || errorData.message || response.statusText
          } catch {
            message = response.statusText
          }
          throw new APIError(message, response.status)
        }

        const contentType = response.headers.get('content-type')
        if (contentType && contentType.includes('application/json')) {
          return await response.json()
        }
        return { raw: await response.text() }
      } catch (error) {
        lastError = error
        if (error instanceof AuthenticationError || error instanceof RateLimitError) {
          throw error
        }
        if (error.name === 'AbortError') {
          lastError = new ConnectionError(`请求超时（${this.timeout}ms）`)
        } else if (error instanceof TypeError) {
          lastError = new ConnectionError(`无法连接到 ${this.baseUrl}`)
        }
        if (attempt < this.maxRetries) {
          await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)))
        }
      }
    }
    throw lastError
  }

  // ==================== 市场数据 API ====================

  /**
   * 获取行情报价
   * @param {string} market - 市场标识
   * @param {string[]} [symbols] - 股票代码列表
   * @returns {Promise<Quote[]>}
   */
  async getQuotes(market, symbols) {
    const params = { market }
    if (symbols && symbols.length > 0) {
      params.symbols = symbols.join(',')
    }
    const data = await this._request('GET', `/api/${API_VERSION}/market/quotes`, { params })
    const quotes = data.data || data
    return Array.isArray(quotes) ? quotes : [quotes]
  }

  /**
   * 获取K线数据
   * @param {string} symbol - 股票代码
   * @param {string} market - 市场标识
   * @param {string} [period='1d'] - K线周期
   * @param {number} [limit=100] - 数据条数
   * @returns {Promise<Kline[]>}
   */
  async getKlines(symbol, market, period = '1d', limit = 100) {
    const params = { symbol, market, period, limit }
    const data = await this._request('GET', `/api/${API_VERSION}/market/klines`, { params })
    const klines = data.data || data
    return Array.isArray(klines) ? klines : [klines]
  }

  /**
   * 获取股票信息
   * @param {string} symbol - 股票代码
   * @returns {Promise<StockInfo>}
   */
  async getStockInfo(symbol) {
    const data = await this._request('GET', `/api/${API_VERSION}/market/stocks/${symbol}`)
    return data.data || data
  }

  // ==================== 交易 API ====================

  /**
   * 创建交易信号
   * @param {string} symbol - 股票代码
   * @param {string} market - 市场标识
   * @param {string} side - 方向 (buy/sell)
   * @param {string} [strategyId] - 策略 ID
   * @param {Object} [kwargs] - 其他参数
   * @returns {Promise<Signal>}
   */
  async createSignal(symbol, market, side, strategyId, kwargs = {}) {
    const payload = { symbol, market, side, strategy_id: strategyId, ...kwargs }
    const data = await this._request('POST', `/api/${API_VERSION}/signals`, { data: payload })
    return data.data || data
  }

  /**
   * 获取信号列表
   * @param {string} [market] - 市场标识
   * @param {string} [status] - 信号状态
   * @param {number} [limit=50] - 返回条数
   * @returns {Promise<Signal[]>}
   */
  async getSignals(market, status, limit = 50) {
    const params = { limit }
    if (market) params.market = market
    if (status) params.status = status
    const data = await this._request('GET', `/api/${API_VERSION}/signals`, { params })
    const signals = data.data || data
    return Array.isArray(signals) ? signals : [signals]
  }

  /**
   * 获取持仓列表
   * @param {string} [market] - 市场标识
   * @returns {Promise<Position[]>}
   */
  async getPositions(market) {
    const params = {}
    if (market) params.market = market
    const data = await this._request('GET', `/api/${API_VERSION}/positions`, { params })
    const positions = data.data || data
    return Array.isArray(positions) ? positions : [positions]
  }

  /**
   * 创建订单
   * @param {string} symbol - 股票代码
   * @param {string} market - 市场标识
   * @param {string} side - 方向 (buy/sell)
   * @param {number} quantity - 数量
   * @param {number} [price] - 价格
   * @param {string} [orderType='limit'] - 订单类型
   * @returns {Promise<Order>}
   */
  async createOrder(symbol, market, side, quantity, price, orderType = 'limit') {
    const payload = { symbol, market, side, quantity, order_type: orderType }
    if (price !== undefined) payload.price = price
    const data = await this._request('POST', `/api/${API_VERSION}/orders`, { data: payload })
    return data.data || data
  }

  /**
   * 获取订单状态
   * @param {string} orderId - 订单 ID
   * @returns {Promise<Order>}
   */
  async getOrderStatus(orderId) {
    const data = await this._request('GET', `/api/${API_VERSION}/orders/${orderId}`)
    return data.data || data
  }

  /**
   * 取消订单
   * @param {string} orderId - 订单 ID
   * @returns {Promise<Object>}
   */
  async cancelOrder(orderId) {
    return this._request('DELETE', `/api/${API_VERSION}/orders/${orderId}`)
  }

  // ==================== 账户 API ====================

  /**
   * 获取账户信息
   * @returns {Promise<AccountInfo>}
   */
  async getAccountInfo() {
    const data = await this._request('GET', `/api/${API_VERSION}/account/info`)
    return data.data || data
  }

  /**
   * 获取账户余额
   * @returns {Promise<AccountBalance[]>}
   */
  async getAccountBalance() {
    const data = await this._request('GET', `/api/${API_VERSION}/account/balance`)
    const balances = data.data || data
    return Array.isArray(balances) ? balances : [balances]
  }

  // ==================== 回测 API ====================

  /**
   * 运行回测
   * @param {BacktestConfig|Object} config - 回测配置
   * @returns {Promise<BacktestResult>}
   */
  async runBacktest(config) {
    const data = await this._request('POST', `/api/${API_VERSION}/backtest/run`, { data: config })
    return data.data || data
  }

  /**
   * 获取回测结果列表
   * @param {number} [limit=20] - 返回条数
   * @returns {Promise<BacktestResult[]>}
   */
  async getBacktestResults(limit = 20) {
    const data = await this._request('GET', `/api/${API_VERSION}/backtest/results`, { params: { limit } })
    const results = data.data || data
    return Array.isArray(results) ? results : [results]
  }

  /**
   * 获取回测详情
   * @param {string} backtestId - 回测 ID
   * @returns {Promise<BacktestResult>}
   */
  async getBacktestDetail(backtestId) {
    const data = await this._request('GET', `/api/${API_VERSION}/backtest/results/${backtestId}`)
    return data.data || data
  }

  // ==================== AI API ====================

  /**
   * 自然语言查询
   * @param {string} query - 查询文本
   * @param {string} [market] - 市场标识
   * @returns {Promise<AIResponse>}
   */
  async aiQuery(query, market) {
    const payload = { query }
    if (market) payload.market = market
    const data = await this._request('POST', `/api/${API_VERSION}/ai/query`, { data: payload })
    return data.data || data
  }

  /**
   * AI 对话
   * @param {string} sessionId - 会话 ID
   * @param {string} message - 消息内容
   * @returns {Promise<Object>}
   */
  async aiChat(sessionId, message) {
    return this._request('POST', `/api/${API_VERSION}/ai/chat`, {
      data: { session_id: sessionId, message },
    })
  }

  /**
   * 获取市场情绪
   * @param {string} market - 市场标识
   * @returns {Promise<MarketSentiment>}
   */
  async getMarketSentiment(market) {
    const data = await this._request('GET', `/api/${API_VERSION}/ai/sentiment`, { params: { market } })
    return data.data || data
  }

  /**
   * 获取策略建议
   * @param {string} market - 市场标识
   * @param {string} [riskLevel='medium'] - 风险等级
   * @returns {Promise<StrategyAdvice>}
   */
  async getStrategyAdvice(market, riskLevel = 'medium') {
    const data = await this._request('GET', `/api/${API_VERSION}/ai/advice`, {
      params: { market, risk_level: riskLevel },
    })
    return data.data || data
  }

  // ==================== 使用统计 API ====================

  /**
   * 获取使用统计
   * @returns {Promise<UsageStats>}
   */
  async getUsageStats() {
    const data = await this._request('GET', `/api/${API_VERSION}/usage/stats`)
    return data.data || data
  }
}

module.exports = { OpenClawClient }
