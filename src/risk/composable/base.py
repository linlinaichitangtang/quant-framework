"""
风控模块基类定义
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

from src.data_types import Position, AccountInfo


@dataclass
class RiskContext:
    """风控上下文

    包含风控检查所需的全部信息
    """

    target_symbol: str
    """目标标的"""
    target_volume: int
    """目标成交量"""
    side: str
    """买卖方向"""
    current_positions: List[Position]
    """当前持仓"""
    account: AccountInfo
    """账户信息"""
    price: float
    """交易价格"""


@dataclass
class RiskResult:
    """风控检查结果"""

    passed: bool
    """是否通过"""
    message: str
    """结果信息"""
    adjusted_volume: int = 0
    """调整后的成交量，0表示不调整"""


class BaseRiskControl(ABC):
    """风控规则基类

    所有自定义风控规则都应该继承此类
    """

    @abstractmethod
    def check(self, context: RiskContext) -> RiskResult:
        """执行风控检查

        Args:
            context: 风控上下文

        Returns:
            风控检查结果
        """
        raise NotImplementedError("子类必须实现check方法")
