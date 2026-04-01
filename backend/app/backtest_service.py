"""
回测服务层 — 封装 Backtester 调用，生成模拟数据并持久化到数据库
"""
import json
import logging
import random
from typing import Optional

import numpy as np
import pandas as pd

from . import crud

logger = logging.getLogger(__name__)


def _generate_mock_daily_values(
    initial_capital: float,
    n_days: int,
    annual_return: float = 0.15,
    annual_vol: float = 0.25,
    seed: Optional[int] = None,
) -> list:
    """生成模拟每日资产数据"""
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random.RandomState()

    daily_mu = annual_return / 252
    daily_sigma = annual_vol / np.sqrt(252)
    daily_returns = rng.normal(daily_mu, daily_sigma, n_days)

    values = [initial_capital]
    for r in daily_returns:
        values.append(values[-1] * (1 + r))

    result = []
    for i, v in enumerate(values):
        result.append({
            "date": f"2024-01-{(i + 1):02d}" if i < 31 else f"2024-{(i // 30 + 1):02d}-{(i % 30 + 1):02d}",
            "cash": round(v * 0.3, 2),
            "holdings_value": round(v * 0.7, 2),
            "total_value": round(v, 2),
            "daily_return": round(daily_returns[i - 1], 6) if i > 0 else 0,
            "drawdown": 0,
        })

    # 计算回撤
    cummax = values[0]
    for i, item in enumerate(result):
        if values[i] > cummax:
            cummax = values[i]
        dd = (values[i] - cummax) / cummax if cummax > 0 else 0
        item["drawdown"] = round(dd, 6)

    return result


def _generate_mock_trades(
    n_trades: int,
    codes: list,
    start_idx: int = 0,
    seed: Optional[int] = None,
) -> list:
    """生成模拟交易记录（成对的买入+卖出）"""
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random.RandomState()

    trades = []
    for i in range(n_trades):
        code = rng.choice(codes)
        buy_price = round(rng.uniform(10, 100), 2)
        shares = rng.choice([100, 200, 300, 400, 500])
        commission = round(shares * buy_price * 0.0003, 2)

        day = start_idx + i * rng.randint(1, 4)
        buy_date = f"2024-{(day // 30 + 1):02d}-{(day % 30 + 1):02d}"

        trades.append({
            "date": buy_date,
            "action": "buy",
            "code": code,
            "price": buy_price,
            "shares": shares,
            "cost": round(shares * buy_price + commission, 2),
            "commission": commission,
        })

        # 卖出
        price_change = rng.normal(0.01, 0.03)
        sell_price = round(buy_price * (1 + price_change), 2)
        sell_commission = round(shares * sell_price * 0.0003, 2)
        stamp_tax = round(shares * sell_price * 0.001, 2)
        proceeds = round(shares * sell_price - sell_commission - stamp_tax, 2)
        cost_basis = shares * buy_price + commission
        pnl = round(proceeds - cost_basis, 2)
        pnl_pct = round(pnl / cost_basis, 6) if cost_basis > 0 else 0

        sell_day = day + rng.randint(1, 3)
        sell_date = f"2024-{(sell_day // 30 + 1):02d}-{(sell_day % 30 + 1):02d}"

        trades.append({
            "date": sell_date,
            "action": "sell",
            "code": code,
            "price": sell_price,
            "shares": shares,
            "proceeds": proceeds,
            "commission": sell_commission,
            "stamp_tax": stamp_tax,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })

    # 按日期排序
    trades.sort(key=lambda x: x["date"])
    return trades


def _generate_mock_feature_importance(n_features: int = 10, seed: Optional[int] = None) -> list:
    """生成模拟特征重要性"""
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random.RandomState()

    features = [
        "return_5d", "ma5_slope", "volume_ratio_5d", "rsi_14",
        "amplitude", "close_over_ma20", "momentum_10d",
        "turnover_rate", "volatility_20d", "price_volume_corr_5d",
        "ma_bullish", "dist_to_5d_high", "log_cap",
        "k_norm", "j_norm", "skewness_10d",
    ]
    importance = rng.dirichlet(np.ones(min(n_features, len(features))))
    result = []
    for i in range(min(n_features, len(features))):
        result.append({
            "feature": features[i],
            "importance": round(float(importance[i]), 4),
        })
    result.sort(key=lambda x: x["importance"], reverse=True)
    return result


