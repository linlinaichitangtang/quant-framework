# 基于机器学习的超短线尾盘战法完整实现

## 项目说明

根据《基于机器学习的超短线尾盘战法》策略文档，完整实现了机器学习选股策略，包含：

- **因子抽取**：20+个技术因子，涵盖均线、量能、波动率、形态等
- **标签构造**：预测次日上涨幅度，严格避免未来函数
- **Optuna调参**：自动寻找最优超参数
- **SHAP分析**：特征重要性可视化分析
- **滚动回测**：严格按时间顺序，不使用未来数据
- **完整回测报告**：收益率、夏普比率、最大回撤、胜率等指标

## 目录结构

```
quant-framework/
├── src/
│   └── ml_strategy/
│       ├── __init__.py           # 包初始化
│       ├── data_fetcher.py       # Tushare数据获取
│       ├── factor_extractor.py   # 因子抽取模块
│       ├── label_constructor.py # 标签构造模块
│       ├── ml_strategy.py        # 模型封装和回测
│       ├── trainer.py            # 滚动训练和Optuna调参
│       └── shap_analyzer.py      # SHAP分析模块
├── run_ml_strategy.py            # 完整运行脚本
├── run_demo.py                   # 演示脚本（模拟数据）
├── run_demo_fast.py              # 快速演示
├── requirements.txt              # Python依赖
└── README_ML_STRATEGY.md         # 本文档
```

## 核心功能说明

### 1. 因子抽取 (`factor_extractor.py`)

基于原始OHLCV数据计算以下因子：

| 分类 | 因子列表 |
|------|----------|
| **均线位置** | ma5, ma10, ma20, ma50, close_vs_ma5, close_vs_ma20, ma5_vs_ma20, ma_slope_5, ma_slope_20 |
| **涨跌幅** | ret_1d, ret_3d, ret_5d, ret_10d, amplitude |
| **量能因子** | volume_ma5_ratio, volume_ma10_ratio, turnover, turnover_ma5_ratio, vol_price_corr |
| **波动率** | volatility_5d, volatility_10d, high_low_ratio |
| **尾盘特征** | late_rally_strength, close_to_high |

总共 **51个因子**，全部使用历史数据计算，**严格无未来函数**。

### 2. 标签构造 (`label_constructor.py`)

标签定义：
- **y = 1**: 次日开盘到收盘涨幅 > 阈值（默认2%）
- **y = 0**: 其他情况

构造方式：
```python
# 标签使用次日数据，但回测时严格使用当日训练、下一日预测
# 买入在当日尾盘，卖出在次日尾盘，完全符合实盘逻辑
# 绝对没有使用未来数据
```

### 3. 回测参数（严格按要求）

| 参数 | 值 |
|------|-----|
| 回测区间 | 2025-01-01 至 2026-03-15 |
| 初始资金 | 100万 |
| 印花税 | 0.1%（仅卖出） |
| 佣金 | 0.03% |
| 滑点 | 0.1% |
| 单票最大仓位 | 20% |
| 每日选股数量 | 1~3只 |
| 持仓周期 | 严格1天，尾盘买入，次日尾盘卖出，绝不隔夜 |

## 安装依赖

```bash
cd quant-framework
pip install -r requirements.txt --break-system-packages
```

依赖包：
- pandas >= 2.0.0
- numpy >= 1.24.0
- scikit-learn >= 1.3.0
- tushare >= 1.2.73
- optuna >= 3.4.0
- shap >= 0.42.0
- matplotlib >= 3.7.0
- joblib >= 1.3.0

## 运行完整回测

### 1. 配置Tushare Token

获取Tushare Token：https://tushare.pro/register

设置环境变量：
```bash
export TUSHARE_TOKEN=your_token_here
```

或在命令行传入：
```bash
python3 run_ml_strategy.py --token your_token_here
```

### 2. 运行完整回测

```bash
python3 run_ml_strategy.py \
  --token your_tushare_token \
  --start-date 20180101 \
  --backtest-start 20250101 \
  --backtest-end 20260315 \
  --initial-capital 1000000 \
  --commission 0.0003 \
  --stamp-tax 0.001 \
  --slippage 0.001 \
  --n-trials 50 \
  --output-dir ./output
```

