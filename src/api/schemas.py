"""
API请求/响应模型定义
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Literal


class OrderRequest(BaseModel):
    """下单请求"""

    symbol: str
    side: Literal["buy", "sell"]
    volume: int
    price: Optional[float] = None


class CancelRequest(BaseModel):
    """撤单请求"""

    order_id: str


class OrderResponse(BaseModel):
    """下单响应"""

    success: bool
    order_id: Optional[str] = None
    message: str = ""


class PositionResponse(BaseModel):
    """持仓响应"""

    symbol: str
    volume: int
    cost: float
    current_price: float


class AccountResponse(BaseModel):
    """账户信息响应"""

    total_balance: float
    available_balance: float
    frozen_balance: float
    total_market_value: float


class TickPush(BaseModel):
    """tick推送"""

    symbol: str
    price: float
    volume: float
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None


class TradePush(BaseModel):
    """成交推送"""

    symbol: str
    side: Literal["buy", "sell"]
    volume: int
    price: float
    timestamp: datetime
    trade_id: str
    order_id: str


class WebsocketMessage(BaseModel):
    """WebSocket消息"""

    msg_type: Literal["tick", "trade", "order_update", "position_update"]
    data: dict
