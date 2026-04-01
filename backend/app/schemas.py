from pydantic import BaseModel, Field
from typing import Optional, List, TypeVar, Generic
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


# ========== 策略模板相关 ==========
class TemplateCategoryEnum(str, Enum):
    STOCK_SELECTION = "stock_selection"
    RISK_CONTROL = "risk_control"
    BACKTEST = "backtest"
    SIGNAL = "signal"
    OTHER = "other"


class TemplateCreate(BaseModel):
    """创建/保存模板"""
    name: str = Field(..., min_length=1, max_length=200, description="模板名称")
    description: Optional[str] = Field(None, max_length=2000, description="模板描述")
    category: TemplateCategoryEnum = Field(TemplateCategoryEnum.OTHER, description="模板分类")
    cover_url: Optional[str] = Field(None, max_length=500, description="封面图URL")
    is_public: bool = Field(False, description="是否公开到市场")
    config: str = Field(..., min_length=1, description="策略配置(JSON字符串)")


class TemplateUpdate(BaseModel):
    """更新模板"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[TemplateCategoryEnum] = None
    cover_url: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    config: Optional[str] = None


class TemplateResponse(BaseModel):
    """模板响应"""
    id: int
    name: str
    description: Optional[str] = None
    category: str
    cover_url: Optional[str] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    is_public: bool
    config: str
    install_count: int = 0
    rating_avg: float = 0
    rating_count: int = 0
    version: int = 1
    status: str = "active"
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MarketTemplateResponse(BaseModel):
    """市场模板列表响应（不含 config 详情）"""
    id: int
    name: str
    description: Optional[str] = None
    category: str
    cover_url: Optional[str] = None
    author_name: Optional[str] = None
    install_count: int = 0
    rating_avg: float = 0
    rating_count: int = 0
    version: int = 1
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateRateRequest(BaseModel):
    """模板评分"""
    score: int = Field(..., ge=1, le=5, description="评分 1-5")


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


# ========== 策略配置 ==========
class StrategyConfigBase(BaseModel):
    strategy_id: str
    strategy_name: str
    market: MarketType
    enabled: Optional[bool] = True
    config: Optional[str] = None
    max_position: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


class StrategyConfigCreate(StrategyConfigBase):
    pass


class StrategyConfigUpdate(BaseModel):
    strategy_name: Optional[str] = None
    market: Optional[MarketType] = None
    enabled: Optional[bool] = None
    config: Optional[str] = None
    max_position: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


class StrategyConfigResponse(StrategyConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 分页响应 ==========
T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    page_size: int
    data: List[T]


# ========== FMZ接口调用请求 ==========
class FMZExecuteRequest(BaseModel):
    signal_id: int
    robot_id: Optional[int] = None


class FMZExecuteResponse(BaseModel):
    success: bool
    message: str
    command: Optional[str] = None
    robot_id: Optional[int] = None
    order_id: Optional[str] = None
    data: Optional[dict] = None


class FMZRobotStatus(BaseModel):
    robot_id: Optional[int] = None
    name: Optional[str] = None
    status: int = -1
    status_text: str = "未知"
    strategy_name: Optional[str] = None
    refresh: Optional[str] = None


class FMZCommandRequest(BaseModel):
    robot_id: Optional[int] = None
    command: str
    description: Optional[str] = None


# ========== 认证相关 ==========
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    display_name: Optional[str] = Field(None, max_length=100, description="显示名称")


class UserLogin(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24小时


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100)


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


# ========== 通用响应 ==========
class CommonResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


# ========== 回测相关 ==========
class BacktestConfig(BaseModel):
    """回测参数配置"""
    name: str = Field(..., min_length=1, max_length=200, description="回测名称")
    strategy_type: str = Field("ml_stock_picker", description="策略类型")
    market: MarketType = Field(MarketType.A, description="市场")
    initial_capital: float = Field(1_000_000, ge=10_000, description="初始资金")
    commission: float = Field(0.0003, ge=0, description="佣金费率")
    stamp_tax: float = Field(0.001, ge=0, description="印花税率")
    slippage: float = Field(0.001, ge=0, description="滑点")
    start_date: Optional[str] = Field(None, description="回测开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="回测结束日期 YYYY-MM-DD")
    top_n: int = Field(3, ge=1, le=20, description="每日选股数量")
    min_prob: float = Field(0.5, ge=0.1, le=0.99, description="最低预测概率")
    max_position_pct: float = Field(0.2, ge=0.05, le=1.0, description="单只最大仓位")
    model_type: str = Field("gbm", description="模型类型 gbm/rf")
    n_trials: int = Field(20, ge=1, le=200, description="Optuna 调参次数")


class BacktestTradeResponse(BaseModel):
    """回测交易明细"""
    id: int
    date: str
    action: str
    code: str
    price: float
    shares: int
    cost: Optional[float] = None
    commission: Optional[float] = 0
    stamp_tax: Optional[float] = 0
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None

    class Config:
        from_attributes = True


class BacktestResultResponse(BaseModel):
    """回测结果"""
    id: int
    name: str
    strategy_type: str
    market: str
    status: str
    initial_capital: float
    commission: float
    stamp_tax: float
    slippage: float
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    final_value: Optional[float] = None
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    n_trades: int = 0
    win_rate: Optional[float] = None
    avg_pnl: Optional[float] = None
    avg_pnl_pct: Optional[float] = None
    profit_loss_ratio: Optional[float] = None
    daily_values: Optional[str] = None
    feature_importance: Optional[str] = None
    created_at: datetime
    trades: List[BacktestTradeResponse] = []

    class Config:
        from_attributes = True


class BacktestSummaryResponse(BaseModel):
    """回测列表摘要（不含交易明细和每日数据）"""
    id: int
    name: str
    strategy_type: str
    market: str
    status: str
    initial_capital: float
    final_value: Optional[float] = None
    total_return: Optional[float] = None
    annual_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    n_trades: int = 0
    win_rate: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