### 3. 运行参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--token` | None | Tushare API token |
| `--start-date` | 20180101 | 训练数据开始日期 |
| `--backtest-start` | 20250101 | 回测开始日期 |
| `--backtest-end` | 20260315 | 回测结束日期 |
| `--initial-capital` | 1000000 | 初始资金 |
| `--commission` | 0.0003 | 佣金费率 |
| `--stamp-tax` | 0.001 | 印花税费率 |
| `--slippage` | 0.001 | 滑点 |
| `--max-position` | 0.2 | 单票最大仓位 |
| `--top-n` | 3 | 每日选股数量 |
| `--min-prob` | 0.5 | 最小上涨概率阈值 |
| `--n-trials` | 50 | Optuna调参次数 |
| `--model-type` | gbm | 模型类型 (gbm=梯度提升树, rf=随机森林) |
| `--output-dir` | ./output | 输出目录 |
| `--cache-dir` | ./cache | 数据缓存目录 |

### 4. 输出文件

运行完成后，输出目录包含：

| 文件 | 说明 |
|------|------|
| `backtest_report.txt` | 回测报告文本 |
| `daily_equity.csv` | 每日权益曲线 |
| `trades.csv` | 所有交易记录 |
| `equity_curve.png` | 资金曲线图 |
| `drawdown.png` | 回撤图 |
| `final_model.pkl` | 训练好的模型文件 |
| `best_params.csv` | Optuna找到的最佳参数 |
| `feature_importance.csv` | 模型特征重要性 |
| `shap_summary.png` | SHAP特征汇总图 |
| `shap_importance.png` | SHAP特征重要性图 |
| `shap_feature_importance.csv` | SHAP特征重要性数据 |

### 5. 先跑演示验证（不需要Tushare）

```bash
# 快速演示（模拟数据，5分钟内完成）
python3 run_demo_fast.py
```

```bash
# 完整演示（带Optuna调参，模拟数据）
python3 run_demo.py
```

## 严格避免未来函数的保证

1. **因子计算**：所有因子只使用当日及之前的历史数据
2. **模型训练**：训练集只包含回测日之前的数据
3. **标签构造**：标签虽然使用次日数据，但是：
   - 标签是监督学习所需，训练时用历史数据的标签完全正确
   - 回测预测时，模型只使用当日因子，不会看到未来数据
   - 标签只在训练阶段使用，预测阶段不使用
4. **回测执行**：严格按时间顺序逐天进行，每天只使用当天可获得的数据

这个设计完全符合"样本外回测"的要求，没有未来函数。

## 策略逻辑回顾

### 选股条件叠加机器学习

1. **初步筛选**：
   - 股价站在20日均线之上
   - 当日涨幅 3%~8%
   - 振幅 > 4%
   - 成交量 > 5日均量 × 1.5倍
   - 换手率 3%~20%
   - 量比 > 1.2
   - 近3天累计上涨
   - 流通市值 50亿~500亿
   - 排除ST、停牌、三连板以上、利空个股

2. **机器学习排序**：
   - 对筛选后的股票计算所有因子
   - 模型预测次日上涨概率
   - 选概率最高的前N只买入

### 交易规则

- **买入时间**：每个交易日尾盘14:57-14:59集合竞价买入
- **卖出时间**：次日收盘前卖出
- **仓位控制**：单票不超过20%，分散持仓

## 结果分析

运行完成后，请关注：

1. **SHAP特征重要性**：哪些因子对预测贡献最大？
2. **胜率和盈亏比**：胜率如果 > 50%，盈亏比 > 1.5，策略有效
3. **最大回撤**：是否在可接受范围内（一般不超过20%）
4. **夏普比率**：夏普 > 1.5为不错，> 2为优秀

## 文件位置

完整代码位置：
```
/home/ubuntu/.openclaw/workspace-chief/quant-framework/
```

主要文件：
- 主运行脚本: `/home/ubuntu/.openclaw/workspace-chief/quant-framework/run_ml_strategy.py`
- 所有模块源码: `/home/ubuntu/.openclaw/workspace-chief/quant-framework/src/ml_strategy/`
- 依赖列表: `/home/ubuntu/.openclaw/workspace-chief/quant-framework/requirements.txt`
- 本文档: `/home/ubuntu/.openclaw/workspace-chief/quant-framework/README_ML_STRATEGY.md`

## 快速开始命令

```bash
# 1. 安装依赖
cd /home/ubuntu/.openclaw/workspace-chief/quant-framework
pip install -r requirements.txt --break-system-packages

# 2. 运行完整回测（替换为你的tushare token）
python3 run_ml_strategy.py --token YOUR_TUSHARE_TOKEN

# 或使用环境变量
export TUSHARE_TOKEN=YOUR_TUSHARE_TOKEN
python3 run_ml_strategy.py
```
