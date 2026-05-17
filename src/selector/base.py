"""
选股模块基类定义
"""

from abc import ABC, abstractmethod
from typing import List

from src.data_types import StockScore


class BaseSelector(ABC):
    """选股器基类

    所有自定义选股器都应该继承此类
    """

    @abstractmethod
    def filter(self, universe: List[str]) -> List[StockScore]:
        """对股票池进行筛选

        Args:
            universe: 输入候选股票列表

        Returns:
            筛选后的股票评分列表，按评分降序排列
        """
        raise NotImplementedError("子类必须实现filter方法")


class BaseFactor(ABC):
    """因子基类

    用于多因子选股的单个因子
    """

    @abstractmethod
    def calculate(self, symbol: str) -> float:
        """计算因子值

        Args:
            symbol: 股票代码

        Returns:
            因子值（归一化到0-1区间）
        """
        raise NotImplementedError("子类必须实现calculate方法")
