#!/usr/bin/env python3
"""
因子正交化模块 — 构建独立因子组合

两种方案：
1. 施密特正交化 (Gram-Schmidt)：保持因子可解释性
2. PCA降维：最大化方差保留，真正去相关

目标：去除冗余因子，使各因子间相关系数接近0
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Tuple

warnings.filterwarnings('ignore')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))

from data.qlib_adapter import QlibExpressionParser


# ============================================================
# 数据
# ============================================================
def generate_mock_data(n_stocks=50, n_days=252, seed=42):
    np.random.seed(seed)
    dates = pd.bdate_range(start='2022-01-01', periods=n_days)
    
    all_data = []
    for i in range(n_stocks):
        code = f"{600000 + i:06d}.SH" if i < 25 else f"{1 + i - 25:06d}.SZ"
        base_price = np.random.uniform(10, 100)
        vol = np.random.uniform(0.015, 0.035)
        drift = np.random.uniform(-0.0001, 0.0002)
        
        prices = [base_price]
        for d in range(1, n_days):
            ret = drift + vol * np.random.randn()
            prices.append(prices[-1] * (1 + ret))
        prices = np.array(prices)
        
        for d, date in enumerate(dates):
            close = prices[d]
            high = close * (1 + abs(np.random.normal(0, 0.01)))
            low = close * (1 - abs(np.random.normal(0, 0.01)))
            open_p = close * (1 + np.random.normal(0, 0.005))
            volume = int(np.random.lognormal(15, 1))
            
            all_data.append({
                'ts_code': code,
                'trade_date': date.strftime('%Y%m%d'),
                'open': round(open_p, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume,
            })
    
    return pd.DataFrame(all_data).sort_values(['ts_code', 'trade_date']).reset_index(drop=True)


# ============================================================
# 因子计算
# ============================================================
def compute_factors(df: pd.DataFrame, expressions: List[Dict]) -> pd.DataFrame:
    """按单只股票时间序列计算因子"""
    all_results = []
    
    for code, stock_df in df.groupby('ts_code'):
        stock_df = stock_df.sort_values('trade_date').copy()
        
        rename = {}
        for c in stock_df.columns:
            if c.lower() in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                rename[c] = f'${c.lower()}'
        if rename:
            stock_df = stock_df.rename(columns=rename)
        
        parser = QlibExpressionParser(stock_df)
        
        for expr_info in expressions:
            name = expr_info['name']
            expr = expr_info['expression']
            try:
                vals = parser.evaluate(expr)
                if len(vals) == len(stock_df):
                    stock_df[name] = vals
                else:
                    stock_df[name] = np.nan
            except Exception:
                stock_df[name] = np.nan
        
        all_results.append(stock_df)
    
    return pd.concat(all_results, ignore_index=True)


# ============================================================
# PCA正交化
# ============================================================
def pca_orthogonalize(factor_panel: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    PCA正交化 — 对因子面板进行主成分分析
    
    Args:
        factor_panel: 宽格式因子面板 (index=trade_date, columns=ts_code, values=factor)
    
    Returns:
        pca_df: 主成分时序 (每天一个主成分向量)
        explained: 各主成分的方差解释比例
    """
    # 截面标准化后做PCA
    scaler = StandardScaler()
    scaled = scaler.fit_transform(factor_panel.fillna(0))
    
    pca = PCA()
    pca_factors = pca.fit_transform(scaled)
    
    explained = {}
    for i, (var_ratio, cum) in enumerate(zip(
        pca.explained_variance_ratio_,
        np.cumsum(pca.explained_variance_ratio_)
    )):
        explained[f'PC{i+1}'] = {'variance_ratio': var_ratio, 'cumulative': cum}
    
    pca_df = pd.DataFrame(pca_factors, index=factor_panel.index,
                         columns=[f'PC{i+1}' for i in range(pca_factors.shape[1])])
    return pca_df, explained


# ============================================================
# 相关性分析
# ============================================================
def correlation_report(factors_df: pd.DataFrame, title: str):
    """打印相关性矩阵"""
    corr = factors_df.corr()
    
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"\n相关系数矩阵：")
    print(corr.round(4).to_string())
    
    high_corr = []
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            if abs(corr.iloc[i, j]) > 0.5:
                high_corr.append({'f1': corr.columns[i], 'f2': corr.columns[j],
                                 'r': corr.iloc[i, j]})
    
    if high_corr:
        print(f"\n⚠️ 高相关因子对 (|r| > 0.5):")
        for h in sorted(high_corr, key=lambda x: -abs(x['r'])):
            print(f"   {h['f1']:20s} <-> {h['f2']:20s}: {h['r']:+.4f}")
    else:
        print(f"\n✅ 无高相关因子对 (|r| 均 < 0.5)")
    
    return corr


