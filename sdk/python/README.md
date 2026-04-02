# OpenClaw Python SDK

OpenClaw 量化交易平台官方 Python SDK，版本 2.0.0。

## 安装

```bash
pip install openclaw-sdk
```

或从源码安装：

```bash
git clone https://github.com/openclaw/openclaw-sdk-python.git
cd openclaw-sdk-python
pip install -e .
```

## 快速开始

```python
from openclaw_sdk import OpenClawClient

# 初始化客户端
client = OpenClawClient(
    api_key="your_api_key",
    api_secret="your_api_secret",
    base_url="http://localhost:8000",
)

# 获取行情报价
quotes = client.get_quotes(market="cn", symbols=["000001", "600519"])
for quote in quotes:
    print(f"{quote.symbol}: {quote.price} ({quote.change_percent}%)")

# 获取K线数据
klines = client.get_klines(symbol="000001", market="cn", period="1d", limit=30)
for kline in klines:
    print(f"{kline.timestamp}: O={kline.open} H={kline.high} L={kline.low} C={kline.close}")

# 创建交易信号
signal = client.create_signal(
    symbol="000001",
    market="cn",
    side="buy",
    strategy_id="strategy_001",
    price=15.50,
    quantity=100,
    confidence=0.85,
    reason="均线金叉，成交量放大",
)
print(f"信号已创建: {signal.id}")

# 查询持仓
positions = client.get_positions(market="cn")
for pos in positions:
    print(f"{pos.symbol}: 数量={pos.quantity}, 盈亏={pos.pnl} ({pos.pnl_percent}%)")

# AI 查询
response = client.ai_query("今天大盘走势如何？", market="cn")
print(f"AI 回答: {response.answer}")

# 使用上下文管理器自动关闭连接
with OpenClawClient(api_key="key", api_secret="secret") as client:
    info = client.get_account_info()
    print(f"账户: {info.name}, 状态: {info.status}")
```

## API 方法说明

### 市场数据

| 方法 | 说明 |
|------|------|
| `get_quotes(market, symbols)` | 获取行情报价 |
| `get_klines(symbol, market, period, limit)` | 获取K线数据 |
| `get_stock_info(symbol)` | 获取股票信息 |

### 交易

| 方法 | 说明 |
|------|------|
| `create_signal(symbol, market, side, strategy_id, **kwargs)` | 创建交易信号 |
| `get_signals(market, status, limit)` | 获取信号列表 |
| `get_positions(market)` | 获取持仓列表 |
| `create_order(symbol, market, side, quantity, price, order_type)` | 创建订单 |
| `get_order_status(order_id)` | 获取订单状态 |
| `cancel_order(order_id)` | 取消订单 |

### 账户

| 方法 | 说明 |
|------|------|
| `get_account_info()` | 获取账户信息 |
| `get_account_balance()` | 获取账户余额 |

### 回测

| 方法 | 说明 |
|------|------|
| `run_backtest(config)` | 运行回测 |
| `get_backtest_results(limit)` | 获取回测结果列表 |
| `get_backtest_detail(backtest_id)` | 获取回测详情 |

### AI

| 方法 | 说明 |
|------|------|
| `ai_query(query, market)` | 自然语言查询 |
| `ai_chat(session_id, message)` | AI 对话 |
| `get_market_sentiment(market)` | 获取市场情绪 |
| `get_strategy_advice(market, risk_level)` | 获取策略建议 |

### 使用统计

| 方法 | 说明 |
|------|------|
| `get_usage_stats()` | 获取使用统计 |

## 错误处理

SDK 提供了完善的异常体系：

```python
from openclaw_sdk import OpenClawClient
from openclaw_sdk.exceptions import (
    OpenClawError,
    AuthenticationError,
    RateLimitError,
    APIError,
    ConnectionError,
)

client = OpenClawClient(api_key="key", api_secret="secret")

try:
    quotes = client.get_quotes(market="cn")
except AuthenticationError as e:
    print(f"认证失败: {e}")
except RateLimitError as e:
    print(f"限流，{e.retry_after}秒后重试")
except APIError as e:
    print(f"API 错误 [{e.status_code}]: {e}")
except ConnectionError as e:
    print(f"连接错误: {e}")
except OpenClawError as e:
    print(f"SDK 错误: {e}")
```

### 异常类型

| 异常类 | 说明 | HTTP 状态码 |
|--------|------|-------------|
| `OpenClawError` | 基础异常 | - |
| `AuthenticationError` | 认证失败 | 401 |
| `RateLimitError` | 请求限流 | 429 |
| `APIError` | API 错误 | 400-599 |
| `ConnectionError` | 连接错误 | - |

## 认证说明

SDK 使用 HMAC-SHA256 签名认证。每个请求会自动生成签名，包含以下请求头：

- `X-OC-API-Key`: API Key
- `X-OC-Timestamp`: 请求时间戳
- `X-OC-Signature`: HMAC-SHA256 签名

签名算法：

```
message = "{METHOD}\n{PATH}\n{TIMESTAMP}\n{BODY}"
signature = HMAC-SHA256(api_secret, message)
```

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_key` | str | 必填 | API Key |
| `api_secret` | str | 必填 | API Secret |
| `base_url` | str | `http://localhost:8000` | API 基础地址 |
| `timeout` | int | 30 | 请求超时（秒） |
| `max_retries` | int | 3 | 最大重试次数 |

## 许可证

MIT License
