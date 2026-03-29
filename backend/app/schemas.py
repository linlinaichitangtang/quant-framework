from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class MarketType(str, Enum):
    A = "A"
    HK = "HK"
    US = "US"


class BarType(str, Enum):
    DAILY = "1d"
    MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    HOUR = "1h"


# ========== 股票基础信息 ==========
class StockInfoBase(BaseModel):
    symbol: str
    name: str
    market: MarketType
    is_listed: Optional[bool] = True
    industry: Optional[str] = None
    list_date: Optional[date] = None


class StockInfoCreate(StockInfoBase):
    pass


class StockInfoUpdate(StockInfoBase):
    pass


class StockInfoResponse(StockInfoBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== 历史行情 ==========
class HistoricalBarBase(BaseModel):
    symbol: str
    market: MarketType
    bar_type: BarType = BarType.DAILY
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: Optional[float] = None


class HistoricalBarCreate(HistoricalBarBase):
    pass


class HistoricalBarResponse(HistoricalBarBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ========== 持仓信息 ==========
class PositionBase(BaseModel):
    symbol: str
    market: MarketType
    quantity: float
    avg_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    profit_pct: Optional[float] = None
    profit_amount: Optional[float] = None
    is_option: Optional[bool] = False
    option_type: Optional[str] = None
    strike_price: Optional[float] = None
    expiry_date: Optional[date] = None


class PositionCreate(PositionBase):
    pass


class PositionUpdate(PositionBase):
    pass


class PositionResponse(PositionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== 交易信号 ==========
class TradingSignalBase(BaseModel):
    signal_id: Optional[str] = None
    symbol: str
    market: MarketType
    side: str  # BUY/SELL
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    signal_type: Optional[str] = "OPEN"  # OPEN/CLOSE
    confidence: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    quantity: Optional[float] = None
    reason: Optional[str] = None


class TradingSignalCreate(TradingSignalBase):
    pass


class TradingSignalResponse(TradingSignalBase):
    id: int
    status: str
    executed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ========== 交易记录 ==========
class TradeRecordBase(BaseModel):
    order_id: Optional[str] = None
    symbol: str
    market: MarketType
    side: str
    quantity: float
    price: float
    amount: float
    commission: Optional[float] = 0
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    signal_id: Optional[int] = None
    fmz_order_id: Optional[str] = None
    status: str = "FILLED"


class TradeRecordCreate(TradeRecordBase):
    pass


class TradeRecordResponse(TradeRecordBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== 选股结果 ==========
class StockSelectionBase(BaseModel):
    symbol: str
    name: str
    market: MarketType
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    score: Optional[float] = None
    reason: Optional[str] = None
    selection_date: datetime


class StockSelectionCreate(StockSelectionBase):
    pass


class StockSelectionResponse(StockSelectionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ========== 分页响应 ==========
class PaginatedResponse[T](BaseModel):
    total: int
    page: int
    page_size: int
    data: List[T]


# ========== FMZ接口调用请求 ==========
class FMZExecuteRequest(BaseModel):
    signal_id: int
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    cid: Optional[int] = None


class FMZExecuteResponse(BaseModel):
    success: bool
    message: str
    order_id: Optional[str] = None
    data: Optional[dict] = None


# ========== 通用响应 ==========
class CommonResponse[T](BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[T] = None
