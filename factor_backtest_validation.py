#!/usr/bin/env python3
"""
因子回测验证脚本 — 对RD-Agent挖掘的Top因子进行独立回测

思路：
1. 对每个因子单独跑12期滚动回测
2. 用因子值排序选股（Top N做多，Bottom N做空）
3. 衡量：每期收益、IC稳定性、夏普比率、最大回撤
4. 对比：因子策略 vs 等权基准
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd
from scipy import stats
from typing import List, Dict, Tuple, Optional

warnings.filterwarnings('ignore')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from data.qlib_adapter import QlibExpressionParser
from ml_strategy.factor_extractor import FactorExtractor
from ml_strategy.label_constructor import LabelConstructor


# ============================================================
# 配置
# ============================================================
CONFIG = {
    'train_window': 252,
    'test_window': 21,
    'n_rollings': 12,
    'top_n': 5,          # 选股数
    'signal_threshold': 0.5,  # 信号阈值（因子排名分位点）
    'initial_capital': 1_000_000,
    'commission': 0.0003,
    'stamp_tax': 0.001,
    'slippage': 0.001,
}


# ============================================================
# 数据
# ============================================================
def generate_mock_stock_data(n_stocks=50, start_date='2022-01-01', end_date='2025-12-31', seed=42):
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


def load_data() -> Tuple[pd.DataFrame, bool]:
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


# ============================================================
# 因子计算
# ============================================================
def compute_factor(df: pd.DataFrame, expression: str) -> pd.Series:
    """用QlibExpressionParser计算单因子"""
    try:
        df = df.copy()
        rename = {}
        for c in df.columns:
            if c.lower() in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                rename[c] = f'${c.lower()}'
        if rename:
            df = df.rename(columns=rename)
        
        parser = QlibExpressionParser(df)
        values = parser.evaluate(expression)
        return values
    except Exception as e:
        return None


# ============================================================
# 单因子回测
# ============================================================
def single_factor_backtest(processed: pd.DataFrame, expression: str, factor_name: str,
                             config: Dict) -> Dict:
    """
    对单个因子跑12期滚动回测
    策略：因子值越高越买入（long only）
    """
    dates = sorted(processed['trade_date'].unique())
    n_dates = len(dates)
    train_window = config['train_window']
    test_window = config['test_window']
    n_rollings = config['n_rollings']
    top_n = config['top_n']
    
    results = []
    
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
        
        # 计算因子值
        train_factor = compute_factor(train_df, expression)
        test_factor = compute_factor(test_df, expression)
        
        if train_factor is None or test_factor is None:
            continue
        
        # 存储因子值
        train_df = train_df.copy()
        test_df = test_df.copy()
        train_df['factor'] = train_factor
        test_df['factor'] = test_factor
        
        # 删除NaN
        train_df = train_df.dropna(subset=['factor', 'return_next_close'])
        test_df = test_df.dropna(subset=['factor', 'return_next_close'])
        
        if len(train_df) < 50 or len(test_df) < 10:
            continue
        
        # 计算IC（训练集）
        train_ic = np.corrcoef(train_df['factor'].values, train_df['return_next_close'].values)[0, 1]
        if np.isnan(train_ic):
            continue
        
        # 测试集回测
        # 选因子值最高的top_n只股票
        test_df = test_df.sort_values('factor', ascending=False)
        
        period_returns = []
        for date in test_dates:
            day_df = test_df[test_df['trade_date'] == date]
            if len(day_df) == 0:
                continue
            
            # 选top_n
            selected = day_df.head(top_n)
            if len(selected) == 0:
                continue
            
            # 平均收益率
            avg_return = selected['return_next_close'].mean()
            period_returns.append(avg_return)
        
        # 计算各项指标
        if len(period_returns) == 0:
            continue
        
        total_return = np.prod(1 + np.array(period_returns)) - 1
        annual_return = (1 + total_return) ** (252 / len(period_returns)) - 1 if len(period_returns) > 0 else 0
        sharpe = np.mean(period_returns) / np.std(period_returns) * np.sqrt(252) if np.std(period_returns) > 0 else 0
        max_drawdown = 0
        cumulative = np.cumprod(1 + np.array(period_returns))
        for j in range(len(cumulative)):
            peak = np.max(cumulative[:j+1])
            dd = (cumulative[j] - peak) / peak
            if dd < max_drawdown:
                max_drawdown = dd
        
        # 测试集IC
        if 'factor' in test_df.columns and 'return_next_close' in test_df.columns:
            test_ic = np.corrcoef(test_df['factor'].values, test_df['return_next_close'].values)[0, 1]
            test_ic = test_ic if not np.isnan(test_ic) else 0
        else:
            test_ic = 0
        
        result = {
            'period': i + 1,
            'train_dates': f"{train_dates[0]}~{train_dates[-1]}",
            'test_dates': f"{test_dates[0]}~{test_dates[-1]}",
            'train_ic': train_ic,
            'test_ic': test_ic,
            'n_train': len(train_df),
            'n_test': len(test_df),
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'n_trades': len(period_returns),
            'avg_return_per_trade': np.mean(period_returns),
            'win_rate': np.mean([r > 0 for r in period_returns]),
        }
        results.append(result)
    
    return {
        'factor_name': factor_name,
        'expression': expression,
        'results': results,
    }


# ============================================================
# 批量回测
# ============================================================
def batch_backtest(processed: pd.DataFrame, factors: List[Dict], config: Dict) -> List[Dict]:
    """对多个因子批量回测"""
    all_results = []
    
    for i, fact in enumerate(factors):
        expr = fact['expression']
        name = fact.get('name', f"factor_{i+1}")
        print(f"\n[{i+1}/{len(factors)}] 回测因子: {name}")
        print(f"  表达式: {expr[:70]}...")
        
        result = single_factor_backtest(processed, expr, name, config)
        all_results.append(result)
        
        if result['results']:
            last = result['results'][-1]
            print(f"  测试集IC: {last['test_ic']:.4f}")
            print(f"  总收益: {last['total_return']*100:.2f}%")
            print(f"  夏普: {last['sharpe_ratio']:.2f}")
    
    return all_results


# ============================================================
# 统计汇总
# ============================================================
def summarize_results(all_results: List[Dict]) -> pd.DataFrame:
    """汇总所有因子的回测结果"""
    rows = []
    
    for res in all_results:
        if not res['results']:
            continue
        
        rets = [r['total_return'] for r in res['results']]
        sharpes = [r['sharpe_ratio'] for r in res['results']]
        train_ics = [r['train_ic'] for r in res['results']]
        test_ics = [r['test_ic'] for r in res['results']]
        
        rows.append({
            'factor_name': res['factor_name'],
            'expression': res['expression'],
            'mean_train_ic': np.mean(train_ics),
            'mean_test_ic': np.mean(test_ics),
            'ic_decay': np.mean(train_ics) - np.mean(test_ics),
            'std_test_ic': np.std(test_ics),
            'mean_return': np.mean(rets),
            'std_return': np.std(rets),
            'mean_sharpe': np.mean(sharpes),
            'max_drawdown': max(r['max_drawdown'] for r in res['results']),
            'win_rate': np.mean([r['win_rate'] for r in res['results']]),
            'n_periods': len(res['results']),
        })
    
    df = pd.DataFrame(rows)
    df = df.sort_values('mean_test_ic', ascending=False)
    return df


# ============================================================
# 报告
# ============================================================
def print_report(df: pd.DataFrame):
    """打印回测验证报告"""
    print("\n" + "=" * 90)
    print("  因子回测验证报告")
    print("=" * 90)
    
    print(f"\n📊 共验证 {len(df)} 个因子")
    print()
    
    # 表头
    print(f"  {'排名':>4} | {'因子名':>12} | {'训练IC':>8} | {'测试IC':>8} | {'IC衰减':>8} | {'收益':>8} | {'夏普':>6} | {'最大回撤':>8}")
    print("  " + "-" * 90)
    
    for i, row in df.iterrows():
        rank = df.index.get_loc(i) + 1
        print(f"  {rank:>4} | {row['factor_name']:>12} | "
              f"{row['mean_train_ic']:>+7.4f} | {row['mean_test_ic']:>+7.4f} | "
              f"{row['ic_decay']:>+7.4f} | {row['mean_return']*100:>6.2f}% | "
              f"{row['mean_sharpe']:>5.2f} | {row['max_drawdown']*100:>7.2f}%")
    
    print()
    
    # 结论
    top = df.iloc[0]
    print(f"  🏆 最佳因子: {top['factor_name']}")
    print(f"     表达式: {top['expression'][:70]}...")
    print(f"     测试IC: {top['mean_test_ic']:.4f} (IC衰减 {top['ic_decay']:.4f})")
    print(f"     平均收益: {top['mean_return']*100:.2f}%")
    print(f"     夏普比率: {top['mean_sharpe']:.2f}")
    print(f"     最大回撤: {top['max_drawdown']*100:.2f}%")
    
    # IC稳定性检验
    print(f"\n  📈 IC稳定性检验:")
    stable_factors = df[df['std_test_ic'] < 0.05]
    if len(stable_factors) > 0:
        print(f"     稳定因子 (IC std < 0.05): {len(stable_factors)} 个")
        for _, r in stable_factors.iterrows():
            print(f"       - {r['factor_name']}: IC={r['mean_test_ic']:.4f}, std={r['std_test_ic']:.4f}")
    else:
        print(f"     无稳定因子（所有因子IC波动较大）")
    
    print("\n" + "=" * 90)


# ============================================================
# 示范因子列表（来自RD-Agent常见挖掘结果类型）
# ============================================================
DEMO_FACTORS = [
    {'name': 'ret_5d',     'expression': 'Ref($close, 5) / $close - 1'},
    {'name': 'ret_20d',    'expression': 'Ref($close, 20) / $close - 1'},
    {'name': 'vol_ratio',  'expression': '$volume / Mean($volume, 20)'},
    {'name': 'ma5_c',      'expression': '$close / Mean($close, 5)'},
    {'name': 'ma20_c',     'expression': '$close / Mean($close, 20)'},
    {'name': 'ema_vol',    'expression': 'EMA($volume, 12) / Mean($volume, 20)'},
    {'name': 'high_low',   'expression': 'Max($high, 5) / Min($low, 5)'},
    {'name': 'close_pos',  'expression': '($close - Min($low, 20)) / (Max($high, 20) - Min($low, 20))'},
    {'name': 'vol_turn',   'expression': '$volume / Ref($volume, 10)'},
    {'name': 'price_mom',  'expression': 'EMA($close, 5) / EMA($close, 20)'},
]


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 90)
    print("  因子回测验证 — 对RD-Agent Top因子独立回测")
    print("=" * 90)
    
    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    raw_data, data_loaded = load_data()
    print(f"  数据量: {len(raw_data)} 条")
    
    # 2. 预处理
    print("\n[2/4] 预处理...")
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
    
    # 计算return_next_close（用于IC计算）
    processed = processed.sort_values(['ts_code', 'trade_date'])
    processed['return_next_close'] = processed.groupby('ts_code')['close'].pct_change(1).shift(-1)
    
    # 删除NaN
    processed = processed.dropna(subset=['return_next_close'])
    processed = processed.sort_values('trade_date').reset_index(drop=True)
    
    print(f"  有效样本: {len(processed)}")
    print(f"  日期范围: {processed['trade_date'].min()} ~ {processed['trade_date'].max()}")
    
    # 3. 批量回测
    print("\n[3/4] 批量回测...")
    all_results = batch_backtest(processed, DEMO_FACTORS, CONFIG)
    
    # 4. 汇总报告
    print("\n[4/4] 生成报告...")
    summary_df = summarize_results(all_results)
    print_report(summary_df)
    
    # 保存
    summary_df.to_csv('factor_backtest_results.csv', index=False)
    print(f"\n💾 结果已保存至 factor_backtest_results.csv")


if __name__ == '__main__':
    main()