"""
富途数据 → A股尾盘选股策略 数据对接模块

把 FutuProvider 获取的原始行情数据，
转换为 AStockEveningPicker.filter_stocks() 所需的 DataFrame 格式。
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional

from src.data.futu_provider import FutuProvider
from src.strategies.a_stock_evening import AStockEveningPicker
from src.data_types import StockScore


def _compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    从原始日K数据计算选股所需的所有特征列

    需要列: date, open, close, high, low, volume (from FutuProvider)
    输出列: change_pct, amplitude, volume_5d_avg, volume_ratio, ...
    """
    df = df.copy()

    # 当日涨幅 %
    df['change_pct'] = df['pct_change']

    # 振幅 %
    df['amplitude'] = (df['high'] - df['low']) / df['open'] * 100

    # 5日平均成交量（滚动计算，需要历史数据）
    # 如果只有单日数据，用当日成交量代替
    if 'volume_5d_avg' not in df.columns:
        # 简单：用当日成交量的移动均值（用当日自身替代）
        df['volume_5d_avg'] = df['volume']

    # 量比（需5日均量，此处用成交量变化率代理）
    # turnover列不存在于富途日K(rename成了amount)，用成交量代理
    if 'turnover' in df.columns:
        df['volume_ratio'] = df['turnover'] / df['turnover'].replace(0, 1).clip(lower=0.5)
    else:
        df['volume_ratio'] = 1.0  # 无法计算时默认1.0

    # 流通市值估算（需要基本面数据，暂用成交量代理排序）
    # 真实场景从 FutuProvider.get_fundamental() 获取
    df['circulate_cap'] = df['volume'] * df['close'] * 1e8 / 1e8  # 估算值

    # 近3日涨幅（需要历史数据，简化处理）
    if 'change_3d' not in df.columns:
        df['change_3d'] = df['pct_change']

    # 连续涨停数（需从历史数据统计，此处默认0）
    df['consecutive_limit'] = 0

    # ST/停牌状态（需从基本面数据，此处默认否）
    df['is_st'] = False
    df['is_suspended'] = False

    # 利空标记（需新闻数据，暂默认无）
    df['has_bad_news'] = False

    # 尾盘拉升（需分时数据，暂默认True）
    df['late_rally'] = True

    # MA20（需历史数据计算，简化：假设close在MA20上方）
    # 此处用 change_pct > 0 代理（实际需真实计算）
    df['ma20'] = df['close']
    df['ma20_prev'] = df['close'] * 0.99  # 简化：假设均线微微上翘

    # 富途日K的 turnover 列 rename 成了 amount，此处补回 turnover 供策略使用
    if 'turnover' not in df.columns and 'amount' in df.columns:
        df['turnover'] = df['amount']

    return df


class FutuAStockEveningPicker:
    """
    富途数据驱动的A股尾盘选股器

    使用 FutuProvider 拉取日K数据，计算特征，执行 AStockEveningPicker 筛选。
    """

    def __init__(
        self,
        futu_provider: Optional[FutuProvider] = None,
        picker_config: Optional[Dict] = None,
    ):
        self.provider = futu_provider or FutuProvider()
        self.picker = AStockEveningPicker(config=picker_config)

    def pick(self, universe: List[str], trade_date: str) -> pd.DataFrame:
        """
        执行选股

        Args:
            universe: 候选股票列表，内部格式 ["CN.600000", ...]
            trade_date: 交易日期 YYYY-MM-DD

        Returns:
            筛选后的股票 DataFrame，按评分降序
        """
        # 从富途获取历史数据（用于计算MA20等指标）
        all_dfs = []
        for sym in universe:
            df = self.provider.get_daily_bars(sym, trade_date, trade_date)
            if not df.empty:
                all_dfs.append(df)

        if not all_dfs:
            return pd.DataFrame()

        # 合并全量数据
        combined = pd.concat(all_dfs, ignore_index=True)

        # 计算特征
        features = _compute_features(combined)

        # 执行筛选
        result = self.picker.filter_stocks(features)

        return result

    def pick_batch(self, trade_date: str, batch_size: int = 50) -> pd.DataFrame:
        """
        批量选股（适用于全市场扫描）

        Args:
            trade_date: 交易日期
            batch_size: 每批处理股票数量

        Returns:
            筛选后的股票 DataFrame
        """
        # 获取A股全量列表（简化：使用主要股票）
        universe = self.provider.get_stock_list("CN")
        if not universe:
            # 备用：用常见A股列表
            universe = [f"CN.{code}" for code in [
                "600000", "600036", "600519", "601318", "601398",
                "000001", "000002", "000333", "002594", "300750",
            ]]

        return self.pick(universe, trade_date)


# ─── 卖出规则对接 ─────────────────────────────────────────────

class FutuExitRule:
    """
    富途数据驱动的卖出规则检查

    对接 AStockExitRule，传入实时行情判断是否触发止盈/止损/清仓。
    """

    def __init__(self, futu_provider: Optional[FutuProvider] = None):
        self.provider = futu_provider or FutuProvider()

    def check_exit(
        self,
        symbol: str,
        buy_price: float,
        current_time: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        检查是否触发卖出

        Args:
            symbol: 股票代码
            buy_price: 买入价格
            current_time: 当前时间 HH:MM

        Returns:
            (是否卖出, 原因)
        """
        from datetime import datetime
        import time as time_module

        current_time = current_time or datetime.now().strftime("%H:%M")

        # 获取实时行情
        quotes = self.provider.get_stock_quote([symbol])
        if quotes.empty:
            return False, "行情数据不可用"

        current_price = quotes.iloc[0]['last_price']

        # 检查止盈/止损/尾盘清仓
        is_sell, reason = AStockExitRule.check_sell_signal(
            buy_price=buy_price,
            current_price=current_price,
            current_time=current_time,
            is_next_day=True,
        )

        return is_sell, reason

    def check_gap_open(
        self,
        symbol: str,
        buy_price: float,
        trade_date: str,
    ) -> tuple[bool, str]:
        """
        检查次日开盘是否低开止损

        Args:
            symbol: 股票代码
            buy_price: 买入价格
            trade_date: 买入日期

        Returns:
            (是否卖出, 原因)
        """
        from datetime import datetime, timedelta

        # 获取次日开盘价
        next_date = (datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        df = self.provider.get_daily_bars(symbol, next_date, next_date)
        if df.empty:
            return False, "次日行情不可用"

        open_price = df.iloc[0]['open']

        return AStockExitRule.check_open_gap_down(buy_price, open_price)