def run_backtest(db, config) -> dict:
    """
    执行回测并保存结果到数据库。

    使用模拟数据生成回测结果（真实场景可替换为调用 Backtester）。

    :param db: SQLAlchemy Session
    :param config: BacktestConfig schema
    :return: 创建的 BacktestResult ORM 对象
    """
    seed = hash(config.name) % 100000

    # 1. 创建回测记录（状态 running）
    result = crud.create_backtest_result(
        db,
        name=config.name,
        strategy_type=config.strategy_type,
        market=config.market,
        status="running",
        initial_capital=config.initial_capital,
        commission=config.commission,
        stamp_tax=config.stamp_tax,
        slippage=config.slippage,
        start_date=config.start_date,
        end_date=config.end_date,
        params=json.dumps({
            "top_n": config.top_n,
            "min_prob": config.min_prob,
            "max_position_pct": config.max_position_pct,
            "model_type": config.model_type,
            "n_trials": config.n_trials,
        }),
    )

    try:
        # 2. 生成模拟回测数据
        n_days = 120  # 模拟120个交易日
        daily_values = _generate_mock_daily_values(
            initial_capital=config.initial_capital,
            n_days=n_days,
            seed=seed,
        )

        final_value = daily_values[-1]["total_value"]
        total_return = (final_value - config.initial_capital) / config.initial_capital
        annual_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0

        # 最大回撤
        max_dd = min(d["drawdown"] for d in daily_values)

        # 夏普比率
        returns = [d["daily_return"] for d in daily_values if d["daily_return"] != 0]
        sharpe = 0
        if returns and np.std(returns) > 0:
            sharpe = float(np.sqrt(252) * np.mean(returns) / np.std(returns))

        # 模拟交易
        mock_codes = ["600519.SH", "000858.SZ", "601318.SH", "000333.SZ",
                       "600036.SH", "002415.SZ", "300750.SZ", "601888.SH"]
        n_trades = random.Random(seed).randint(15, 40)
        trades = _generate_mock_trades(n_trades, mock_codes, seed=seed)

        # 交易统计
        sells = [t for t in trades if t["action"] == "sell"]
        n_sell = len(sells)
        wins = [t for t in sells if t.get("pnl", 0) > 0]
        win_rate = len(wins) / n_sell if n_sell > 0 else 0
        avg_pnl = np.mean([t["pnl"] for t in sells]) if sells else 0
        avg_pnl_pct = np.mean([t["pnl_pct"] for t in sells]) if sells else 0

        # 盈亏比
        profit_trades = [t["pnl"] for t in sells if t["pnl"] > 0]
        loss_trades = [-t["pnl"] for t in sells if t["pnl"] <= 0]
        if profit_trades and loss_trades:
            pl_ratio = np.mean(profit_trades) / np.mean(loss_trades)
        else:
            pl_ratio = float("inf") if profit_trades else 0

        # 特征重要性
        feature_importance = _generate_mock_feature_importance(seed=seed)

        # 3. 更新回测结果
        result = crud.update_backtest_result(
            db, result.id,
            status="completed",
            final_value=round(final_value, 2),
            total_return=round(total_return, 6),
            annual_return=round(annual_return, 6),
            max_drawdown=round(max_dd, 6),
            sharpe_ratio=round(sharpe, 4),
            n_trades=n_sell,
            win_rate=round(win_rate, 4),
            avg_pnl=round(float(avg_pnl), 2),
            avg_pnl_pct=round(float(avg_pnl_pct), 4),
            profit_loss_ratio=round(float(pl_ratio), 4),
            daily_values=json.dumps(daily_values, ensure_ascii=False),
            feature_importance=json.dumps(feature_importance, ensure_ascii=False),
        )

        # 4. 保存交易明细
        crud.create_backtest_trades(db, result.id, trades)

        logger.info(f"回测完成: {config.name}, 收益率={total_return*100:.2f}%, 夏普={sharpe:.2f}")
        return result

    except Exception as e:
        logger.error(f"回测失败: {config.name}, 错误: {e}")
        crud.update_backtest_result(db, result.id, status="failed")
        raise
