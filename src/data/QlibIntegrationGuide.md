"""
集成指南：Qlib × quant-framework 融合路线图

目标：在不破坏现有 ML 流水线的前提下，逐步引入 Qlib 因子表达式 + 模型能力。
本文档说明阶段一的接入方案。

────────────────────────────────────────────
快速开始（阶段一：数据层）
────────────────────────────────────────────

1. 安装 pyqlib（在现有 Python 3.9.6 环境中，无冲突）

   pip install pyqlib

2. 在策略中同时使用 quant-framework 原始因子 + Qlib 表达式因子

   from src.data.factors import calc_returns, calc_macd, calc_turnover_volume
   from src.data.qlib_adapter import QlibFactorEngine

   # 原始流水线（不变）
   df = fetcher.get_daily_data(ts_code, start_date, end_date)
   df = calc_returns(df, periods=[1, 5, 20])
   df = calc_macd(df)

   # 新增：Qlib 表达式因子（在原有列上计算，不改原始数据）
   fe = QlibFactorEngine()
   fe.register_factor("mfi_14",      "EMA($close, 14)")        # 技术指标
   fe.register_factor("vol_avg_20",  "Mean($volume, 20)")
   fe.register_factor("vol_r_20",    "$volume / Mean($volume, 20)")
   fe.register_factor("ret_5d",      "Ref($close, 5) / $close - 1")  # 已有的因子也可用表达式重写
   df = fe.calculate_factors(df)    # inplace=False，不影响原始列名

   # 合并后交给 ML 模型
   ml_picker = MLStockPicker()
   signals = ml_picker.predict(df)

────────────────────────────────────────────
Qlib 表达式速查
────────────────────────────────────────────

  Ref($field, N)          N日前值（滞后）
  Mean($field, N)        N日均值
  Std($field, N)         N日标准差
  Sum($field, N)         N日求和
  EMA($field, N)         N日指数移动平均
  Max(A, B) / Min(A, B)  最大/最小值
  Div / Add / Sub / Mul  四则运算（安全除法）
  If(Cond, A, B)         条件选择
  Abs(A) / Log(A)        数学函数
  Lt / Le / Gt / Ge / Eq / Ne   比较运算

  infix 运算符（自动转换）：A + B, A - B, A * B, A / B

────────────────────────────────────────────
quant-framework 现有因子（factors.py）vs Qlib 表达式
────────────────────────────────────────────

  目的相同，用哪个都行（推荐逐步迁移到 Qlib 表达式）：

  calc_returns(df)        →  "Ref($close, N) / $close - 1"
  calc_volatility(df)     →  "Std($close, N)" 或 "Std(Ref($close,1)/$close-1, N)"
  calc_turnover_volume(df) → "$volume / Mean($volume, 20)"
  calc_macd(df)           →  EMA系列因子

────────────────────────────────────────────
与 TushareDataFetcher 的关系
────────────────────────────────────────────

  TushareDataFetcher（数据获取层）负责：
    - 从 Tushare API 拉取原始行情数据
    - 缓存到本地 ./cache/
    - 返回 pd.DataFrame（字段：trade_date/open/high/low/close/volume）

  QlibFactorEngine（特征工程层）负责：
    - 在已有 DataFrame 上计算技术因子
    - 不替代 TushareDataFetcher，两者是串联关系

  数据流：
    TushareDataFetcher → factors.py（原始技术指标） → QlibFactorEngine（qlib表达式）
      → MLStockPicker → Backtester

────────────────────────────────────────────
下一步（阶段二：模型层）
────────────────────────────────────────────

  阶段二将引入：
    - Qlib 因子模型（qlib.model.ExpressionFeature）
    - SOTA 模型：qlib.model.GBDT（LightGBM）、qlib.model.CATBoostModel
    - 替代 sklearn RandomForest/GBM
    - 与现有 rolling_trainer.py 保持接口兼容

────────────────────────────────────────────
"""
