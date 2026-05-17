# quant-framework ML 集成 SPEC v1.0

## 1. 目标

将 `src/ml_strategy/` 独立原型（Phase 1~3 + Task 1~4）接入 `backend/app/` 主框架 FastAPI，变成真实可调用的 REST API：

- ✅ 因子挖掘 → API 可调用
- ✅ 超参优化 → API 可调用
- ✅ 滚动训练 → API 可调用
- ✅ 选股预测 → API 可调用
- ✅ 回测 → API 可调用（替换现有 mock）

## 2. 架构

```
FastAPI (backend/app/)
├── ml_api.py         ← 新增 / 修改
│   └── /api/v1/ml/run_factor_mining      POST  启动因子挖掘
│   └── /api/v1/ml/run_hpo                POST  启动超参优化
│   └── /api/v1/ml/run_rolling_train      POST  启动滚动训练
│   └── /api/v1/ml/predict                POST  选股预测
│   └── /api/v1/ml/run_backtest           POST  回测（替换mock）
│
├── ml_service.py    ← 新增核心调度逻辑
│   └── ML集成服务：封装 src/ml_strategy 所有模块
│
└── src/ml_strategy/  ← 新增为 backend/src/ml_strategy/
    ├── qlib_adapter.py    ✅ 已完成
    ├── futu_data_fetcher.py ✅ 已完成
    ├── factor_extractor.py ✅ 已完成
    ├── label_constructor.py ✅ 已完成
    ├── ml_strategy.py      ✅ 已完成
    ├── trainer.py          ✅ 已完成
    ├── rd_agent_factor_mining.py ✅ 已完成
    ├── rd_agent_hpo.py     ✅ 已完成
    └── run_backtest_compare_v2.py ✅ 已完成

数据层：
├── FutuDataFetcher → 替换 TushareDataFetcher（已实现）
│   └── 需要 Futu OpenD 运行在 127.0.0.1:11111
└── backend/app/models.py → BacktestResult 表直接复用
```

## 3. API 设计

### 3.1 因子挖掘 POST `/api/v1/ml/run_factor_mining`

**Request:**
```json
{
  "population_size": 50,
  "n_generations": 20,
  "min_ic_threshold": 0.01
}
```

**Response:**
```json
{
  "data": {
    "task_id": "fm_xxxxx",
    "status": "running",
    "top_factors": [...]
  }
}
```

### 3.2 超参优化 POST `/api/v1/ml/run_hpo`

**Request:**
```json
{
  "symbol": "QQQ",
  "market": "US",
  "n_trials": 50,
  "model_type": "gbm"
}
```

**Response:**
```json
{
  "data": {
    "task_id": "hpo_xxxxx",
    "status": "running",
    "best_params": {...},
    "best_ic": 0.031,
    "best_ir": 1.56
  }
}
```

### 3.3 滚动训练 POST `/api/v1/ml/run_rolling_train`

**Request:**
```json
{
  "symbols": ["QQQ", "AAPL"],
  "market": "US",
  "train_window": 252,
  "step": 21,
  "model_type": "gbm",
  "n_trials": 50
}
```

**Response:**
```json
{
  "data": {
    "task_id": "rt_xxxxx",
    "status": "running",
    "model_path": "./models/rolling_gbm_20260503.pkl"
  }
}
```

### 3.4 选股预测 POST `/api/v1/ml/predict`

**Request:**
```json
{
  "symbols": ["QQQ", "AAPL", "TSLA"],
  "market": "US",
  "model_path": "./models/rolling_gbm_20260503.pkl",
  "top_n": 3,
  "min_prob": 0.5
}
```

**Response:**
```json
{
  "data": {
    "selections": [
      {"symbol": "AAPL", "confidence": 0.72, "direction": "UP"},
      {"symbol": "QQQ", "confidence": 0.65, "direction": "UP"}
    ]
  }
}
```

