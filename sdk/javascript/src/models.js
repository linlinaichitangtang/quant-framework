/**
 * OpenClaw 量化交易平台 JavaScript SDK - 类型定义 (JSDoc)
 */

/**
 * @typedef {Object} Quote
 * @property {string} symbol - 股票代码
 * @property {string} market - 市场标识
 * @property {number} price - 当前价格
 * @property {number} [open] - 开盘价
 * @property {number} [high] - 最高价
 * @property {number} [low] - 最低价
 * @property {number} [close] - 收盘价
 * @property {number} [volume] - 成交量
 * @property {number} [change] - 涨跌额
 * @property {number} [changePercent] - 涨跌幅
 * @property {string} [timestamp] - 时间戳
 */

/**
 * @typedef {Object} Kline
 * @property {string} symbol - 股票代码
 * @property {string} market - 市场标识
 * @property {string} period - K线周期
 * @property {number} open - 开盘价
 * @property {number} high - 最高价
 * @property {number} low - 最低价
 * @property {number} close - 收盘价
 * @property {number} volume - 成交量
 * @property {string} [timestamp] - 时间戳
 * @property {number} [turnover] - 成交额
 */

/**
 * @typedef {Object} StockInfo
 * @property {string} symbol - 股票代码
 * @property {string} name - 股票名称
 * @property {string} market - 市场标识
 * @property {string} [industry] - 行业
 * @property {string} [sector] - 板块
 * @property {number} [marketCap] - 市值
 * @property {number} [peRatio] - 市盈率
 * @property {number} [pbRatio] - 市净率
 * @property {string} [description] - 描述
 * @property {string} [listDate] - 上市日期
 */

/**
 * @typedef {Object} Signal
 * @property {string} [id] - 信号 ID
 * @property {string} symbol - 股票代码
 * @property {string} market - 市场标识
 * @property {string} side - 方向 (buy/sell)
 * @property {string} [strategyId] - 策略 ID
 * @property {string} [status] - 状态
 * @property {number} [price] - 价格
 * @property {number} [quantity] - 数量
 * @property {number} [confidence] - 置信度
 * @property {string} [reason] - 原因
 * @property {string} [createdAt] - 创建时间
 * @property {string} [executedAt] - 执行时间
 */

/**
 * @typedef {Object} Position
 * @property {string} [id] - 持仓 ID
 * @property {string} symbol - 股票代码
 * @property {string} market - 市场标识
 * @property {string} side - 方向
 * @property {number} quantity - 持仓数量
 * @property {number} [availableQuantity] - 可用数量
 * @property {number} [avgPrice] - 平均成本
 * @property {number} [currentPrice] - 当前价格
 * @property {number} [pnl] - 盈亏
 * @property {number} [pnlPercent] - 盈亏百分比
 * @property {number} [marketValue] - 市值
 * @property {number} [cost] - 成本
 */

/**
 * @typedef {Object} Order
 * @property {string} [id] - 订单 ID
 * @property {string} symbol - 股票代码
 * @property {string} market - 市场标识
 * @property {string} side - 方向
 * @property {string} [type] - 订单类型
 * @property {number} quantity - 数量
 * @property {number} [price] - 价格
 * @property {number} [filledQuantity] - 已成交数量
 * @property {number} [filledPrice] - 成交价格
 * @property {string} [status] - 状态
 * @property {number} [fee] - 手续费
 * @property {string} [createdAt] - 创建时间
 * @property {string} [updatedAt] - 更新时间
 */

/**
 * @typedef {Object} AccountBalance
 * @property {string} [currency] - 货币
 * @property {number} [total] - 总额
 * @property {number} [available] - 可用
 * @property {number} [frozen] - 冻结
 * @property {number} [profit] - 盈亏
 */

/**
 * @typedef {Object} AccountInfo
 * @property {string} [accountId] - 账户 ID
 * @property {string} [name] - 账户名称
 * @property {string} [level] - 账户等级
 * @property {string} [status] - 状态
 * @property {AccountBalance[]} [balances] - 余额列表
 * @property {string} [createdAt] - 创建时间
 */

/**
 * @typedef {Object} BacktestConfig
 * @property {string} [strategyId] - 策略 ID
 * @property {string} [strategyName] - 策略名称
 * @property {string[]} [symbols] - 股票列表
 * @property {string} [market] - 市场
 * @property {string} [startDate] - 开始日期
 * @property {string} [endDate] - 结束日期
 * @property {number} [initialCapital] - 初始资金
 * @property {number} [commissionRate] - 手续费率
 * @property {number} [slippage] - 滑点
 * @property {string} [benchmark] - 基准
 * @property {string} [frequency] - 频率
 */

/**
 * @typedef {Object} BacktestResult
 * @property {string} [id] - 回测 ID
 * @property {BacktestConfig} [config] - 回测配置
 * @property {string} [status] - 状态
 * @property {Object} [metrics] - 回测指标
 * @property {Array} [equityCurve] - 权益曲线
 * @property {Array} [trades] - 交易记录
 * @property {string} [createdAt] - 创建时间
 * @property {string} [completedAt] - 完成时间
 * @property {string} [error] - 错误信息
 */

/**
 * @typedef {Object} AIResponse
 * @property {string} [query] - 查询
 * @property {string} answer - 回答
 * @property {number} [confidence] - 置信度
 * @property {string[]} [sources] - 来源
 * @property {string} [market] - 市场
 * @property {string} [timestamp] - 时间戳
 */

/**
 * @typedef {Object} MarketSentiment
 * @property {string} market - 市场
 * @property {number} overallScore - 综合评分
 * @property {string} label - 情绪标签
 * @property {Object} [factors] - 影响因素
 * @property {string} [timestamp] - 时间戳
 */

/**
 * @typedef {Object} StrategyAdvice
 * @property {string} market - 市场
 * @property {string} riskLevel - 风险等级
 * @property {string[]} [recommendations] - 建议
 * @property {Object[]} [topPicks] - 推荐标的
 * @property {string[]} [riskWarnings] - 风险提示
 * @property {string} [timestamp] - 时间戳
 */

/**
 * @typedef {Object} UsageStats
 * @property {number} [totalApiCalls] - 总 API 调用数
 * @property {number} [dailyApiCalls] - 日 API 调用数
 * @property {number} [monthlyApiCalls] - 月 API 调用数
 * @property {number} [apiCallsLimit] - API 调用上限
 * @property {number} [usagePercent] - 使用率百分比
 * @property {string} [period] - 统计周期
 */

module.exports = {}
