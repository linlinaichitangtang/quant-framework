"""
公共数据类型定义
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
import types as std_types


@dataclass
class TickData:
    """Tick行情数据"""

    symbol: str
    """标的代码"""
    price: float
    """最新价"""
    volume: float
    """成交量"""
    timestamp: datetime
    """时间戳"""
    open: Optional[float] = None
    """开盘价"""
    high: Optional[float] = None
    """最高价"""
    low: Optional[float] = None
    """最低价"""


@dataclass
class Position:
    """持仓信息"""

    symbol: str
    """标的代码"""
    volume: int
    """持仓量"""
    cost: float
    """持仓成本"""
    current_price: float
    """当前价格"""

    @property
    def market_value(self) -> float:
        """市值"""
        return self.volume * self.current_price

    @property
    def profit(self) -> float:
        """盈亏"""
        return self.volume * (self.current_price - self.cost)

    @property
    def profit_pct(self) -> float:
        """盈亏比例"""
        return (self.current_price - self.cost) / self.cost if self.cost != 0 else 0


@dataclass
class Order:
    """订单"""

    symbol: str
    """标的代码"""
    side: Literal["buy", "sell"]
    """买卖方向"""
    volume: int
    """数量"""
    price: Optional[float] = None
    """价格，None表示市价"""
    order_id: Optional[str] = None
    """订单ID"""
    status: Literal["pending", "filled", "canceled", "rejected"] = "pending"
    """订单状态"""


@dataclass
class Trade:
    """成交记录"""

    symbol: str
    """标的代码"""
    side: Literal["buy", "sell"]
    """买卖方向"""
    volume: int
    """成交数量"""
    price: float
    """成交价格"""
    timestamp: datetime
    """成交时间"""
    trade_id: str
    """成交ID"""
    order_id: str
    """订单ID"""


@dataclass
class AccountInfo:
    """账户信息"""

    total_balance: float
    """总资金"""
    available_balance: float
    """可用资金"""
    frozen_balance: float
    """冻结资金"""
    total_market_value: float
    """总市值"""


@dataclass
class StockScore:
    """股票评分"""

    symbol: str
    """标的代码"""
    score: float
    """综合评分"""
    factor_scores: dict[str, float]
    """各因子评分"""


@dataclass
class MarketEvent:
    """市场事件"""

    event_type: str
    """事件类型"""
    symbol: Optional[str]
    """关联标的"""
    timestamp: datetime
    """事件时间"""
    data: dict
    """事件数据"""
    message: str
    """事件描述"""


class OpenClawFrameworkError(Exception):
    """框架基础异常"""
    pass


class APIError(OpenClawFrameworkError):
    """API调用错误"""
    pass


class RiskCheckError(OpenClawFrameworkError):
    """风控检查不通过"""
    pass


class DataSourceError(OpenClawFrameworkError):
    """数据源错误"""
    pass