### 3.5 回测 PUT `/api/v1/backtest/run_new_backtest`（改造）

**改动**：替换 mock 数据生成 → 调用真实 `MLStockPicker + Backtester`

**Request:**
```json
{
  "name": "ML尾盘选股策略",
  "strategy_type": "ml_stock_picker",
  "market": "US",
  "initial_capital": 100000,
  "symbols": ["QQQ", "AAPL", "TSLA", "MSFT"],
  "start_date": "20250101",
  "end_date": "20260315",
  "top_n": 3,
  "min_prob": 0.5,
  "model_type": "gbm",
  "model_path": "./models/rolling_gbm_20260503.pkl"
}
```

**Response**（不变，仅数据变真实）：
```json
{
  "data": {
    "backtest_id": "bt_xxxxx",
    "total_return": 0.153,
    "annual_return": 0.892,
    "sharpe_ratio": 2.31,
    "max_drawdown": -0.081,
    "win_rate": 0.67,
    "trades": [...]
  }
}
```

## 4. 数据流

```
FutuDataFetcher (数据源)
  │ (或 TushareDataFetcher fallback)
  ▼
FactorExtractor (30+技术因子)
  │ raw_price_df
  ▼
LabelConstructor (y = 次日涨幅≥2%)
  ▼
OptunaOptimizer (HPO) → best_params → MLStockPicker.train()
  │
  ▼
MLStockPicker (sklearn GBM/RF)
  │
  ├──→ Backtester (逐日尾盘买入→次日卖出)
  │     │
  │     └──→ backtest_report (指标)
  │
  └──→ predict (选股)
        │
        └──→ selections (选股结果)
```

## 5. 依赖管理

在 `backend/requirements.txt` 新增：

```
qlib>=0.9.7
lightgbm
optuna
shap
joblib
scikit-learn
```

**注意**：`qlib` 安装较重（几十个依赖），可选；如果导入失败则 fallback 到 `sklearn.GradientBoosting`，功能不变。

## 6. 实施顺序

### Phase A：基础设施（预计 2h）
1. 创建 `backend/src/ml_strategy/` 目录
2. 软链/复制 `src/data/qlib_adapter.py` → `backend/src/data/qlib_adapter.py`
3. 软链/复制 `src/ml_strategy/*.py` → `backend/src/ml_strategy/`
4. 追加 `backend/requirements.txt`
5. 写 `backend/src/ml_strategy/__init__.py`

### Phase B：ML Service 集成（预计 3h）
1. 写 `backend/app/ml_integration_service.py`（核心调度类）
2. 重写 `ml_api.py` 新增 5 个端点
3. 数据库：`BacktestResult` 表复用，字段不变

### Phase C：回测 API 改造（预计 2h）
1. 重写 `backtest_service.py` 的 `run_backtest()` 真实调用
2. 保留原有 `run_backtest()` 函数签名，接口不变

### Phase D：测试验证（预计 2h）
1. 单元测试：各模块独立调用
2. 集成测试：API 端到端
3. Futu OpenD 连通性测试

## 7. 验收标准

- [ ] `GET /api/v1/ml/features` 返回真实因子列表（不再是硬编码）
- [ ] `POST /api/v1/ml/run_hpo` 返回真实 HPO 结果
- [ ] `POST /api/v1/ml/run_rolling_train` 返回真实训练结果
- [ ] `POST /api/v1/backtest/run_new_backtest` 返回真实回测数据（非 mock）
- [ ] `POST /api/v1/ml/predict` 返回选股结果
- [ ] `GET /api/v1/backtest` 列表正常

## 8. 风险与折中

| 风险 | 应对 |
|------|------|
| Futu OpenD 未启动 | API 返回"数据源未就绪"，前端提示启动 OpenD |
| qlib 安装失败 | fallback 到纯 sklearn，不影响核心流程 |
| 回测耗时（252天×多只） | 后台异步任务，API 立即返回 task_id |
