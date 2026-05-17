"""
监控模块基类定义
"""

from abc import ABC, abstractmethod
from typing import Callable, List

from src.data_types import TickData, MarketEvent


class BaseMonitor(ABC):
    """监控器基类

    所有自定义监控器都应该继承此类
    """

    def __init__(self):
        self._callbacks: List[Callable[[MarketEvent], None]] = []

    def register_callback(self, callback: Callable[[MarketEvent], None]):
        """注册事件回调

        当监控器检测到事件时，会调用此回调

        Args:
            callback: 回调函数，接收MarketEvent参数
        """
        self._callbacks.append(callback)

    def emit_event(self, event: MarketEvent):
        """触发事件

        Args:
            event: 市场事件
        """
        for callback in self._callbacks:
            callback(event)

    @abstractmethod
    def on_tick(self, tick: TickData):
        """处理新tick数据

        每个新tick都会调用此方法

        Args:
            tick: tick数据
        """
        raise NotImplementedError("子类必须实现on_tick方法")

    @abstractmethod
    def on_event(self, event: MarketEvent):
        """处理其他市场事件

        Args:
            event: 市场事件
        """
        raise NotImplementedError("子类必须实现on_event方法")
