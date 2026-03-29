# OpenClaw量化交易框架 - API接口文档

## 概述

OpenClaw量化交易框架后端API基于FastAPI构建，提供了完整的数据查询、信号管理、FMZ执行接口。

**基础URL:** `http://host:port/api/v1`

**文档地址:** `http://host:port/docs` (FastAPI自动生成的Swagger文档)

---

## 接口列表

### 一、股票信息

#### 获取股票列表
```
GET /stocks
```

**参数:**
- `market` (可选): 市场类型 `A`/`HK`/`US`
- `page` (可选): 页码，默认1
- `page_size` (可选): 每页数量，默认50，最大200

**响应:**
```json
{
  "total": 1000,
  "page": 1,
  "page_size": 50,
  "data": [
    {
      "id": 1,
      "symbol": "000001",
      "name": "平安银行",
      "market": "A",
      "is_listed": true,
      "industry": "银行",
      "list_date": "1991-04-03",
      "created_at": "2026-03-17T00:00:00Z",
      "updated_at": "2026-03-17T00:00:00Z"
    }
  ]
}
```

#### 获取单个股票信息
```
GET /stocks/{symbol}
```

---

### 二、历史行情

#### 获取历史K线
```
GET /bars/{symbol}
```

**参数:**
- `symbol`: 股票代码
- `bar_type` (可选): K线类型 `1d`/`1m`/`5m`/`15m`/`1h`，默认 `1d`
- `start_date` (可选): 开始时间 ISO格式
- `end_date` (可选): 结束时间 ISO格式
- `page` (可选): 页码，默认1
- `page_size` (可选): 每页数量，默认1000，最大5000

**响应:**
```json
{
  "total": 250,
  "page": 1,
  "page_size": 1000,
  "data": [
    {
      "id": 1,
      "symbol": "000001",
      "market": "A",
      "bar_type": "1d",
      "timestamp": "2026-03-16T00:00:00Z",
      "open": 10.5,
      "high": 10.8,
      "low": 10.3,
      "close": 10.7,
      "volume": 1000000,
      "turnover": 10700000
    }
  ]
}
```

---

### 三、持仓查询

#### 获取所有持仓
```
GET /positions
```

**参数:**
- `market` (可选): 过滤市场 `A`/`HK`/`US`

**响应:**
```json
[
  {
    "id": 1,
    "symbol": "000001",
    "market": "A",
    "quantity": 1000,
    "avg_cost": 10.5,
    "current_price": 10.7,
    "market_value": 10700,
    "profit_pct": 1.90,
    "profit_amount": 200,
    "is_option": false,
    "created_at": "2026-03-17T00:00:00Z",
    "updated_at": "2026-03-17T00:00:00Z"
  }
]
```

#### 获取单个持仓
```
GET /positions/{position_id}
```

---

### 四、选股结果

#### 获取选股结果列表
```
GET /selections
```

**参数:**
- `market` (可选): 过滤市场
- `strategy_id` (可选): 过滤策略
- `selection_date` (可选): 过滤选股日期 `YYYY-MM-DD`
- `page` (可选): 页码
- `page_size` (可选): 每页数量

**响应:**
按评分降序排列。

---

### 五、交易信号

#### 获取交易信号列表
```
GET /signals
```

**参数:**
- `market` (可选): 过滤市场
- `status` (可选): 过滤状态 `PENDING`/`EXECUTED`/`FAILED`/`EXPIRED`
- `side` (可选): 过滤方向 `BUY`/`SELL`
- `strategy_id` (可选): 过滤策略
- `page` (可选): 页码
- `page_size` (可选): 每页数量

**响应:**
按创建时间降序排列。

#### 获取单个信号
```
GET /signals/{signal_id}
```

#### 创建交易信号
```
POST /signals
Content-Type: application/json

{
  "signal_id": "signal-20260317-0001",
  "symbol": "000001",
  "market": "A",
  "side": "BUY",
  "strategy_id": "a-stock-close-swipe",
  "strategy_name": "A股尾盘竞价策略",
  "signal_type": "OPEN",
  "confidence": 0.85,
  "target_price": 10.5,
  "stop_loss": 10.3,
  "take_profit": 10.71,
  "quantity": 1000,
  "reason": "满足尾盘放量上涨条件"
}
```

**响应:** 返回创建的信号对象。

---

### 六、交易记录

#### 获取交易记录列表
```
GET /trades
```

**参数:**
- `symbol` (可选): 过滤股票
- `market` (可选): 过滤市场
- `side` (可选): 过滤方向
- `strategy_id` (可选): 过滤策略
- `signal_id` (可选): 过滤信号ID
- `status` (可选): 过滤状态
- `page` (可选): 页码
- `page_size` (可选): 每页数量

