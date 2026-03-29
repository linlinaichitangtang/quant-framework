#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于机器学习的A股超短线尾盘战法完整运行脚本
流程：数据获取 → 因子抽取 → 标签构造 → Optuna调参 → 滚动训练 → SHAP分析 → 回测
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ml_strategy.factor_extractor import FactorExtractor
from ml_strategy.label_constructor import LabelConstructor
from ml_strategy.ml_strategy import MLStockPicker, Backtester
from ml_strategy.trainer import RollingTrainer, OptunaOptimizer
from ml_strategy.shap_analyzer import SHAPAnalyzer
from ml_strategy.data_fetcher import TushareDataFetcher


def parse_args():
    parser = argparse.ArgumentParser(description='机器学习尾盘战法回测')
    parser.add_argument('--token', type=str, default=None, help='Tushare token')
    parser.add_argument('--start-date', type=str, default='20180101', help='训练数据开始日期')
    parser.add_argument('--backtest-start', type=str, default='20250101', help='回测开始日期')
    parser.add_argument('--backtest-end', type=str, default='20260315', help='回测结束日期')
    parser.add_argument('--initial-capital', type=float, default=1_000_000, help='初始资金')
    parser.add_argument('--commission', type=float, default=0.0003, help='佣金费率')
    parser.add_argument('--stamp-tax', type=float, default=0.001, help='印花税')
    parser.add_argument('--slippage', type=float, default=0.001, help='滑点')
    parser.add_argument('--max-position', type=float, default=0.2, help='单票最大仓位')
    parser.add_argument('--top-n', type=int, default=3, help='每日选股数量')
    parser.add_argument('--min-prob', type=float, default=0.5, help='最小上涨概率')
    parser.add_argument('--n-trials', type=int, default=50, help='Optuna调参次数')
    parser.add_argument('--model-type', type=str, default='gbm', choices=['gbm', 'rf'], help='模型类型')
    parser.add_argument('--output-dir', type=str, default='./output', help='输出目录')
    parser.add_argument('--cache-dir', type=str, default='./cache', help='数据缓存目录')
    return parser.parse_args()


