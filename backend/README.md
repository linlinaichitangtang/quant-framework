# OpenClaw量化交易 - 后端服务

OpenClaw做决策大脑，FMZ做执行手脚，这是后端数据服务和API部分。

## 项目结构

```
backend/
├── app/                      # 主应用
│   ├── api.py               # API路由
│   ├── config.py            # 配置
│   ├── database.py          # 数据库连接
│   ├── models.py            # 数据模型（数据库设计）
│   ├── schemas.py           # Pydantic模式（API验证）
│   ├── crud.py              # CRUD操作
│   ├── main.py              # 应用入口
│   └── fmz_client.py        # FMZ API客户端
├── data_collection/         # 数据采集服务
│   ├── collector_base.py    # 采集器基类
│   ├── a_stock_collector.py # A股采集器
│   ├── hk_stock_collector.py# 港股采集器
│   ├── us_stock_collector.py# 美股采集器
│   └── scheduler.py         # 定时任务调度
├── scripts/                 # 脚本
│   └── init_data.py        # 初始化数据采集
├── tests/                   # 测试
├── requirements.txt         # 依赖
├── start_api.sh             # API启动脚本
├── start_scheduler.sh       # 定时任务启动脚本
└── .env.example             # 环境配置示例
```

## 功能

### 1. 数据库设计 ✓

已完成设计以下表：
- `historical_bars` - 历史行情K线数据
- `stock_info` - 股票基础信息
- `positions` - 当前持仓信息
- `trade_records` - 交易记录表
- `trading_signals` - 交易信号表
- `stock_selections` - 选股结果表
- `system_logs` - 系统日志表
- `strategy_configs` - 策略配置表

### 2. API接口开发 ✓

提供以下接口：
- 股票信息查询
- 历史行情查询（分页支持大范围数据）
- 持仓查询
- 选股结果查询（支持按策略、日期筛选）
- 交易信号查询/创建
- 交易记录查询/创建
- FMZ执行接口（信号推送到FMZ执行）
- 账户概览统计

### 3. 数据采集服务 ✓

- A股日线数据采集（AKShare）
- 港股日线数据采集（AKShare）
- 美股日线数据采集（AKShare）
- 定时任务自动采集每日数据
- 支持初始化全量采集

### 4. FMZ执行对接 ✓

- FMZ API客户端封装
- 信号自动执行流程
- 执行结果自动记录交易

### 5. API接口文档 ✓

完整文档在 `../docs/API接口文档.md`

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
pip install akshare
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 填写FMZ API信息
```

### 3. 初始化数据

```bash
cd scripts
python init_data.py
```

这会采集：
- A股全部股票最近1年日线
- 港股前500只最近1年日线
- 美股20只主流股票最近2年日线

### 4. 启动API

```bash
./start_api.sh
```

API服务启动在 `http://localhost:8000`

文档地址: `http://localhost:8000/docs`

### 5. 启动数据采集定时任务

```bash
./start_scheduler.sh
```

会每天自动采集收盘后的行情数据。

## 技术栈

- **Web框架**: FastAPI
- **ORM**: SQLAlchemy
- **数据采集**: AKShare
- **定时任务**: APScheduler
- **数据库**: 支持SQLite/MySQL
- **执行端**: FMZ发明者量化API

## 对接核心策略逻辑

麟算（量化算法工程师）对接方式：

1. **获取历史数据**: `GET /api/v1/bars/{symbol}` 或者直接通过ORM查询数据库
2. **输出选股结果**: 存入 `stock_selections` 表，通过 `bulk_create_stock_selections` 批量插入
3. **生成交易信号**: 创建 `TradingSignal` 记录
4. **执行交易**: 调用 `POST /api/v1/fmz/execute/{signal_id}` 自动发送到FMZ执行并记录交易

详见 `../docs/API接口文档.md`

## 数据流向

```
市场数据 → 定时采集 → PostgreSQL/SQLite ← 
            ↓
OpenClaw策略分析 → 生成选股/交易信号 → 存入数据库 ←
            ↓
API接口 → 麟算核心逻辑读取信号 → 
            ↓
调用FMZ执行接口 → FMZ执行交易 → 回写交易记录
```
