# OpenClaw决策 + FMZ执行 量化交易框架

## 架构理念

- **决策层（OpenClaw）**：负责市场数据分析、选股、策略信号生成
- **执行层（FMZ发明者量化）**：负责订单执行、实盘成交推送
- **数据流：** `市场数据 → OpenClaw分析 → 生成交易信号 → JSON API → FMZ执行 → 结果返回OpenClaw`

## 项目结构

```
quant-framework/
├── src/
│   ├── __init__.py
│   ├── strategies/          # 策略模块
│   │   ├── __init__.py
│   │   ├── a_stock_evening.py      # A股尾盘选股策略（约炮式）
│   │   └── us_hk_event_driven.py   # 港股美股事件驱动期权策略（恋爱式）
│   ├── api/                 # API接口模块
│   │   ├── __init__.py
│   │   └── fmz_api.py       # OpenClaw ↔ FMZ JSON API定义
│   └── risk/                # 风控模块
│       ├── __init__.py
│       └── risk_manager.py  # 综合风控管理器
├── docs/                    # 文档
├── examples/                # 使用示例
│   └── example_usage.py     # 完整使用示例
└── README.md
```

## 策略说明

### 1. A股"约炮式"超短尾盘策略

核心逻辑：尾盘竞价买入，博取次日冲高，严格2%止盈止损，绝不持仓过夜

**选股规则：**
- 股价站在20日均线之上，20日均线向上
- 当日涨幅 3% ~ 8%
- 当日成交量大于5日均量1.5倍
- 换手率 3% ~ 20%
- 流通市值 50亿 ~ 500亿
- 尾盘半小时拉升，收盘价接近当日最高点
- 排除ST、停牌、连续3个涨停以上

**卖出规则：**
- 止盈：次日涨幅达到+2%立即卖出
- 止损：次日跌幅达到-2%立即卖出
- 开盘低开超过-2%：开盘立即止损
- 14:30未触及止盈止损：无论盈亏都卖出
- 绝对不持仓超过一个交易日

### 2. 港股美股"恋爱式"事件驱动期权策略

核心逻辑：基于财报/新闻事件，判断方向，使用期权杠杆，持有数天到数周等待事件发酵

**支持的期权策略：**

| 策略 | 应用场景 |
|------|----------|
| Long Call | 财报超预期/政策利好，明确看多 |
| Long Put | 财报不及预期/黑天鹅，明确看空 |
| 跨式(Straddle) | 财报前方向不确定，等待波动率放大 |
| 宽跨(Strangle) | 预计大波动，方向有倾向，降低成本 |
| 牛市价差/熊市价差 | 方向确定但波动率高，降低权利金成本 |

**风控规则：**
- 单策略最大亏损不超过总资金 2%~5%
- 期权总权利金不超过总资金20%
- 权利金亏损50%强制止损
- 到期前一周提前平仓

## API接口规范

### OpenClaw → FMZ 交易信号 (JSON格式)

```json
{
  "strategy": "a股隔夜",
  "action": "buy",
  "symbol": "000001",
  "market": "CN",
  "price": 15.2,
  "quantity": 6500,
  "order_type": "market",
  "stop_loss": 14.896,
  "take_profit": 15.504,
  "expire_time": "2026-03-17T15:00:00",
  "remark": "尾盘选股买入"
}
```

### FMZ → OpenClaw 执行结果 (JSON格式)

```json
{
  "request_id": "req-xxxx",
  "status": "success",
  "message": "成交完成",
  "order_id": "fmz-order-123",
  "filled_quantity": 6500,
  "filled_price": 15.19,
  "positions": [
    {
      "symbol": "000001",
      "market": "CN",
      "quantity": 6500,
      "cost_price": 15.19,
      "current_price": 15.19,
      "profit_pct": 0,
      "profit_amount": 0,
      "is_today_open": true
    }
  ],
  "capital": {
    "total": 1000000,
    "available": 901265
  }
}
```

## 风控规则

- **A股：** 单票不超过总资金10%，每日新开仓不超过5只，总持仓不超过80%，单笔亏损-2%强制止损
- **期权：** 单策略最大亏损不超过总资金3%，总权利金不超过20%，权利金亏损50%止损
- **整体：** VIX > 25暂停开仓，连续3日亏损暂停开仓，单板块持仓不超过30%

## 使用示例

```python
import sys
sys.path.insert(0, 'src')

from quant_framework import AStockEveningPicker, RiskManager, FMZClient
import pandas as pd

# 1. 初始化选股器和风控
picker = AStockEveningPicker()
risk = RiskManager(total_capital=1000000)  # 总资金100万

# 2. 筛选股票
df = pd.DataFrame(your_market_data)
selected = picker.filter_stocks(df)

# 3. 生成交易信号
client = FMZClient()
for _, row in selected.iterrows():
    shares = risk.calculate_position_size(row['close'])
    signal = client.create_trading_signal(
        strategy='a股隔夜',
        action='buy',
        symbol=row['code'],
        market='CN',
        price=row['close'],
        quantity=shares,
        stop_loss=row['close'] * 0.98,
        take_profit=row['close'] * 1.02
    )
    # 发送signal到FMZ执行
    print(signal.to_json())
```

## 版本

- v1.0 (2026-03-17)：完成核心策略和API接口
