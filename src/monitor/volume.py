"""
成交量异动监控
"""

from collections import deque
from datetime import datetime

from src.data_types import TickData, MarketEvent
from .base import BaseMonitor


class VolumeSpikeMonitor(BaseMonitor):
    """成交量放量监控器

    当成交量相对于近期均值放大超过倍数时触发事件
    """

    def __init__(
        self,
        window_size: int = 20,
        multiple_threshold: float = 3.0,
    ):
        """初始化

        Args:
            window_size: 计算平均成交量的窗口大小
            multiple_threshold: 放量倍数阈值
        """
        super().__init__()
        self.window_size = window_size
        self.multiple_threshold = multiple_threshold
        self._volume_history: dict[str, deque[float]] = {}

    def _get_history(self, symbol: str) -> deque[float]:
        """获取或创建成交量历史"""
        if symbol not in self._volume_history:
            self._volume_history[symbol] = deque(maxlen=self.window_size)
        return self._volume_history[symbol]

    def on_tick(self, tick: TickData):
        """处理tick数据"""
        history = self._get_history(tick.symbol)
        current_vol = tick.volume

        # 如果历史足够，计算均值并检查
        if len(history) == self.window_size:
            avg_vol = sum(history) / len(history)
            if avg_vol > 0 and current_vol / avg_vol >= self.multiple_threshold:
                event = MarketEvent(
                    event_type="volume_spike",
                    symbol=tick.symbol,
                    timestamp=datetime.now(),
                    data={
                        "current_volume": current_vol,
                        "average_volume": avg_vol,
                        "multiple": current_vol / avg_vol,
                    },
                    message=f"{tick.symbol} 成交量放量 {current_vol / avg_vol:.2f}倍，超过阈值 {self.multiple_threshold}倍",
                )
                self.emit_event(event)

        history.append(current_vol)

    def on_event(self, event: MarketEvent):
        """处理其他事件"""
        pass
