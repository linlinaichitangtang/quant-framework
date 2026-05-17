"""
策略基类
用户自定义策略需要继承此类
"""

from abc import ABC, abstractmethod
from typing import List

from src.data_types import Order, MarketEvent
from src.data_types import StockScore
from src.risk.composable.base import RiskContext


class BaseStrategy(ABC):
    """策略基类"""

    @abstractmethod
    def on_open(self):
        """开盘时调用"""
        raise NotImplementedError("子类必须实现on_open方法")

    @abstractmethod
    def on_close(self):
        """收盘时调用"""
        raise NotImplementedError("子类必须实现on_close方法")

    @abstractmethod
    def on_stock_selected(self, candidates: List[StockScore]) -> List[Order]:
        """选股完成后生成交易指令

        Args:
            candidates: 选股结果，按评分降序排列

        Returns:
            交易指令列表
        """
        raise NotImplementedError("子类必须实现on_stock_selected方法")

    @abstractmethod
    def on_market_event(self, event: MarketEvent) -> List[Order]:
        """处理市场事件，生成交易指令

        Args:
            event: 市场事件

        Returns:
            交易指令列表
        """
        raise NotImplementedError("子类必须实现on_market_event方法")