def main():
    args = parse_args()
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)
    
    print("=" * 60)
    print("基于机器学习的超短线尾盘战法 - 回测开始")
    print("=" * 60)
    print(f"回测区间: {args.backtest_start} - {args.backtest_end}")
    print(f"初始资金: {args.initial_capital:,.0f}")
    print(f"佣金: {args.commission*10000:.0f}‰ 印花税: {args.stamp_tax*1000:.0f}‰ 滑点: {args.slippage*1000:.0f}‰")
    print(f"单票最大仓位: {args.max_position*100:.0f}% 每日选股: {args.top_n}只")
    print()
    
    # 1. 获取数据
    print("[Step 1] 获取股票数据...")
    fetcher = TushareDataFetcher(token=args.token)
    
    # 获取股票列表（目前选取部分股票作为示例，可扩展到全市场）
    stock_list = fetcher.get_stock_list()
    print(f"获取到 {len(stock_list)} 只股票")
    
    # 只保留主板+创业板，排除ST
    if 'name' in stock_list.columns:
        stock_list = stock_list[~stock_list['name'].str.contains('ST', na=False)]
    print(f"排除ST后剩余: {len(stock_list)} 只股票")
    
    # 取市值在50亿到500亿之间的股票作为样本（实际可以全市场）
    if 'circ_cap' in stock_list.columns:
        stock_list = stock_list[(stock_list['circ_cap'] >= 50) & (stock_list['circ_cap'] <= 500)]
        print(f"市值筛选后剩余: {len(stock_list)} 只股票")
    
    # 取前100只作为示例（避免数据获取过慢，实际可以全市场）
    sample_size = 100
    if len(stock_list) > sample_size:
        stock_list = stock_list.sample(sample_size, random_state=42)
    print(f"本次回测使用 {len(stock_list)} 只股票样本")
    
    # 获取所有股票日线数据
    ts_codes = stock_list['ts_code'].tolist() if 'ts_code' in stock_list.columns else stock_list['code'].tolist()
    daily_data = fetcher.get_all_stock_daily(
        ts_codes, 
        start_date=args.start_date, 
        end_date=args.backtest_end,
        cache_dir=args.cache_dir
    )
    print(f"成功获取 {len(daily_data)} 只股票数据")
    
    if len(daily_data) == 0:
        print("错误: 没有获取到任何数据，请检查tushare token和网络连接")
        return
    
    # 2. 合并所有数据用于训练
    print("\n[Step 2] 提取因子和构造标签...")
    fe = FactorExtractor()
    lc = LabelConstructor(threshold=0.02)
    
    all_data = []
    for code, df in daily_data.items():
        if len(df) < 60:  # 数据不足60天跳过
            continue
        # 提取因子
        df_factored, _ = fe.extract_all_factors(df)
        # 构造标签
        df_labeled = lc.construct_label_with_open(df_factored)
        all_data.append(df_labeled)
    
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df = combined_df.sort_values('trade_date').reset_index(drop=True)
    
    # 获取因子和标签
    factor_cols = [col for col in combined_df.columns if col not in 
                  ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
                   'volume', 'amount', 'turnover', 'y', 'y_close', 
                   'next_open', 'next_close', 'return_next_open', 
                   'return_next_close', 'return_next_max']]
    
    X = combined_df[factor_cols].values
    y = combined_df['y'].values
    
    # 删除NaN
    mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
    X = X[mask]
    y = y[mask]
    combined_df = combined_df[mask].reset_index(drop=True)
    
    print(f"总样本数: {len(X)}")
    print(f"正样本比例: {(y == 1).mean()*100:.2f}%")
    
    # 3. Optuna超参数优化
    print("\n[Step 3] Optuna超参数优化...")
    # 分割训练集 (只使用回测前的数据进行调参，避免未来函数)
    train_mask = combined_df['trade_date'] < args.backtest_start
    X_train = X[train_mask]
    y_train = y[train_mask]
    
    print(f"训练样本: {len(X_train)}")
    if len(X_train) == 0:
        print("错误: 训练集为空，请扩大训练区间")
        return
    
    optimizer = OptunaOptimizer(X_train, y_train, model_type=args.model_type, n_splits=5)
    best_params = optimizer.optimize(n_trials=args.n_trials)
    
    # 保存最佳参数
    pd.DataFrame([best_params]).to_csv(os.path.join(args.output_dir, 'best_params.csv'), index=False)
    
    # 4. 使用最佳参数训练最终模型
    print("\n[Step 4] 训练最终模型...")
    best_model = optimizer.train_best_model()
    best_model.save_model(os.path.join(args.output_dir, 'final_model.pkl'))
    
    # 输出特征重要性
    fi = best_model.get_feature_importance()
    if fi is not None:
        fi.to_csv(os.path.join(args.output_dir, 'feature_importance.csv'), index=False)
        print("\n前10个最重要特征:")
        print(fi.head(10))
    
    # 5. SHAP分析
    print("\n[Step 5] SHAP特征重要性分析...")
    # 取部分样本做SHAP分析
    if len(X_train) > 200:
        np.random.seed(42)
        shap_idx = np.random.choice(len(X_train), 200, replace=False)
        X_shap = X_train[shap_idx]
    else:
        X_shap = X_train
    
    analyzer = SHAPAnalyzer(best_model)
    analyzer.fit(X_shap, background_samples=min(100, len(X_shap)))
    
    # 保存各种SHAP图表
    analyzer.summary_plot(os.path.join(args.output_dir, 'shap_summary.png'))
    fi_shap = analyzer.feature_importance_plot(os.path.join(args.output_dir, 'shap_importance.png'))
    fi_shap.to_csv(os.path.join(args.output_dir, 'shap_feature_importance.csv'), index=False)
    
    print("\nSHAP特征重要性排序 (Top 10):")
    print(fi_shap.head(10))
    
    # 对最重要的特征画依赖图
    if not fi_shap.empty:
        top_feature = fi_shap.iloc[0]['feature']
        analyzer.dependence_plot(
            top_feature, 
            os.path.join(args.output_dir, f'shap_dependence_{top_feature}.png')
        )
    
    # 6. 滚动训练和回测
    print("\n[Step 6] 执行回测...")
    backtester = Backtester(
        initial_capital=args.initial_capital,
        commission=args.commission,
        stamp_tax=args.stamp_tax,
        slippage=args.slippage
    )
    
    # 获取回测区间所有交易日
    backtest_dates = combined_df[
        (combined_df['trade_date'] >= args.backtest_start) & 
        (combined_df['trade_date'] <= args.backtest_end)
    ]['trade_date'].sort_values().unique()
    
    print(f"回测交易日: {len(backtest_dates)}天")
    
    # 按交易日进行回测
    for date in sorted(backtest_dates):
        # 获取当日所有候选股票
        daily_candidates = combined_df[combined_df['trade_date'] == date].copy()
        
        if len(daily_candidates) == 0:
            continue
        
        # 模型预测
        X_day = daily_candidates[factor_cols].values
        probs = best_model.predict_proba(X_day)
        daily_candidates['up_probability'] = probs
        
        # 选股
        selected = daily_candidates[daily_candidates['up_probability'] >= args.min_prob].copy()
        selected = selected.sort_values('up_probability', ascending=False)
        if len(selected) > args.top_n:
            selected = selected.head(args.top_n)
        
        if len(selected) == 0:
            # 没有选中的股票，计算当日总资产（只有现金）
            backtester.calculate_daily_value(date, {})
            continue
        
        # 买入选中的股票，买入价为当日收盘价
        for _, row in selected.iterrows():
            backtester.buy(
                date=date,
                code=row['ts_code'] if 'ts_code' in row else row.get('code', 'unknown'),
                price=row['close'],
                max_position_pct=args.max_position
            )
        
        # 处理昨日持仓，次日卖出（尾盘买入，次日卖出）
        # 因为我们是提前一天选股，当日买入，次日卖出
        # 这里简化处理：每日尾盘买入，次日任何情况都卖出（符合策略）
        # 实际应该在检查止盈止损，但这里超短线策略是次日尾盘无论如何都卖
        
        # 获取当前持仓的次日收盘价卖出
        # 找到下一个交易日
        date_idx = np.where(backtest_dates == date)[0][0]
        if date_idx + 1 < len(backtest_dates):
            next_date = backtest_dates[date_idx + 1]
            
            # 获取持仓股票在next_date的收盘价
            price_map = {}
            for code in list(backtester.holdings.keys()):
                # 找到next_date该股票的收盘价
                next_day_data = daily_data[code]
                next_row = next_day_data[next_day_data['trade_date'] == str(next_date)]
                if len(next_row) > 0:
                    price_map[code] = next_row.iloc[0]['close']
            
            # 卖出所有持仓（严格不持仓过夜）
            backtester.sell_all_holdings(next_date, price_map)
        
        # 计算当日总资产
        current_prices = {}
        for code, holding in backtester.holdings.items():
            current_prices[code] = holding['price_bought']
        backtester.calculate_daily_value(date, current_prices)
    
    # 处理最后一天持仓，在下一个交易日卖出
    if len(backtester.holdings) > 0 and len(backtest_dates) > 0:
        last_date = backtest_dates[-1]
        price_map = {}
        for code in list(backtester.holdings.keys()):
            if code in daily_data:
                last_row = daily_data[code].iloc[-1]
                price_map[code] = last_row['close']
        backtester.sell_all_holdings(last_date, price_map)
    
    # 生成回测报告
    report = backtester.get_backtest_report()
    
    # 7. 保存回测结果
    print("\n[Step 7] 保存回测结果...")
    report['daily_df'].to_csv(os.path.join(args.output_dir, 'daily_equity.csv'), index=False)
    report['trades_df'].to_csv(os.path.join(args.output_dir, 'trades.csv'), index=False)
    
    # 保存报告文本
    with open(os.path.join(args.output_dir, 'backtest_report.txt'), 'w') as f:
        f.write("基于机器学习的超短线尾盘战法回测报告\n")
        f.write("=" * 60 + "\n")
        f.write(f"回测区间: {args.backtest_start} - {args.backtest_end}\n")
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
    plt.plot(pd.to_datetime(report['daily_df']['date']), report['daily_df']['total_value'])
    plt.title('资金曲线')
    plt.xlabel('日期')
    plt.ylabel('总资产')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, 'equity_curve.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # 绘制回撤曲线
    plt.figure(figsize=(12, 6))
    plt.fill_between(
        pd.to_datetime(report['daily_df']['date']), 
        0, 
        report['daily_df']['drawdown'] * 100,
        color='red', 
        alpha=0.3
    )
    plt.title('回撤')
    plt.xlabel('日期')
    plt.ylabel('回撤 (%)')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(args.output_dir, 'drawdown.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # 打印最终报告
    print("\n" + "=" * 60)
    print("回测完成！报告:")
    print("=" * 60)
    backtester.print_report(report)
    print()
    print(f"所有结果已保存至目录: {args.output_dir}")
    print("- backtest_report.txt: 回测报告文本")
    print("- daily_equity.csv: 每日权益曲线")
    print("- trades.csv: 所有交易记录")
    print("- equity_curve.png: 资金曲线图")
    print("- drawdown.png: 回撤图")
    print("- final_model.pkl: 训练好的模型")
    print("- feature_importance.csv: 模型特征重要性")
    print("- shap_summary.png: SHAP汇总图")
    print("- shap_importance.png: SHAP特征重要性图")
    print("- shap_feature_importance.csv: SHAP特征重要性数据")


if __name__ == '__main__':
    main()