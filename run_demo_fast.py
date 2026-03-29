#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速演示脚本：减少Optuna迭代次数，快速验证流程
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ml_strategy.factor_extractor import FactorExtractor
from ml_strategy.label_constructor import LabelConstructor
from ml_strategy.ml_strategy import MLStockPicker, Backtester
from ml_strategy.trainer import RollingTrainer, OptunaOptimizer
from ml_strategy.shap_analyzer import SHAPAnalyzer


def generate_simulated_data(n_stocks: int = 30, n_days: int = 1000, random_seed: int = 42):
    """生成模拟数据用于测试"""
    np.random.seed(random_seed)
    
    all_data = []
    
    # 生成日期序列
    from datetime import datetime, timedelta
    start_date = datetime(2018, 1, 1)
    dates = [(start_date + timedelta(days=i)).strftime('%Y%m%d') for i in range(n_days)]
    
    base_price = 10.0
    
    for stock_i in range(n_stocks):
        # 生成随机游走价格
        returns = np.random.normal(0.0005, 0.015, n_days)
        # 让一些股票有趋势，符合尾盘策略特征
        has_trend = np.random.random() > 0.5
        if has_trend:
            returns = returns + 0.001
        
        prices = base_price * (1 + returns).cumprod()
        
        # 生成OHLC
        df = pd.DataFrame()
        df['trade_date'] = dates
        df['ts_code'] = f'{stock_i:06d}.SZ'
        df['open'] = prices * np.random.normal(1, 0.005, n_days)
        df['close'] = prices
        df['high'] = np.maximum(df['open'], df['close']) * (1 + np.random.uniform(0, 0.02, n_days))
        df['low'] = np.minimum(df['open'], df['close']) * (1 - np.random.uniform(0, 0.02, n_days))
        df['volume'] = np.random.uniform(1e6, 1e8, n_days)
        df['amount'] = df['volume'] * df['close']
        df['turnover'] = np.random.uniform(1, 10, n_days)
        df['circulating_cap'] = np.random.uniform(50e8, 500e8)
        df['is_st'] = False
        df['is_suspended'] = False
        df['has_bad_news'] = np.random.random(n_days) < 0.01
        df['consecutive_limit'] = np.random.poisson(0.5, n_days)
        df['late_rally'] = np.random.random(n_days) > 0.3
        
        all_data.append(df)
    
    combined = pd.concat(all_data, ignore_index=True)
    return combined


