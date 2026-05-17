"""
价格涨跌幅监控
"""

from datetime import datetime
from typing import Optional

from src.data_types import TickData, MarketEvent
from .base import BaseMonitor


class PriceChangeMonitor(BaseMonitor):
    """价格涨跌幅监控器

    当股票价格涨跌幅超过阈值时触发事件
    """

    def __init__(
        self,
        up_threshold: float = 0.05,
        down_threshold: float = -0.05,
    ):
        """初始化

        Args:
            up_threshold: 上涨阈值，默认5%
            down_threshold: 下跌阈值，默认-5%
        """
        super().__init__()
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold
        self._open_prices: dict[str, float] = {}

    def set_open_price(self, symbol: str, open_price: float):
        """设置开盘价

        Args:
            symbol: 股票代码
            open_price: 开盘价
        """
        self._open_prices[symbol] = open_price

    def on_tick(self, tick: TickData):
        """处理tick数据"""
        if tick.open is not None:
            self.set_open_price(tick.symbol, tick.open)

        if tick.symbol not in self._open_prices:
            return

        open_price = self._open_prices[tick.symbol]
        if open_price == 0:
            return

        change = (tick.price - open_price) / open_price

        if change >= self.up_threshold:
            event = MarketEvent(
                event_type="price_spike_up",
                symbol=tick.symbol,
                timestamp=datetime.now(),
                data={
                    "price": tick.price,
                    "open": open_price,
                    "change": change,
                },
                message=f"{tick.symbol} 上涨 {change*100:.2f}%，超过阈值 {self.up_threshold*100:.2f}%",
            )
            self.emit_event(event)

        elif change <= self.down_threshold:
            event = MarketEvent(
                event_type="price_spike_down",
                symbol=tick.symbol,
                timestamp=datetime.now(),
                data={
                    "price": tick.price,
                    "open": open_price,
                    "change": change,
                },
                message=f"{tick.symbol} 下跌 {change*100:.2f}%，超过阈值 {self.down_threshold*100:.2f}%",
            )
            self.emit_event(event)

    def on_event(self, event: MarketEvent):
        """处理其他事件"""
        pass
