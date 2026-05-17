# Qlib 融合指南 v2.0

## 架构概览

```
quant-framework
├── src/data/
│   ├── qlib_adapter.py          # Phase 1: 因子表达式引擎
│   └── qlib_data_provider.py     # Phase 2B: 数据缓存层
├── src/ml_strategy/
│   ├── qlib_gbdt.py              # Phase 2A: GBDT模型封装
│   ├── ml_strategy.py            # 回测引擎
│   └── trainer.py                # 滚动训练
├── run_backtest_compare_v2.py    # Phase 2: 多周期回测对比
└── rd_agent_factor_mining.py     # Phase 3: 自动因子挖掘
```

## 快速开始

### 1. 因子表达式计算

```python
from src.data.qlib_adapter import QlibFactorEngine

engine = QlibFactorEngine()
engine.register_factor("ma5", "Mean($close, 5)")
engine.register_factor("ret_5d", "Ref($close, 5) / $close - 1")
engine.register_factor("vol_ratio", "$volume / Mean($volume, 20)")

# 计算因子
df_with_factors = engine.calculate_factors(df)
```

### 2. Qlib GBDT模型

```python
from src.ml_strategy.qlib_gbdt import QlibGBDTWrapper

model = QlibGBDTWrapper(
    n_estimators=100,
    learning_rate=0.1,
    max_depth=3,
    num_leaves=31,
)

model.fit(X_train, y_train)
proba = model.predict_proba(X_test)
```

### 3. 数据缓存

```python
from src.data.qlib_data_provider import QlibDataCache

cache = QlibDataCache(cache_dir='./cache/qlib')
df = cache.get_stock_data('000001.SZ', '20240101', '20241231')
```

### 4. 多周期回测对比

```bash
cd quant-framework
python run_backtest_compare_v2.py
```

输出：
- 12期滚动回测结果
- 配对t检验 / Wilcoxon检验
- Bootstrap置信区间
- `backtest_comparison_results.csv`

### 5. RD-Agent自动因子挖掘

```bash
python rd_agent_factor_mining.py
```

输出：
- Top10因子表达式（IC/IR排序）
- 进化曲线
- `rd_agent_factors.csv`

## 核心特性

| 模块 | 特性 |
|------|------|
| QlibFactorEngine | 支持56+算子，infix表达式，$field语法 |
| QlibGBDTWrapper | sklearn兼容接口，LightGBM后端，joblib序列化 |
| QlibDataCache | Tushare数据源，CSV缓存，批量获取 |
| 回测对比v2 | 多期滚动，统计检验，置信区间 |
| RD-Agent | 遗传算法，IC/IR适应度，自动发现 |

## 下一步

- [ ] 实盘对接：富途/华泰接口
- [ ] 深度学习：LSTM/Transformer因子
- [ ] 组合优化：风险平价 + Black-Litterman