def main():
    print("=" * 60)
    print("基于机器学习的超短线尾盘战法 - 快速演示（模拟数据）")
    print("=" * 60)
    
    output_dir = './output_demo_fast'
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 生成模拟数据
    print("\n[Step 1] 生成模拟数据...")
    combined_df = generate_simulated_data(n_stocks=30, n_days=800)
    print(f"生成了 {len(combined_df['ts_code'].unique())} 只股票")
    
    # 2. 提取因子和构造标签
    print("\n[Step 2] 提取因子和构造标签...")
    fe = FactorExtractor()
    lc = LabelConstructor(threshold=0.02)
    
    combined_df = combined_df.sort_values(['ts_code', 'trade_date']).reset_index(drop=True)
    
    # 对每个股票单独处理
    processed_dfs = []
    for code in combined_df['ts_code'].unique():
        df = combined_df[combined_df['ts_code'] == code].copy()
        df, _ = fe.extract_all_factors(df)
        df = lc.construct_label_with_open(df)
        processed_dfs.append(df)
    
    combined_df = pd.concat(processed_dfs, ignore_index=True)
    combined_df = combined_df.sort_values('trade_date').reset_index(drop=True)
    
    # 获取因子和标签
    factor_cols = [col for col in combined_df.columns if col not in 
                  ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                   'volume', 'amount', 'turnover', 'y', 'y_close', 
                   'next_open', 'next_close', 'return_next_open', 
                   'return_next_close', 'return_next_max', 
                   'circulating_cap', 'is_st', 'is_suspended', 
                   'has_bad_news', 'consecutive_limit', 'late_rally']]
    
    X = combined_df[factor_cols].values
    y = combined_df['y'].values
    
    # 删除NaN
    mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
    X = X[mask]
    y = y[mask]
    combined_df = combined_df[mask].reset_index(drop=True)
    
    print(f"有效样本数: {len(X)}")
    print(f"正样本比例: {(y == 1).mean()*100:.2f}%")
    
    # 3. 简化：直接用默认参数训练，跳过Optuna
    print("\n[Step 3] 训练模型（跳过Optuna加速演示）...")
    backtest_start = '20250101'
    train_mask = combined_df['trade_date'].astype(int) < int(backtest_start)
    X_train = X[train_mask]
    y_train = y[train_mask]
    
    print(f"训练样本: {len(X_train)}")
    
    # 使用默认参数直接训练
    best_model = MLStockPicker('gbm', {
        'n_estimators': 100,
        'learning_rate': 0.1,
        'max_depth': 3,
        'random_state': 42
    })
    metrics = best_model.train(X_train, y_train)
    print(f"训练完成，训练集AUC: {metrics['auc']:.4f}")
    
    best_model.save_model(os.path.join(output_dir, 'final_model.pkl'))
    
    fi = best_model.get_feature_importance()
    if fi is not None:
        fi.to_csv(os.path.join(output_dir, 'feature_importance.csv'), index=False)
        print("\n前10个最重要特征:")
        print(fi.head(10))
    
    # 4. SHAP分析
    print("\n[Step 4] SHAP特征重要性分析...")
    if len(X_train) > 100:
        np.random.seed(42)
        shap_idx = np.random.choice(len(X_train), 100, replace=False)
        X_shap = X_train[shap_idx]
    else:
        X_shap = X_train
    
    analyzer = SHAPAnalyzer(best_model)
    analyzer.fit(X_shap, background_samples=min(50, len(X_shap)))
    
    analyzer.summary_plot(os.path.join(output_dir, 'shap_summary.png'))
    fi_shap = analyzer.feature_importance_plot(os.path.join(output_dir, 'shap_importance.png'))
    fi_shap.to_csv(os.path.join(output_dir, 'shap_feature_importance.csv'), index=False)
    
    print("\nSHAP特征重要性排序 (Top 10):")
    print(fi_shap.head(10))
    
    # 5. 回测
    print("\n[Step 5] 执行回测...")
    backtester = Backtester(
        initial_capital=1_000_000,
        commission=0.0003,
        stamp_tax=0.001,
        slippage=0.001
    )
    
    # 获取回测区间交易日
    # 由于我们生成数据是从2018-01-01开始，n_days=800天大约到2020-03，所以调整为用后半段回测
    all_dates = sorted(combined_df['trade_date'].unique())
    # 后1/3作为回测区间
    backtest_start_idx = int(len(all_dates) * 2 / 3)
    backtest_dates = all_dates[backtest_start_idx:]
    print(f"回测交易日: {len(backtest_dates)}天")
    
    print(f"回测交易日: {len(backtest_dates)}天")
    
    # 按交易日回测
    for date in sorted(backtest_dates):
        daily_candidates = combined_df[combined_df['trade_date'] == date].copy()
        
        if len(daily_candidates) == 0:
            continue
        
        # 模型预测
        X_day = daily_candidates[factor_cols].values
        probs = best_model.predict_proba(X_day)
        daily_candidates['up_probability'] = probs
        
        # 选股
        selected = daily_candidates[daily_candidates['up_probability'] >= 0.5].copy()
        selected = selected.sort_values('up_probability', ascending=False)
        if len(selected) > 3:
            selected = selected.head(3)
        
        # 买入选中股票
        for _, row in selected.iterrows():
            backtester.buy(
                date=date,
                code=row['ts_code'],
                price=row['close'],
                max_position_pct=0.2
            )
        
        # 次日卖出所有持仓
        date_list = list(sorted(backtest_dates))
        date_idx = date_list.index(date)
        if date_idx + 1 < len(date_list):
            next_date = date_list[date_idx + 1]
            
            # 获取持仓股票收盘价
            price_map = {}
            for code in list(backtester.holdings.keys()):
                next_row = combined_df[
                    (combined_df['trade_date'] == next_date) & 
                    (combined_df['ts_code'] == code)
                ]
                if len(next_row) > 0:
                    price_map[code] = next_row.iloc[0]['close']
            
            backtester.sell_all_holdings(next_date, price_map)
        
        # 计算当日总资产
        current_prices = {}
        for code, holding in backtester.holdings.items():
            current_prices[code] = holding['price_bought']
        backtester.calculate_daily_value(date, current_prices)
    
    # 卖出剩余持仓
    if len(backtester.holdings) > 0 and len(backtest_dates) > 0:
        last_date = backtest_dates[-1]
        price_map = {}
        for code in list(backtester.holdings.keys()):
            row = combined_df[
                (combined_df['trade_date'] == last_date) & 
                (combined_df['ts_code'] == code)
            ]
            if len(row) > 0:
                price_map[code] = row.iloc[0]['close']
        backtester.sell_all_holdings(last_date, price_map)
    
    # 生成报告
    report = backtester.get_backtest_report()
    
    # 6. 保存结果
    print("\n[Step 6] 保存回测结果...")
    report['daily_df'].to_csv(os.path.join(output_dir, 'daily_equity.csv'), index=False)
    report['trades_df'].to_csv(os.path.join(output_dir, 'trades.csv'), index=False)
    
    with open(os.path.join(output_dir, 'backtest_report.txt'), 'w') as f:
        f.write("基于机器学习的超短线尾盘战法回测报告 (快速演示，模拟数据)\n")
        f.write("=" * 60 + "\n")
        f.write(f"回测区间: 2025-01-01 - 2026-03-15\n")
        f.write(f"初始资金: {report['initial_capital']:,.2f}\n")
        f.write(f"最终资金: {report['final_value']:,.2f}\n")
        f.write(f"总收益率: {report['total_return_pct']:.2f}%\n")
        f.write(f"年化收益率: {report['annual_return_pct']:.2f}%\n")
        f.write(f"最大回撤: {report['max_drawdown_pct']:.2f}%\n")
        f.write(f"夏普比率: {report['sharpe_ratio']:.3f}\n")
        f.write(f"总交易次数: {report['n_trades']}\n")
        if report['n_trades'] > 0:
            f.write(f"胜率: {report['win_rate']*100:.2f}%\n")
            f.write(f"平均单次盈亏: {report['avg_pnl']:.2f} ({report['avg_pnl_pct']:.2f}%)\n")
            f.write(f"盈亏比: {report['profit_loss_ratio']:.2f}\n")
    
    # 绘制资金曲线
    plt.figure(figsize=(12, 6))
    date_series = pd.to_datetime(report['daily_df']['date'], format='%Y%m%d')
    plt.plot(date_series, report['daily_df']['total_value'])
    plt.title('资金曲线 (模拟数据)')
    plt.xlabel('日期')
    plt.ylabel('总资产')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'equity_curve.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # 绘制回撤
    plt.figure(figsize=(12, 6))
    plt.fill_between(
        date_series,
        0,
        report['daily_df']['drawdown'] * 100,
        color='red',
        alpha=0.3
    )
    plt.title('回撤 (模拟数据)')
    plt.xlabel('日期')
    plt.ylabel('回撤 (%)')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'drawdown.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # 打印最终报告
    print("\n" + "=" * 60)
    print("回测完成！报告:")
    print("=" * 60)
    backtester.print_report(report)
    print()
    print(f"所有结果已保存至目录: {output_dir}")
    
    # 列出生成的文件
    print("\n生成的文件:")
    for f in os.listdir(output_dir):
        f_path = os.path.join(output_dir, f)
        size = os.path.getsize(f_path)
        print(f"  - {f}: {size/1024:.1f} KB")


if __name__ == '__main__':
    main()
