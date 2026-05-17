#!/usr/bin/env python3
"""
Phase 2 完善版：sklearn GBM vs qlib GBDT 多周期滚动回测对比
新增：统计显著性检验、多窗口验证、置信区间
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy import stats
from typing import Dict, List, Tuple

warnings.filterwarnings('ignore')

# ── 项目路径 ──
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from ml_strategy.factor_extractor import FactorExtractor
from ml_strategy.label_constructor import LabelConstructor
from ml_strategy.ml_strategy import MLStockPicker, Backtester
from ml_strategy.qlib_gbdt import QlibGBDTWrapper
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, roc_auc_score


# ============================================================
# 配置参数
# ============================================================
CONFIG = {
    'train_window': 252,      # ~1年训练
    'test_window': 21,        # ~1月测试
    'n_rollings': 12,         # 滚动12期
    'top_n': 5,               # 每日选股数
    'initial_capital': 1_000_000,
    'commission': 0.0003,
    'stamp_tax': 0.001,
    'slippage': 0.001,
    'n_bootstrap': 1000,      # Bootstrap次数
    'confidence_level': 0.95,   # 置信水平
}


# ============================================================
# 数据加载
# ============================================================
def load_data() -> pd.DataFrame:
    """加载数据：优先真实数据，否则模拟"""
    data_loaded = False
    raw_data = None
    
    try:
        token = os.environ.get('TUSHARE_TOKEN')
        if token:
            from ml_strategy.data_fetcher import TushareDataFetcher
            fetcher = TushareDataFetcher(token)
            codes = ['000001.SZ', '000002.SZ', '000858.SZ', '002304.SZ', '600519.SH',
                     '601318.SH', '600036.SH', '601166.SH', '600276.SH', '000333.SZ',
                     '000568.SZ', '000538.SZ', '002142.SZ', '600887.SH', '600309.SH',
                     '600009.SH', '600690.SH', '601012.SH', '300750.SZ', '002594.SZ']
            stock_data = fetcher.get_all_stock_daily(
                codes, '20220101', '20251231', cache_dir='./cache'
            )
            if len(stock_data) >= 10:
                all_rows = []
                for code, sdf in stock_data.items():
                    sdf = sdf.copy()
                    sdf['ts_code'] = code
                    all_rows.append(sdf)
                raw_data = pd.concat(all_rows, ignore_index=True)
                raw_data = raw_data.sort_values(['ts_code', 'trade_date']).reset_index(drop=True)
                data_loaded = True
                print(f"✅ 数据来源: Tushare (真实数据, {len(stock_data)}只股票)")
    except Exception as e:
        print(f"⚠️ Tushare 不可用: {e}")
    
    if not data_loaded:
        print("⚠️ 使用模拟数据")
        raw_data = generate_mock_stock_data(n_stocks=50, start_date='2022-01-01', end_date='2025-12-31')
    
    return raw_data, data_loaded


def generate_mock_stock_data(n_stocks=50, start_date='2022-01-01', end_date='2025-12-31', seed=42):
    """生成模拟股票数据"""
    np.random.seed(seed)
    dates = pd.bdate_range(start=start_date, end=end_date)
    n_days = len(dates)
    
    all_data = []
    for i in range(n_stocks):
        code = f"{600000 + i:06d}.SH" if i < 25 else f"{1 + i - 25:06d}.SZ"
        base_price = np.random.uniform(10, 100)
        daily_vol = np.random.uniform(0.015, 0.035)
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
    return df.sort_values(['ts_code', 'trade_date']).reset_index(drop=True)


# ============================================================
# 因子提取
# ============================================================
def extract_factors(raw_data: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """提取因子和标签"""
    fe = FactorExtractor()
    lc = LabelConstructor(threshold=0.02, forward_days=1)
    
    all_processed = []
    for code, grp in raw_data.groupby('ts_code'):
        grp = grp.sort_values('trade_date').copy()
        if len(grp) < 100:
            continue
        grp_fe, _ = fe.extract_all_factors(grp)
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
    
    # 清洗NaN
    valid_mask = processed[factor_cols].notna().all(axis=1) & processed['y'].notna()
    processed = processed[valid_mask].copy()
    processed = processed.sort_values('trade_date').reset_index(drop=True)
    
    return processed, factor_cols


# ============================================================
# 滚动回测引擎
# ============================================================
def rolling_backtest(processed: pd.DataFrame, factor_cols: List[str], 
                     model_type: str, config: Dict) -> Dict:
    """
    多期滚动回测
    :param model_type: 'sklearn' 或 'qlib'
    :return: 每期回测结果列表
    """
    dates = sorted(processed['trade_date'].unique())
    n_dates = len(dates)
    
    train_window = config['train_window']
    test_window = config['test_window']
    n_rollings = config['n_rollings']
    
    results = []
    
    # 从后往前取n_rollings个测试窗口
    for i in range(n_rollings):
        test_end_idx = n_dates - i * test_window
        test_start_idx = test_end_idx - test_window
        train_end_idx = test_start_idx
        train_start_idx = max(0, train_end_idx - train_window)
        
        if train_start_idx < 0 or test_start_idx < 0:
            continue
        
        train_dates = dates[train_start_idx:train_end_idx]
        test_dates = dates[test_start_idx:test_end_idx]
        
        train_df = processed[processed['trade_date'].isin(train_dates)].copy()
        test_df = processed[processed['trade_date'].isin(test_dates)].copy()
        
        if len(train_df) < 100 or len(test_df) < 20:
            continue
        
        # 训练模型
        X_train = train_df[factor_cols].values
        y_train = train_df['y'].values.astype(int)
        X_test = test_df[factor_cols].values
        
        # 处理NaN
        col_means = np.nanmean(X_train, axis=0)
        X_train = np.where(np.isnan(X_train), col_means, X_train)
        X_test = np.where(np.isnan(X_test), col_means, X_test)
        
        if model_type == 'sklearn':
            model = MLStockPicker(model_type='gbm', params={
                'n_estimators': 100, 'learning_rate': 0.1, 'max_depth': 3,
                'random_state': 42,
            })
            model.train(X_train, y_train, scale=True)
            predict_fn = lambda X: model.predict_proba(X)
            
        elif model_type == 'qlib':
            scaler = StandardScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)
            model = QlibGBDTWrapper(n_estimators=100, learning_rate=0.1, 
                                    max_depth=3, num_leaves=31, random_state=42)
            model.fit(X_train_s, y_train)
            predict_fn = lambda X: model.predict_proba(scaler.transform(X))[:, 1]
        
        # 回测
        report = run_single_backtest(test_df, predict_fn, factor_cols, config, col_means)
        report['period'] = i + 1
        report['train_dates'] = f"{train_dates[0]}~{train_dates[-1]}"
        report['test_dates'] = f"{test_dates[0]}~{test_dates[-1]}"
        report['n_train'] = len(train_df)
        report['n_test'] = len(test_df)
        results.append(report)
    
    return {'results': results, 'model_type': model_type}


def run_single_backtest(test_df: pd.DataFrame, predict_fn, factor_cols: List[str],
                        config: Dict, col_means: np.ndarray) -> Dict:
    """单次回测"""
    bt = Backtester(
        initial_capital=config['initial_capital'],
        commission=config['commission'],
        stamp_tax=config['stamp_tax'],
        slippage=config['slippage'],
    )
    bt.reset()
    
    test_dates = sorted(test_df['trade_date'].unique())
    daily_returns = []
    
    for i, date in enumerate(test_dates):
        day_data = test_df[test_df['trade_date'] == date].copy()
        if len(day_data) == 0:
            continue
        
        price_map = dict(zip(day_data['ts_code'], day_data['close'].values))
        
        if i > 0:
            bt.calculate_daily_value(date, price_map)
            prev_value = bt.daily_values[-1]['total_value'] if bt.daily_values else config['initial_capital']
            if i > 1:
                prev_prev_value = bt.daily_values[-2]['total_value'] if len(bt.daily_values) > 1 else config['initial_capital']
                daily_ret = (prev_value - prev_prev_value) / prev_prev_value
                daily_returns.append(daily_ret)
        
        if bt.holdings and i > 0:
            bt.sell_all_holdings(date, price_map)
        
        X_day = day_data[factor_cols].values
        X_day = np.where(np.isnan(X_day), col_means, X_day)
        probs = predict_fn(X_day)
        
        day_data['up_prob'] = probs
        selected = day_data.nlargest(config['top_n'], 'up_prob')
        
        for _, row in selected.iterrows():
            if row['up_prob'] >= 0.5:
                bt.buy(date, row['ts_code'], row['close'], max_position_pct=1.0/config['top_n'])
    
    if test_dates:
        last_date = test_dates[-1]
        last_day = test_df[test_df['trade_date'] == last_date]
        price_map = dict(zip(last_day['ts_code'], last_day['close'].values))
        bt.calculate_daily_value(last_date, price_map)
        bt.sell_all_holdings(last_date, price_map)
    
    report = bt.get_backtest_report()
    report['daily_returns'] = daily_returns
    return report


# ============================================================
# 统计检验
# ============================================================
def statistical_test(sklearn_results: List[Dict], qlib_results: List[Dict], 
                     config: Dict) -> Dict:
    """
    统计显著性检验
    """
    s_rets = [r['total_return_pct'] for r in sklearn_results if r.get('total_return_pct') is not None]
    q_rets = [r['total_return_pct'] for r in qlib_results if r.get('total_return_pct') is not None]
    
    s_sharpes = [r['sharpe_ratio'] for r in sklearn_results if r.get('sharpe_ratio') is not None]
    q_sharpes = [r['sharpe_ratio'] for r in qlib_results if r.get('sharpe_ratio') is not None]
    
    # 配对t检验（同周期对比）
    min_len = min(len(s_rets), len(q_rets))
    if min_len >= 2:
        s_rets_arr = np.array(s_rets[:min_len])
        q_rets_arr = np.array(q_rets[:min_len])
        diff = s_rets_arr - q_rets_arr
        
        t_stat, p_value = stats.ttest_rel(s_rets_arr, q_rets_arr)
        
        # Bootstrap置信区间
        boot_diffs = []
        for _ in range(config['n_bootstrap']):
            idx = np.random.choice(min_len, size=min_len, replace=True)
            boot_diffs.append(np.mean(s_rets_arr[idx] - q_rets_arr[idx]))
        
        alpha = 1 - config['confidence_level']
        ci_lower = np.percentile(boot_diffs, alpha/2 * 100)
        ci_upper = np.percentile(boot_diffs, (1 - alpha/2) * 100)
        
        # Wilcoxon符号秩检验（非参数）
        if min_len >= 3:
            w_stat, w_pvalue = stats.wilcoxon(s_rets_arr, q_rets_arr)
        else:
            w_stat, w_pvalue = None, None
    else:
        t_stat, p_value, ci_lower, ci_upper, w_stat, w_pvalue = None, None, None, None, None, None
    
    return {
        'sklearn_mean_ret': np.mean(s_rets) if s_rets else None,
        'sklearn_std_ret': np.std(s_rets) if s_rets else None,
        'sklearn_mean_sharpe': np.mean(s_sharpes) if s_sharpes else None,
        'qlib_mean_ret': np.mean(q_rets) if q_rets else None,
        'qlib_std_ret': np.std(q_rets) if q_rets else None,
        'qlib_mean_sharpe': np.mean(q_sharpes) if q_sharpes else None,
        'paired_t_stat': t_stat,
        'paired_t_pvalue': p_value,
        'wilcoxon_stat': w_stat,
        'wilcoxon_pvalue': w_pvalue,
        'bootstrap_ci_lower': ci_lower,
        'bootstrap_ci_upper': ci_upper,
        'n_periods': min_len,
    }


# ============================================================
# 报告输出
# ============================================================
def print_report(sklearn_res: Dict, qlib_res: Dict, stats: Dict, config: Dict):
    """打印对比报告"""
    print("\n" + "=" * 80)
    print("  Phase 2 完善版：多周期滚动回测对比报告")
    print("=" * 80)
    
    print(f"\n📊 实验配置:")
    print(f"  训练窗口: {config['train_window']} 交易日 (~1年)")
    print(f"  测试窗口: {config['test_window']} 交易日 (~1月)")
    print(f"  滚动期数: {config['n_rollings']} 期")
    print(f"  每日选股: Top {config['top_n']}")
    print(f"  Bootstrap: {config['n_bootstrap']} 次")
    print(f"  置信水平: {config['confidence_level']*100:.0f}%")
    
    print(f"\n📈 sklearn GBM 结果 ({stats['n_periods']}期):")
    print(f"  平均总收益率: {stats['sklearn_mean_ret']:.2f}% (±{stats['sklearn_std_ret']:.2f}%)")
    print(f"  平均夏普比率: {stats['sklearn_mean_sharpe']:.3f}")
    
    print(f"\n📈 qlib LightGBM 结果 ({stats['n_periods']}期):")
    print(f"  平均总收益率: {stats['qlib_mean_ret']:.2f}% (±{stats['qlib_std_ret']:.2f}%)")
    print(f"  平均夏普比率: {stats['qlib_mean_sharpe']:.3f}")
    
    print(f"\n🔬 统计检验:")
    if stats['paired_t_pvalue'] is not None:
        print(f"  配对t检验: t={stats['paired_t_stat']:.3f}, p={stats['paired_t_pvalue']:.4f}")
        sig = "显著" if stats['paired_t_pvalue'] < 0.05 else "不显著"
        print(f"  收益差异: {sig} (α=0.05)")
    
    if stats['wilcoxon_pvalue'] is not None:
        print(f"  Wilcoxon检验: W={stats['wilcoxon_stat']:.1f}, p={stats['wilcoxon_pvalue']:.4f}")
    
    if stats['bootstrap_ci_lower'] is not None:
        print(f"  Bootstrap {config['confidence_level']*100:.0f}% CI: [{stats['bootstrap_ci_lower']:.2f}%, {stats['bootstrap_ci_upper']:.2f}%]")
        if stats['bootstrap_ci_lower'] > 0:
            print(f"  → sklearn 显著优于 qlib")
        elif stats['bootstrap_ci_upper'] < 0:
            print(f"  → qlib 显著优于 sklearn")
        else:
            print(f"  → 两者无显著差异")
    
    # 每期明细
    print(f"\n📋 每期明细:")
    print(f"  {'期数':>4} | {'测试日期':>20} | {'sklearn收益':>12} | {'qlib收益':>12} | {'差异':>10}")
    print("  " + "-" * 70)
    for i in range(stats['n_periods']):
        s_ret = sklearn_res['results'][i]['total_return_pct']
        q_ret = qlib_res['results'][i]['total_return_pct']
        diff = s_ret - q_ret
        dates_str = sklearn_res['results'][i]['test_dates']
        print(f"  {i+1:>4} | {dates_str:>20} | {s_ret:>11.2f}% | {q_ret:>11.2f}% | {diff:>+9.2f}%")
    
    print("\n" + "=" * 80)
    print("  结论与建议:")
    if stats['paired_t_pvalue'] is not None and stats['paired_t_pvalue'] < 0.05:
        winner = "sklearn GBM" if stats['sklearn_mean_ret'] > stats['qlib_mean_ret'] else "qlib LightGBM"
        print(f"  ✅ {winner} 在统计上显著更优 (p={stats['paired_t_pvalue']:.4f})")
    else:
        print(f"  ⚠️ 两者无统计显著差异，建议根据训练速度/内存占用选型")
    
    print(f"  💡 LightGBM 训练速度通常快 5-10x，适合大规模因子挖掘")
    print(f"  💡 sklearn GBM 更稳定，适合小样本场景")
    print("=" * 80)


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 80)
    print("Phase 2 完善版：sklearn GBM vs qlib GBDT 多周期滚动回测")
    print("=" * 80)
    
    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    raw_data, data_loaded = load_data()
    
    # 2. 提取因子
    print("[2/4] 提取因子...")
    processed, factor_cols = extract_factors(raw_data)
    print(f"  有效样本: {len(processed)}, 因子数: {len(factor_cols)}")
    
    # 3. 滚动回测
    print("[3/4] 滚动回测 (sklearn GBM)...")
    sklearn_res = rolling_backtest(processed, factor_cols, 'sklearn', CONFIG)
    
    print("[3/4] 滚动回测 (qlib LightGBM)...")
    qlib_res = rolling_backtest(processed, factor_cols, 'qlib', CONFIG)
    
    # 4. 统计检验
    print("[4/4] 统计检验...")
    stats = statistical_test(sklearn_res['results'], qlib_res['results'], CONFIG)
    
    # 5. 输出报告
    print_report(sklearn_res, qlib_res, stats, CONFIG)
    
    # 6. 保存结果
    result_df = pd.DataFrame({
        'period': [r['period'] for r in sklearn_res['results'][:stats['n_periods']]],
        'test_dates': [r['test_dates'] for r in sklearn_res['results'][:stats['n_periods']]],
        'sklearn_return': [r['total_return_pct'] for r in sklearn_res['results'][:stats['n_periods']]],
        'qlib_return': [r['total_return_pct'] for r in qlib_res['results'][:stats['n_periods']]],
    })
    result_df['diff'] = result_df['sklearn_return'] - result_df['qlib_return']
    result_df.to_csv('backtest_comparison_results.csv', index=False)
    print(f"\n💾 结果已保存至 backtest_comparison_results.csv")


if __name__ == '__main__':
    main()