**响应:** 按创建时间降序排列。

#### 创建交易记录
```
POST /trades
Content-Type: application/json

{
  "order_id": "order-12345",
  "symbol": "000001",
  "market": "A",
  "side": "BUY",
  "quantity": 1000,
  "price": 10.5,
  "amount": 10500,
  "commission": 5,
  "strategy_id": "a-stock-close-swipe",
  "strategy_name": "A股尾盘竞价策略",
  "signal_id": 1,
  "fmz_order_id": "fmz-67890",
  "status": "FILLED"
}
```

---

### 七、FMZ执行接口

#### 执行交易信号到FMZ
```
POST /fmz/execute/{signal_id}
Content-Type: application/json

{
  "api_key": "your-api-key",    // 可选，使用配置文件中的值
  "secret_key": "your-secret",  // 可选，使用配置文件中的值
  "cid": 12345                  // 可选，使用配置文件中的值
}
```

**响应:**
```json
{
  "success": true,
  "message": "下单成功",
  "order_id": "fmz-123456",
  "data": {
    // FMZ返回的原始数据
  }
}
```

执行成功后，会自动：
1. 将信号状态更新为 `EXECUTED`
2. 创建对应的交易记录

#### 获取FMZ账户信息
```
GET /fmz/account
```

#### 获取FMZ持仓信息
```
GET /fmz/positions/{exchange}
```
`exchange` 取值: `cn`(A股), `hk`(港股), `us`(美股)

---

### 八、概览统计

```
GET /overview
```

**响应:**
```json
{
  "total_positions": 5,
  "total_market_value": 100000,
  "total_unrealized_profit": 2000,
  "pending_signals_count": 3,
  "recent_trades": [...]
}
```

---

### 九、健康检查

```
GET /health
```

响应:
```json
{
  "status": "ok"
}
```

---

## 数据结构说明

### 市场类型
- `A`: A股
- `HK`: 港股
- `US`: 美股

### K线类型
- `1d`: 日线
- `1m`: 1分钟
- `5m`: 5分钟
- `15m`: 15分钟
- `1h`: 小时线

### 交易信号状态
- `PENDING`: 待执行
- `EXECUTED`: 已执行
- `FAILED`: 执行失败
- `EXPIRED`: 已过期

### 交易状态
- `FILLED`: 已成交
- `PENDING`: 待成交
- `CANCELLED`: 已取消

---

## 数据采集定时任务

系统内置定时采集任务，采集规则：

| 市场 | 采集时间 | 说明 |
|------|----------|------|
| A股  | 每个交易日 15:15 | 收盘后采集当日数据 |
| 港股 | 每个交易日 16:16 | 收盘后采集当日数据 |
| 美股 | 每个交易日次日 05:00 | 隔夜采集当日数据 |

可在 `app/config.py` 或 `.env` 中修改cron表达式。

---

## 部署说明

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

需要额外安装akshare:
```bash
pip install akshare
```

### 2. 配置

复制 `.env.example` 到 `.env`，修改配置：
```
DATABASE_URL=sqlite:///./quant_trade.db
API_HOST=0.0.0.0
API_PORT=8000
FMZ_API_KEY=your_api_key
FMZ_SECRET_KEY=your_secret
FMZ_CID=your_cid
```

### 3. 初始化数据

```bash
cd backend/scripts
python init_data.py
```

### 4. 启动API服务

```bash
./start_api.sh
```

### 5. 启动数据采集定时任务

```bash
./start_scheduler.sh
```

建议使用systemd或supervisor管理进程。

---

## 数据库设计

| 表名 | 说明 |
|------|------|
| historical_bars | 历史行情K线数据 |
| stock_info | 股票基础信息 |
| positions | 当前持仓信息 |
| trade_records | 交易记录表 |
| trading_signals | 交易信号表 |
| stock_selections | 选股结果表 |
| system_logs | 系统日志表 |
| strategy_configs | 策略配置表 |

详见 `app/models.py`

---

## 核心逻辑对接

麟算（量化算法工程师）可以通过以下方式对接核心逻辑：

1. **生成选股结果**: 调用 `POST /api/v1/selections`（需要在代码中添加接口，当前框架已支持数据存储）
2. **生成交易信号**: 调用 `POST /api/v1/signals` 创建信号
3. **执行信号**: 调用 `POST /api/v1/fmz/execute/{signal_id}` 发送到FMZ执行
4. **查询持仓**: `GET /api/v1/positions`
5. **查询历史行情**: `GET /api/v1/bars/{symbol}` 获取历史数据用于计算

所有数据存储在数据库中，核心逻辑可以直接通过ORM访问，也可以通过API访问。
