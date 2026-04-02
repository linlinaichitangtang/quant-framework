"""
OpenClaw 量化交易平台 Python SDK - 数据模型
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型"""
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"


class SignalStatus(str, Enum):
    """信号状态"""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class BacktestStatus(str, Enum):
    """回测状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ========== 市场数据模型 ==========

@dataclass
class Quote:
    """行情报价"""
    symbol: str
    market: str
    price: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    change: float = 0.0
    change_percent: float = 0.0
    timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Quote":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Kline:
    """K线数据"""
    symbol: str
    market: str
    period: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: Optional[str] = None
    turnover: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "Kline":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StockInfo:
    """股票信息"""
    symbol: str
    name: str
    market: str
    industry: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    description: Optional[str] = None
    list_date: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "StockInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ========== 交易模型 ==========

@dataclass
class Signal:
    """交易信号"""
    id: Optional[str] = None
    symbol: str = ""
    market: str = ""
    side: str = ""
    strategy_id: Optional[str] = None
    status: str = "pending"
    price: Optional[float] = None
    quantity: Optional[float] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None
    executed_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Position:
    """持仓"""
    id: Optional[str] = None
    symbol: str = ""
    market: str = ""
    side: str = ""
    quantity: float = 0.0
    available_quantity: float = 0.0
    avg_price: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    market_value: float = 0.0
    cost: float = 0.0
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Order:
    """订单"""
    id: Optional[str] = None
    symbol: str = ""
    market: str = ""
    side: str = ""
    type: str = "limit"
    quantity: float = 0.0
    price: Optional[float] = None
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    status: str = "pending"
    fee: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ========== 账户模型 ==========

@dataclass
class AccountBalance:
    """账户余额"""
    currency: str = "CNY"
    total: float = 0.0
    available: float = 0.0
    frozen: float = 0.0
    profit: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "AccountBalance":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AccountInfo:
    """账户信息"""
    account_id: Optional[str] = None
    name: Optional[str] = None
    level: Optional[str] = None
    status: str = "active"
    balances: List[AccountBalance] = field(default_factory=list)
    created_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "AccountInfo":
        if "balances" in data and isinstance(data["balances"], list):
            data["balances"] = [AccountBalance.from_dict(b) for b in data["balances"]]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ========== 回测模型 ==========

@dataclass
class BacktestConfig:
    """回测配置"""
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    symbols: List[str] = field(default_factory=list)
    market: str = "cn"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003
    slippage: float = 0.001
    benchmark: Optional[str] = None
    frequency: str = "daily"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "symbols": self.symbols,
            "market": self.market,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "commission_rate": self.commission_rate,
            "slippage": self.slippage,
            "benchmark": self.benchmark,
            "frequency": self.frequency,
            **self.extra,
        }


@dataclass
class BacktestMetrics:
    """回测指标"""
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_holding_days: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "BacktestMetrics":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BacktestResult:
    """回测结果"""
    id: Optional[str] = None
    config: Optional[BacktestConfig] = None
    status: str = "pending"
    metrics: Optional[BacktestMetrics] = None
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "BacktestResult":
        if "config" in data and isinstance(data["config"], dict):
            data["config"] = BacktestConfig(**{k: v for k, v in data["config"].items() if k in BacktestConfig.__dataclass_fields__})
        if "metrics" in data and isinstance(data["metrics"], dict):
            data["metrics"] = BacktestMetrics.from_dict(data["metrics"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ========== AI 模型 ==========

@dataclass
class AIResponse:
    """AI 响应"""
    query: Optional[str] = None
    answer: str = ""
    confidence: Optional[float] = None
    sources: List[str] = field(default_factory=list)
    market: Optional[str] = None
    timestamp: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "AIResponse":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str = "user"
    content: str = ""
    timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MarketSentiment:
    """市场情绪"""
    market: str = ""
    overall_score: float = 0.0
    label: str = "neutral"
    factors: Dict[str, float] = field(default_factory=dict)
    timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "MarketSentiment":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class StrategyAdvice:
    """策略建议"""
    market: str = ""
    risk_level: str = "medium"
    recommendations: List[str] = field(default_factory=list)
    top_picks: List[Dict[str, Any]] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyAdvice":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ========== 使用统计模型 ==========

@dataclass
class UsageStats:
    """使用统计"""
    total_api_calls: int = 0
    daily_api_calls: int = 0
    monthly_api_calls: int = 0
    api_calls_limit: int = 0
    usage_percent: float = 0.0
    period: Optional[str] = None
    breakdown: Dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "UsageStats":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
