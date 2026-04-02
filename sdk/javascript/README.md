# OpenClaw JavaScript SDK

OpenClaw 量化交易平台官方 JavaScript SDK，版本 2.0.0。

## 安装

```bash
npm install @openclaw/sdk
```

## 快速开始

```javascript
const { OpenClawClient } = require('@openclaw/sdk')

// 初始化客户端
const client = new OpenClawClient({
  apiKey: 'your_api_key',
  apiSecret: 'your_api_secret',
  baseUrl: 'http://localhost:8000',
})

// 获取行情报价
async function main() {
  try {
    // 获取行情
    const quotes = await client.getQuotes('cn', ['000001', '600519'])
    quotes.forEach(q => {
      console.log(`${q.symbol}: ${q.price} (${q.changePercent}%)`)
    })

    // 获取K线
    const klines = await client.getKlines('000001', 'cn', '1d', 30)
    klines.forEach(k => {
      console.log(`${k.timestamp}: O=${k.open} H=${k.high} L=${k.low} C=${k.close}`)
    })

    // 创建交易信号
    const signal = await client.createSignal('000001', 'cn', 'buy', 'strategy_001', {
      price: 15.50,
      quantity: 100,
      confidence: 0.85,
      reason: '均线金叉，成交量放大',
    })
    console.log(`信号已创建: ${signal.id}`)

    // AI 查询
    const response = await client.aiQuery('今天大盘走势如何？', 'cn')
    console.log(`AI 回答: ${response.answer}`)
  } catch (error) {
    console.error('错误:', error.message)
  }
}

main()
```

## API 方法说明

### 市场数据

| 方法 | 说明 |
|------|------|
| `getQuotes(market, symbols)` | 获取行情报价 |
| `getKlines(symbol, market, period, limit)` | 获取K线数据 |
| `getStockInfo(symbol)` | 获取股票信息 |

### 交易

| 方法 | 说明 |
|------|------|
| `createSignal(symbol, market, side, strategyId, kwargs)` | 创建交易信号 |
| `getSignals(market, status, limit)` | 获取信号列表 |
| `getPositions(market)` | 获取持仓列表 |
| `createOrder(symbol, market, side, quantity, price, orderType)` | 创建订单 |
| `getOrderStatus(orderId)` | 获取订单状态 |
| `cancelOrder(orderId)` | 取消订单 |

### 账户

| 方法 | 说明 |
|------|------|
| `getAccountInfo()` | 获取账户信息 |
| `getAccountBalance()` | 获取账户余额 |

### 回测

| 方法 | 说明 |
|------|------|
| `runBacktest(config)` | 运行回测 |
| `getBacktestResults(limit)` | 获取回测结果列表 |
| `getBacktestDetail(backtestId)` | 获取回测详情 |

### AI

| 方法 | 说明 |
|------|------|
| `aiQuery(query, market)` | 自然语言查询 |
| `aiChat(sessionId, message)` | AI 对话 |
| `getMarketSentiment(market)` | 获取市场情绪 |
| `getStrategyAdvice(market, riskLevel)` | 获取策略建议 |

### 使用统计

| 方法 | 说明 |
|------|------|
| `getUsageStats()` | 获取使用统计 |

## 错误处理

```javascript
const {
  OpenClawClient,
  OpenClawError,
  AuthenticationError,
  RateLimitError,
  APIError,
  ConnectionError,
} = require('@openclaw/sdk')

const client = new OpenClawClient({ apiKey: 'key', apiSecret: 'secret' })

try {
  const quotes = await client.getQuotes('cn')
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('认证失败:', error.message)
  } else if (error instanceof RateLimitError) {
    console.error(`限流，${error.retryAfter}秒后重试`)
  } else if (error instanceof APIError) {
    console.error(`API 错误 [${error.statusCode}]:`, error.message)
  } else if (error instanceof ConnectionError) {
    console.error('连接错误:', error.message)
  } else if (error instanceof OpenClawError) {
    console.error('SDK 错误:', error.message)
  }
}
```

## 认证说明

SDK 使用 HMAC-SHA256 签名认证，每个请求自动生成签名：

- `X-OC-API-Key`: API Key
- `X-OC-Timestamp`: 请求时间戳
- `X-OC-Signature`: HMAC-SHA256 签名

签名算法与 Python SDK 完全一致。

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `apiKey` | string | 必填 | API Key |
| `apiSecret` | string | 必填 | API Secret |
| `baseUrl` | string | `http://localhost:8000` | API 基础地址 |
| `timeout` | number | 30000 | 请求超时（毫秒） |
| `maxRetries` | number | 3 | 最大重试次数 |

## 许可证

MIT License
