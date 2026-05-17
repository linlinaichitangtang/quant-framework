"""
数据源基类定义
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from pandas import DataFrame


class BaseDataSource(ABC):
    """数据源基类

    所有自定义数据源都应该继承此类
    """

    @abstractmethod
    def get_daily(self, symbol: str, start_date: str, end_date: str) -> DataFrame:
        """获取日线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            包含ohlcv的DataFrame
        """
        raise NotImplementedError("子类必须实现get_daily方法")

    @abstractmethod
    def get_minute(self, symbol: str, freq: int = 1) -> DataFrame:
        """获取分钟线数据

        Args:
            symbol: 股票代码
            freq: 分钟周期，默认1分钟

        Returns:
            包含ohlcv的DataFrame
        """
        raise NotImplementedError("子类必须实现get_minute方法")

    @abstractmethod
    def get_stock_list(self) -> List[str]:
        """获取全量股票列表

        Returns:
            股票代码列表
        """
        raise NotImplementedError("子类必须实现get_stock_list方法")

    @abstractmethod
    def get_fundamental(self, symbol: str) -> dict:
        """获取基本面数据

        Args:
            symbol: 股票代码

        Returns:
            基本面数据字典
        """
        raise NotImplementedError("子类必须实现get_fundamental方法")