# ============================================================
# 主流程
# ============================================================
FACTORS = [
    {'name': 'ret_5d',    'expression': 'Ref($close, 5) / $close - 1'},
    {'name': 'ret_20d',   'expression': 'Ref($close, 20) / $close - 1'},
    {'name': 'vol_r',     'expression': '$volume / Mean($volume, 20)'},
    {'name': 'ma5_c',     'expression': '$close / Mean($close, 5)'},
    {'name': 'ma20_c',    'expression': '$close / Mean($close, 20)'},
    {'name': 'ema_vol',   'expression': 'EMA($volume, 12) / Mean($volume, 20)'},
    {'name': 'high_low',  'expression': 'Max($high, 5) / Min($low, 5)'},
    {'name': 'vol_turn',  'expression': '$volume / Ref($volume, 10)'},
]


def main():
    print("=" * 70)
    print("  因子正交化 — PCA 主成分分析")
    print("=" * 70)
    
    # 1. 生成数据
    print("\n[1/5] 生成模拟数据...")
    raw = generate_mock_data(n_stocks=50, n_days=252)
    print(f"  {len(raw)} 条, {raw['ts_code'].nunique()} 只股票")
    
    # 2. 计算因子
    print("\n[2/5] 计算因子...")
    factored = compute_factors(raw, FACTORS)
    
    # 3. 构建每只股票的因子面板（截面z-score后PCA）
    print("\n[3/5] 构建因子面板 → PCA正交化...")
    
    # 对每个日期截面做z-score，然后展平为面板
    all_panels = []
    for date, day_df in factored.groupby('trade_date'):
        day_df = day_df.copy()
        rename = {}
        for c in day_df.columns:
            if c.lower() in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                rename[c] = f'${c.lower()}'
        if rename:
            day_df = day_df.rename(columns=rename)
        
        # 截面z-score（横截面标准化）
        factor_cols = [f['name'] for f in FACTORS]
        existing_cols = [c for c in factor_cols if c in day_df.columns]
        if existing_cols:
            vals = day_df[existing_cols].values
            means = np.nanmean(vals, axis=0, keepdims=True)
            stds = np.nanstd(vals, axis=0, keepdims=True)
            stds[stds < 1e-10] = 1
            zscored = (vals - means) / stds
            panel = pd.DataFrame(zscored, columns=existing_cols)
            panel['trade_date'] = date
            panel['ts_code'] = day_df['ts_code'].values
            all_panels.append(panel)
    
    panel_df = pd.concat(all_panels, ignore_index=True)
    print(f"  面板形状: {panel_df.shape}")
    
    # 4. 对每只股票做PCA（时间序列维度）
    print("\n[4/5] 对各因子执行PCA...")
    
    # 构建每因子面板
    factor_panels = {}
    for fname in [f['name'] for f in FACTORS]:
        if fname in panel_df.columns:
            wide = panel_df.pivot_table(index='trade_date', columns='ts_code', values=fname)
            factor_panels[fname] = wide
    
    # 合并为面板矩阵 (T × N*F)
    panel_list = []
    for fname, wide in factor_panels.items():
        panel_list.append(wide)
    
    combined_panel = pd.concat(panel_list, axis=1)  # (T, N_stocks * N_factors)
    combined_panel = combined_panel.dropna()
    print(f"  组合面板: {combined_panel.shape}")
    
    # PCA on combined panel
    scaler = StandardScaler()
    scaled_panel = scaler.fit_transform(combined_panel.fillna(0))
    
    pca = PCA()
    pca_scores = pca.fit_transform(scaled_panel)
    
    explained = {}
    for i, (var_ratio, cum) in enumerate(zip(
        pca.explained_variance_ratio_,
        np.cumsum(pca.explained_variance_ratio_)
    )):
        explained[f'PC{i+1}'] = {'variance_ratio': var_ratio, 'cumulative': cum}
    
    pca_df = pd.DataFrame(pca_scores, index=combined_panel.index,
                         columns=[f'PC{i+1}' for i in range(pca_scores.shape[1])])
    
    # 只保留累计>90%的主成分
    n_keep = sum(1 for info in explained.values() if info['cumulative'] <= 0.90) + 1
    
    print(f"\n  主成分方差解释：")
    for pc, info in list(explained.items())[:12]:
        bar = '█' * int(info['variance_ratio'] * 100) + '░' * (100 - int(info['variance_ratio'] * 100))
        keep_marker = ' ◄保留' if pc in [f'PC{i+1}' for i in range(n_keep)] else ''
        print(f"    [{bar[:50]:50s}] {pc:5s} {info['variance_ratio']*100:5.2f}% (累计 {info['cumulative']*100:5.1f}%){keep_marker}")
    
    # PCA验证：主成分之间应该完全不相关
    corr_pca = pca_df[[f'PC{i+1}' for i in range(min(8, pca_df.shape[1]))]].corr()
    off_diag = corr_pca.values[np.triu_indices_from(corr_pca.values, k=1)]
    print(f"\n  ✅ PCA主成分非对角相关系数: max={max(abs(off_diag)):.2e}, mean={np.mean(np.abs(off_diag)):.2e}")
    
    # 原始因子相关性（用每天截面相关系数的均值代表）
    print(f"\n[5/5] 原始因子截面相关性...")
    
    # 计算每天的截面相关系数，然后平均
    daily_corrs = {fname: [] for fname in [f['name'] for f in FACTORS]}
    factor_names = [f['name'] for f in FACTORS if f['name'] in panel_df.columns]
    
    for date, day_df in panel_df.groupby('trade_date'):
        if len(day_df) >= 3:
            vals = day_df[factor_names].values
            if not np.any(np.isnan(vals)):
                c = np.corrcoef(vals.T)
                for fi, fn in enumerate(factor_names):
                    for fj, fn2 in enumerate(factor_names):
                        if fi < fj and not np.isnan(c[fi, fj]):
                            daily_corrs[fn].append({'pair': (fn, fn2), 'r': c[fi, fj]})
    
    # 平均相关性
    mean_corrs = {}
    for fname in factor_names:
        pairs = {}
        for item in daily_corrs[fname]:
            pair = item['pair']
            r = item['r']
            key = tuple(sorted([pair[0], pair[1]]))
            if key not in pairs:
                pairs[key] = []
            pairs[key].append(r)
        mean_corrs[fname] = {k: np.mean(v) for k, v in pairs.items()}
    
    # 汇总所有因子对
    all_pairs = {}
    for fname, pairs in mean_corrs.items():
        for (f1, f2), r in pairs.items():
            key = tuple(sorted([f1, f2]))
            if key not in all_pairs:
                all_pairs[key] = []
            all_pairs[key].append(abs(r))
    
    mean_corr_series = pd.Series({k: np.mean(v) for k, v in all_pairs.items()})
    print(f"\n  原始因子对平均相关系数（绝对值）：")
    for (f1, f2), r in mean_corr_series.sort_values(ascending=False).items():
        bar = '█' * int(r * 20)
        print(f"    {f1:12s} <-> {f2:12s}: {r:+.4f} {bar}")
    
    avg_before = mean_corr_series.mean()
    avg_after_pca = np.mean(np.abs(off_diag))
    
    print(f"\n" + "=" * 70)
    print("  正交化效果对比")
    print("=" * 70)
    print(f"\n  平均绝对相关系数:")
    print(f"    原始因子:    {avg_before:.4f}")
    print(f"    PCA主成分:   {avg_after_pca:.4f} (↓ {max(0,(avg_before-avg_after_pca)/avg_before*100):.0f}%)")
    
    print(f"\n  结论：")
    print(f"""    PCA对原始因子面板进行正交变换，产生完全不相关的主成分。
    各主成分保留了原始因子群的信息（累计方差解释），但两两正交。
    实际量化用法：用前N个主成分（累计方差>80~90%）替代原始因子，
    可大幅降低共线性，同时保留大部分预测能力。""")
    
    # 保存
    pca_df[[f'PC{i+1}' for i in range(n_keep)]].to_csv('pca_orthogonalized_factors.csv')
    combined_panel.to_csv('raw_factor_panel.csv')
    
    print(f"\n💾 结果已保存:")
    print(f"   - pca_orthogonalized_factors.csv (PCA主成分时序)")
    print(f"   - raw_factor_panel.csv (原始因子面板)")


if __name__ == '__main__':
    main()