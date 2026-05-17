#!/usr/bin/env python3
"""
sklearn GBM vs qlib GBDT (LightGBM) 回测对比实验
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# ── 项目路径 ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from ml_strategy.factor_extractor import FactorExtractor
from ml_strategy.label_constructor import LabelConstructor
from ml_strategy.ml_strategy import MLStockPicker, Backtester
from ml_strategy.qlib_gbdt import QlibGBDTWrapper


# ============================================================
# 第一步：环境检查
# ============================================================
print("=" * 60)
print("第一步：环境检查")
print("=" * 60)

import qlib
from lightgbm import LGBMClassifier
from sklearn.ensemble import GradientBoostingClassifier

print(f"  qlib 版本: {qlib.__version__}")
print(f"  LightGBM:  OK")
print(f"  sklearn GBM: OK")
print()


# ============================================================
# 第二步：获取数据（模拟沪深300成分股）
# ============================================================
print("=" * 60)
print("第二步：获取数据")
print("=" * 60)

def generate_mock_stock_data(n_stocks=30, start_date='2023-01-01', end_date='2025-12-31', seed=42):
    """生成模拟股票数据，模拟沪深300成分股特征"""
    np.random.seed(seed)
    dates = pd.bdate_range(start=start_date, end=end_date)
    n_days = len(dates)
    
    all_data = []
    for i in range(n_stocks):
        code = f"{600000 + i:06d}.SH"
        # 随机初始价格 10-100
        base_price = np.random.uniform(10, 100)
        # 随机波动率
        daily_vol = np.random.uniform(0.015, 0.035)
        # 随机漂移
        drift = np.random.uniform(-0.0002, 0.0003)
        
        prices = [base_price]
        for d in range(1, n_days):
            ret = drift + daily_vol * np.random.randn()
            prices.append(prices[-1] * (1 + ret))
        
        prices = np.array(prices)
        
        for d in range(n_days):
            close = prices[d]
            high = close * (1 + abs(np.random.normal(0, 0.01)))
            low = close * (1 - abs(np.random.normal(0, 0.01)))
            open_p = close * (1 + np.random.normal(0, 0.005))
            vol = int(np.random.lognormal(15, 1))
            
            all_data.append({
                'ts_code': code,
                'trade_date': dates[d].strftime('%Y%m%d'),
                'open': round(open_p, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': vol,
            })
    
    df = pd.DataFrame(all_data)
    df = df.sort_values(['ts_code', 'trade_date']).reset_index(drop=True)
    return df


# 尝试用 Tushare 获取真实数据
data_loaded = False
try:
    token = os.environ.get('TUSHARE_TOKEN')
    if token:
        from ml_strategy.data_fetcher import TushareDataFetcher
        fetcher = TushareDataFetcher(token)
        # 获取沪深300部分股票
        codes = ['000001.SZ', '000002.SZ', '000858.SZ', '002304.SZ', '600519.SH',
                 '601318.SH', '600036.SH', '601166.SH', '600276.SH', '000333.SZ']
        stock_data = fetcher.get_all_stock_daily(codes, '20230101', '20251231', cache_dir='./cache')
        if len(stock_data) >= 5:
            all_rows = []
            for code, sdf in stock_data.items():
                sdf = sdf.copy()
                sdf['ts_code'] = code
                all_rows.append(sdf)
            raw_data = pd.concat(all_rows, ignore_index=True)
            raw_data = raw_data.sort_values(['ts_code', 'trade_date']).reset_index(drop=True)
            data_loaded = True
            print(f"  数据来源: Tushare (真实数据)")
except Exception as e:
    print(f"  Tushare 不可用: {e}")

if not data_loaded:
    print("  数据来源: 模拟数据 (numpy随机生成)")
    raw_data = generate_mock_stock_data(n_stocks=30)

n_stocks = raw_data['ts_code'].nunique()
date_range = f"{raw_data['trade_date'].min()} ~ {raw_data['trade_date'].max()}"
print(f"  股票数: {n_stocks} 只")
print(f"  日期范围: {date_range}")
print(f"  总记录数: {len(raw_data)}")
print()


# ============================================================
# 第三步：提取因子 & 构造标签
# ============================================================
print("=" * 60)
print("第三步：提取因子 & 构造标签")
print("=" * 60)

fe = FactorExtractor()
lc = LabelConstructor(threshold=0.02, forward_days=1)

# 对每只股票独立提取因子和标签，然后合并
all_processed = []
for code, grp in raw_data.groupby('ts_code'):
    grp = grp.sort_values('trade_date').copy()
    if len(grp) < 100:
        continue
    grp_fe, factor_cols = fe.extract_all_factors(grp)
    grp_lc = lc.construct_label_with_open(grp_fe)
    all_processed.append(grp_lc)

processed = pd.concat(all_processed, ignore_index=True)

# 因子列
exclude_cols = ['ts_code', 'trade_date', 'code', 'name', 'open', 'high',
               'low', 'close', 'volume', 'amount', 'turnover',
               'circulating_cap', 'total_cap', 'circulating_share',
               'is_st', 'is_suspended', 'has_bad_news', 'consecutive_limit',
               'late_rally', 'next_open', 'next_close', 'return_next_open',
               'return_next_close', 'max_next_high', 'return_next_max',
               'y', 'y_close', 'future_close', 'future_return', 'y_reg']
factor_cols = [c for c in processed.columns if c not in exclude_cols]

# 丢弃含 NaN 的行
valid_mask = processed[factor_cols].notna().all(axis=1) & processed['y'].notna()
processed = processed[valid_mask].copy()
processed = processed.sort_values('trade_date').reset_index(drop=True)

print(f"  因子数: {len(factor_cols)}")
print(f"  因子列表: {factor_cols[:10]}... (共{len(factor_cols)}个)")
print(f"  有效样本数: {len(processed)}")
print(f"  正样本比例: {processed['y'].mean():.4f}")
print()


# ============================================================
# 第四步：训练集划分（取最后一期滚动窗口）
# ============================================================
print("=" * 60)
print("第四步：训练集划分")
print("=" * 60)

TRAIN_WINDOW = 252   # ~1年
TEST_WINDOW = 21     # ~1个月

dates = processed['trade_date'].values
unique_dates = sorted(processed['trade_date'].unique())
n_unique = len(unique_dates)

# 取最后 TRAIN_WINDOW+TEST_WINDOW 个交易日
if n_unique < TRAIN_WINDOW + TEST_WINDOW:
    # 数据不够，按比例缩减
    TRAIN_WINDOW = int(n_unique * 0.8)
    TEST_WINDOW = n_unique - TRAIN_WINDOW

train_end_date = unique_dates[-(TEST_WINDOW + 1)]
test_start_date = unique_dates[-TEST_WINDOW]

train_mask = processed['trade_date'] <= train_end_date
test_mask = processed['trade_date'] > train_end_date

train_df = processed[train_mask].copy()
test_df = processed[test_mask].copy()

X_train = train_df[factor_cols].values
y_train = train_df['y'].values.astype(int)
X_test = test_df[factor_cols].values
y_test = test_df['y'].values.astype(int)

# 处理 NaN
col_means = np.nanmean(X_train, axis=0)
nan_mask_train = np.isnan(X_train)
for j in range(X_train.shape[1]):
    X_train[nan_mask_train[:, j], j] = col_means[j]

nan_mask_test = np.isnan(X_test)
for j in range(X_test.shape[1]):
    X_test[nan_mask_test[:, j], j] = col_means[j]

print(f"  训练集: {len(X_train)} 条 ({train_df['trade_date'].min()} ~ {train_end_date})")
print(f"  测试集: {len(X_test)} 条 ({test_start_date} ~ {test_df['trade_date'].max()})")
print(f"  训练集正样本比例: {y_train.mean():.4f}")
print(f"  测试集正样本比例: {y_test.mean():.4f}")
print()


# ============================================================
# 第五步：训练两个模型
# ============================================================
print("=" * 60)
print("第五步：训练模型")
print("=" * 60)

# --- sklearn GBM ---
print("  [1/2] 训练 sklearn GradientBoostingClassifier ...")
sklearn_picker = MLStockPicker(model_type='gbm', params={
    'n_estimators': 100,
    'learning_rate': 0.1,
    'max_depth': 3,
    'min_samples_split': 20,
    'min_samples_leaf': 5,
    'random_state': 42,
})
sklearn_train_metrics = sklearn_picker.train(X_train, y_train, scale=True)
print(f"        训练 AUC: {sklearn_train_metrics['auc']:.4f}, "
      f"Accuracy: {sklearn_train_metrics['accuracy']:.4f}")

# --- qlib GBDT (LightGBM) ---
print("  [2/2] 训练 qlib LightGBM (QlibGBDTWrapper) ...")
qlib_model = QlibGBDTWrapper(
    n_estimators=100,
    learning_rate=0.1,
    max_depth=3,
    num_leaves=31,
    min_child_samples=5,
    random_state=42,
)

# QlibGBDTWrapper 内部不带 scaler，手动标准化
from sklearn.preprocessing import StandardScaler
qlib_scaler = StandardScaler()
X_train_scaled = qlib_scaler.fit_transform(X_train)
X_test_scaled = qlib_scaler.transform(X_test)

qlib_model.fit(X_train_scaled, y_train)

# 计算训练指标
qlib_train_pred = qlib_model.predict(X_train_scaled)
qlib_train_proba = qlib_model.predict_proba(X_train_scaled)[:, 1]
from sklearn.metrics import accuracy_score, roc_auc_score
qlib_train_acc = accuracy_score(y_train, qlib_train_pred)
qlib_train_auc = roc_auc_score(y_train, qlib_train_proba) if len(np.unique(y_train)) > 1 else 0
print(f"        训练 AUC: {qlib_train_auc:.4f}, Accuracy: {qlib_train_acc:.4f}")
print()


# ============================================================
# 第六步：预测并回测
# ============================================================
print("=" * 60)
print("第六步：预测 & 回测")
print("=" * 60)

def run_backtest(test_df, predict_fn, model_name, factor_cols, top_n=5):
    """
    对测试集跑回测
    predict_fn: 接受 (X) 返回概率数组
    """
    bt = Backtester(
        initial_capital=1_000_000,
        commission=0.0003,
        stamp_tax=0.001,
        slippage=0.001,
    )
    bt.reset()
    
    test_dates = sorted(test_df['trade_date'].unique())
    
    for i, date in enumerate(test_dates):
        day_data = test_df[test_df['trade_date'] == date].copy()
        if len(day_data) == 0:
            continue
        
        # 获取当日价格映射
        price_map = dict(zip(day_data['ts_code'], day_data['close'].values))
        
        # 先记录前一日持仓价值（第0天没有前一日持仓）
        if i > 0:
            bt.calculate_daily_value(date, price_map)
        
        # 如果有持仓，先卖出（T+1日内交易策略：今天买明天卖）
        if bt.holdings and i > 0:
            bt.sell_all_holdings(date, price_map)
        
        # 获取因子矩阵并预测
        X_day = day_data[factor_cols].values
        X_day = np.where(np.isnan(X_day), col_means, X_day)
        probs = predict_fn(X_day)
        
        day_data = day_data.copy()
        day_data['up_prob'] = probs
        
        # 选 top_n 概率最高的
        selected = day_data.nlargest(top_n, 'up_prob')
        
        # 买入
        for _, row in selected.iterrows():
            if row['up_prob'] >= 0.5:
                bt.buy(date, row['ts_code'], row['close'], max_position_pct=1.0/top_n)
    
    # 最后一天记录价值并清仓
    if test_dates:
        last_date = test_dates[-1]
        last_day = test_df[test_df['trade_date'] == last_date]
        price_map = dict(zip(last_day['ts_code'], last_day['close'].values))
        bt.calculate_daily_value(last_date, price_map)
        bt.sell_all_holdings(last_date, price_map)
    
    report = bt.get_backtest_report()
    return report


# sklearn 回测
print("  运行 sklearn GBM 回测 ...")
sklearn_predict_fn = lambda X: sklearn_picker.predict_proba(X)
sklearn_report = run_backtest(test_df, sklearn_predict_fn, "sklearn GBM", factor_cols)

# qlib 回测
print("  运行 qlib LightGBM 回测 ...")
qlib_predict_fn = lambda X: qlib_model.predict_proba(qlib_scaler.transform(X))[:, 1]
qlib_report = run_backtest(test_df, qlib_predict_fn, "qlib LightGBM", factor_cols)
print()


# ============================================================
# 第七步：输出对比报告
# ============================================================
print("=" * 60)
print("第七步：对比报告")
print("=" * 60)

def fmt_pct(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.2f}%"

def fmt_num(v, decimals=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.{decimals}f}"

print()
print("=" * 60)
print("  sklearn GBM vs qlib GBDT 回测对比")
print("=" * 60)
print()
print(f"数据：沪深{n_stocks}只股票（{'真实' if data_loaded else '模拟'}数据）")
print(f"日期：{date_range}")
print(f"因子数：{len(factor_cols)} 个")
print(f"训练集：{len(X_train)} 条，测试集：{len(X_test)} 条")
print()

# sklearn results
s_ret = sklearn_report.get('total_return_pct', 0)
s_ann = sklearn_report.get('annual_return_pct', 0)
s_dd = sklearn_report.get('max_drawdown_pct', 0)
s_sharpe = sklearn_report.get('sharpe_ratio', 0)
s_wr = sklearn_report.get('win_rate', 0) * 100
s_plr = sklearn_report.get('profit_loss_ratio', 0)
s_nt = sklearn_report.get('n_trades', 0)

# qlib results
q_ret = qlib_report.get('total_return_pct', 0)
q_ann = qlib_report.get('annual_return_pct', 0)
q_dd = qlib_report.get('max_drawdown_pct', 0)
q_sharpe = qlib_report.get('sharpe_ratio', 0)
q_wr = qlib_report.get('win_rate', 0) * 100
q_plr = qlib_report.get('profit_loss_ratio', 0)
q_nt = qlib_report.get('n_trades', 0)

print("--- sklearn GradientBoostingClassifier ---")
print(f"  总收益率：  {fmt_pct(s_ret)}")
print(f"  年化收益率：{fmt_pct(s_ann)}")
print(f"  最大回撤：  {fmt_pct(s_dd)}")
print(f"  夏普比率：  {fmt_num(s_sharpe)}")
print(f"  胜率：      {fmt_pct(s_wr)}")
print(f"  盈亏比：    {fmt_num(s_plr)}")
print(f"  总交易次数：{s_nt}")
print()

print("--- qlib LightGBM (QlibGBDTWrapper) ---")
print(f"  总收益率：  {fmt_pct(q_ret)}")
print(f"  年化收益率：{fmt_pct(q_ann)}")
print(f"  最大回撤：  {fmt_pct(q_dd)}")
print(f"  夏普比率：  {fmt_num(q_sharpe)}")
print(f"  胜率：      {fmt_pct(q_wr)}")
print(f"  盈亏比：    {fmt_num(q_plr)}")
print(f"  总交易次数：{q_nt}")
print()

# 对比结论
print("--- 对比结论 ---")
# 赢家判断
if s_ret > q_ret:
    winner = "sklearn GBDT"
elif q_ret > s_ret:
    winner = "qlib GBDT (LightGBM)"
else:
    winner = "持平"

print(f"  赢家（总收益率）：{winner}")
print()
print(f"  收益率差异：sklearn {fmt_pct(s_ret)} vs qlib {fmt_pct(q_ret)} "
      f"(Δ={fmt_pct(s_ret - q_ret)})")
print(f"  夏普差异：  sklearn {fmt_num(s_sharpe)} vs qlib {fmt_num(q_sharpe)} "
      f"(Δ={fmt_num(s_sharpe - q_sharpe)})")
print(f"  回撤差异：  sklearn {fmt_pct(s_dd)} vs qlib {fmt_pct(q_dd)}")
print()

# 主要差异分析
diffs = []
if abs(s_ret - q_ret) > 1:
    diffs.append(f"收益率差异较大({fmt_pct(abs(s_ret - q_ret))})，可能源于树算法差异(sklearn CART vs LightGBM leaf-wise)")
if abs(s_sharpe - q_sharpe) > 0.3:
    diffs.append(f"夏普比率差异明显(Δ={fmt_num(abs(s_sharpe - q_sharpe))})，风险调整后收益不同")
if abs(s_wr - q_wr) > 5:
    diffs.append(f"胜率差异较大(Δ={fmt_pct(abs(s_wr - q_wr))})，选股偏好不同")

if not diffs:
    diffs.append("两者表现接近，差异在统计噪声范围内")

for d in diffs:
    print(f"  • {d}")

print()
print("  建议：")
print("  • 回测窗口较短(~1月)，结论需更多滚动窗口验证")
print("  • LightGBM 训练速度显著快于 sklearn GBM，适合大规模因子库")
print("  • 建议加入多期滚动回测 + 超参优化后再做最终选型")
print("  • 实盘前需考虑涨跌停、停牌等A股特殊约束")
print()
print("=" * 60)
print("  实验完成")
print("=" * 60)
