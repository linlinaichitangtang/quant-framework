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


# ==================== V1.8 高可用与灾备 Schema ====================

class ClusterNodeResponse(BaseModel):
    """集群节点响应"""
    node_id: str
    node_type: str
    host: str
    port: int
    status: str
    role: Optional[str] = None
    replication_lag: int = 0
    region: Optional[str] = None
    last_heartbeat: Optional[datetime] = None


class BackupResponse(BaseModel):
    """备份响应"""
    backup_id: str
    backup_type: str
    status: str
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    duration_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SystemHealthResponse(BaseModel):
    """系统健康状态响应"""
    status: str  # healthy/degraded/critical
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    database: str
    cache: str
    uptime: int
    active_connections: int


class PerformanceMetricsResponse(BaseModel):
    """性能指标响应"""
    period: str
    total_requests: int
    qps: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    throughput: float


class AlertRuleResponse(BaseModel):
    """告警规则响应"""
    id: int
    name: str
    metric: str
    condition: str
    threshold: float
    duration: int
    severity: str
    is_enabled: bool


class SystemAlertResponse(BaseModel):
    """系统告警响应"""
    id: int
    rule_name: Optional[str] = None
    severity: str
    message: str
    status: str
    fired_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


# ==================== V1.9 算法交易增强 Schema ====================

class TWAPOrderRequest(BaseModel):
    """TWAP 订单请求"""
    symbol: str
    market: str = "A"
    side: str  # BUY/SELL
    quantity: float
    duration_minutes: int = 60
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    randomize: bool = True
    max_participation_rate: float = 0.1


class VWAPOrderRequest(BaseModel):
    """VWAP 订单请求"""
    symbol: str
    market: str = "A"
    side: str
    quantity: float
    duration_minutes: int = 60
    volume_profile: Optional[str] = None  # auto/front_loaded/back_loaded


class IcebergOrderRequest(BaseModel):
    """冰山订单请求"""
    symbol: str
    market: str = "A"
    side: str
    quantity: float
    display_quantity: float
    random_variance: float = 0.2
    min_display: Optional[float] = None


class SmartOrderRequest(BaseModel):
    """智能拆单请求"""
    symbol: str
    market: str = "A"
    side: str
    quantity: float
    urgency: str = "medium"  # low/medium/high
    max_impact_pct: float = 0.5
    strategy: Optional[str] = None  # auto/twap/vwap/iceberg


class AlgoOrderResponse(BaseModel):
    """算法订单响应"""
    order_id: str
    algo_type: str
    status: str
    symbol: str
    market: str
    side: str
    total_quantity: float
    filled_quantity: float
    avg_fill_price: Optional[float] = None
    target_price: Optional[float] = None
    progress: float = 0  # 执行进度百分比
    child_order_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ExecutionQualityResponse(BaseModel):
    """执行质量评估响应"""
    order_id: str
    algo_type: str
    vwap: float
    market_vwap: float
    implementation_shortfall: float  # 实现价差
    market_impact: float
    avg_slippage: float
    execution_rate: float  # 执行率
    timing_score: float  # 择时评分
    overall_score: float  # 综合评分


# ==================== V1.5 Schema ====================

# ========== AI 对话相关 ==========
class AIChatSessionCreate(BaseModel):
    """创建AI对话会话"""
    title: Optional[str] = Field(None, max_length=200, description="会话标题")
    market: Optional[str] = Field(None, max_length=10, description="关联市场")


class AIChatSessionResponse(BaseModel):
    """AI对话会话响应"""
    id: int
    session_id: str
    user_id: int
    title: Optional[str] = None
    market: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AIChatMessageResponse(BaseModel):
    """AI对话消息响应"""
    id: int
    session_id: str
    role: str
    content: str
    metadata: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ========== 自然语言查询 ==========
class NLQueryRequest(BaseModel):
    """自然语言查询请求"""
    query: str = Field(..., min_length=1, description="用户查询")
    market: Optional[str] = Field(None, description="关联市场")
    context: Optional[str] = Field(None, description="上下文信息")


class NLQueryResponse(BaseModel):
    """自然语言查询响应"""
    answer: str
    data: Optional[dict] = None
    sources: Optional[List[str]] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="置信度")


# ========== 策略建议 ==========
class StrategyAdviceRequest(BaseModel):
    """策略建议请求"""
    market: str = Field(..., description="市场")
    risk_level: str = Field("medium", description="风险等级 low/medium/high")
    current_positions: Optional[List[dict]] = Field(None, description="当前持仓列表")


class StrategyAdviceResponse(BaseModel):
    """策略建议响应"""
    advice: str
    reasoning: str
    risk_warnings: List[str] = []
    suggested_actions: List[str] = []


# ========== 市场情绪 ==========
class SentimentResponse(BaseModel):
    """市场情绪响应"""
    market: str
    score: float
    label: str
    news_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    summary: str = ""
    top_factors: List[str] = []


# ========== 异常交易检测 ==========
class AnomalyResponse(BaseModel):
    """异常交易检测响应"""
    symbol: str
    anomalies: List[dict] = []
    summary: str = ""
    risk_level: str = "medium"


# ========== 策略归因分析 ==========
class AttributionResponse(BaseModel):
    """策略归因分析响应"""
    strategy_id: str
    total_return: float
    alpha: float
    beta_return: float
    timing_return: float
    sector_contribution: Optional[dict] = None
    risk_contribution: Optional[dict] = None
    summary: str = ""


# ==================== V2.0 Schema ====================

# ========== 多租户管理 ==========
class TenantCreate(BaseModel):
    """创建租户"""
    name: str = Field(..., min_length=1, max_length=200, description="租户名称")
    slug: str = Field(..., min_length=1, max_length=50, description="租户标识")
    plan: str = Field("free", description="订阅计划 free/basic/pro/enterprise")
    brand_name: Optional[str] = Field(None, max_length=200, description="品牌名称")


class TenantUpdate(BaseModel):
    """更新租户"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = None
    plan: Optional[str] = None
    max_users: Optional[int] = None
    max_strategies: Optional[int] = None
    brand_name: Optional[str] = Field(None, max_length=200)
    brand_logo: Optional[str] = Field(None, max_length=500)
    primary_color: Optional[str] = Field(None, max_length=20)
    custom_domain: Optional[str] = Field(None, max_length=200)
    custom_css: Optional[str] = None


class TenantResponse(BaseModel):
    """租户响应"""
    id: int
    tenant_id: str
    name: str
    slug: str
    status: str
    plan: str
    max_users: int
    max_strategies: int
    max_api_calls: int
    brand_name: Optional[str] = None
    brand_logo: Optional[str] = None
    primary_color: str = "#304156"
    custom_domain: Optional[str] = None
    current_users: int = 0
    current_api_calls: int = 0
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 插件管理 ==========
class PluginCreate(BaseModel):
    """创建插件"""
    name: str = Field(..., min_length=1, max_length=200, description="插件名称")
    description: Optional[str] = Field(None, description="插件描述")
    version: str = Field("1.0.0", max_length=20, description="版本号")
    author: Optional[str] = Field(None, max_length=100, description="作者")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    entry_point: Optional[str] = Field(None, max_length=200, description="入口文件/函数")
    config_schema: Optional[str] = Field(None, description="配置Schema(JSON)")
    permissions: Optional[str] = Field(None, description="所需权限(JSON数组)")
    is_public: bool = Field(False, description="是否公开")


class PluginUpdate(BaseModel):
    """更新插件"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=20)
    is_public: Optional[bool] = None
    status: Optional[str] = None


class PluginResponse(BaseModel):
    """插件响应"""
    id: int
    plugin_id: str
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    category: Optional[str] = None
    is_public: bool = False
    is_verified: bool = False
    status: str = "active"
    install_count: int = 0
    rating_avg: float = 0
    rating_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class PluginInstallRequest(BaseModel):
    """插件安装请求"""
    plugin_id: int = Field(..., description="插件ID")
    config: Optional[str] = Field(None, description="安装配置(JSON)")


# ========== 开放API Key ==========
class OpenAPIKeyCreate(BaseModel):
    """创建开放API Key"""
    key_name: str = Field(..., min_length=1, max_length=200, description="Key名称")
    permissions: Optional[List[str]] = Field(None, description="权限范围")
    rate_limit: int = Field(60, ge=1, description="每分钟请求限制")
    expires_days: Optional[int] = Field(None, description="有效天数")


class OpenAPIKeyResponse(BaseModel):
    """开放API Key响应"""
    id: int
    key_name: str
    api_key: str
    permissions: Optional[str] = None
    rate_limit: int = 60
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    total_calls: int = 0
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 订阅计划 ==========
class SubscriptionPlanResponse(BaseModel):
    """订阅计划响应"""
    id: int
    plan_id: str
    name: str
    description: Optional[str] = None
    price_monthly: float = 0
    price_yearly: float = 0
    max_users: int = 5
    max_strategies: int = 10
    max_api_calls: int = 10000
    features: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """订阅记录响应"""
    id: int
    tenant_id: int
    plan_id: str
    status: str
    billing_cycle: str
    current_period_start: datetime
    current_period_end: datetime
    amount: float

    class Config:
        from_attributes = True


# ========== 用量统计 ==========
class UsageResponse(BaseModel):
    """用量记录响应"""
    metric: str
    value: int
    period: str


class WhitelabelConfig(BaseModel):
    """白标配置"""
    brand_name: Optional[str] = Field(None, max_length=200, description="品牌名称")
    brand_logo: Optional[str] = Field(None, max_length=500, description="品牌Logo URL")
    primary_color: str = Field("#304156", max_length=20, description="主色调")
    custom_domain: Optional[str] = Field(None, max_length=200, description="自定义域名")
    custom_css: Optional[str] = Field(None, description="自定义CSS")
    favicon_url: Optional[str] = Field(None, max_length=500, description="Favicon URL")


class UsageStatsResponse(BaseModel):
    """用量统计响应"""
    api_calls: int = 0
    strategies: int = 0
    users: int = 0
    storage: int = 0
    period: str = ""


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


# ==================== V1.7 多市场扩展 Schema ====================

# ========== 期货相关 ==========
class FuturesContractResponse(BaseModel):
    """期货合约响应"""
    id: int
    symbol: str
    name: str
    exchange: str
    underlying: Optional[str] = None
    contract_month: Optional[str] = None
    multiplier: float = 1
    margin_rate: float = 0.1
    tick_size: Optional[float] = None
    last_price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None

    class Config:
        from_attributes = True


class FuturesMarginRequest(BaseModel):
    """期货保证金计算请求"""
    symbol: str = Field(..., description="合约代码")
    quantity: float = Field(..., gt=0, description="手数")
    price: float = Field(..., gt=0, description="价格")
    leverage: float = Field(1.0, ge=1.0, description="杠杆倍数")


class FuturesMarginResponse(BaseModel):
    """期货保证金计算响应"""
    symbol: str
    notional_value: float
    margin_required: float
    leverage: float
    margin_rate: float


# ========== 加密货币相关 ==========
class CryptoMarketResponse(BaseModel):
    """加密货币市场响应"""
    id: int
    symbol: str
    name: str
    base_currency: Optional[str] = None
    quote_currency: str = "USDT"
    last_price: Optional[float] = None
    change_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None

    class Config:
        from_attributes = True


# ========== ETF 相关 ==========
class ETFResponse(BaseModel):
    """ETF 响应"""
    id: int
    symbol: str
    name: str
    market: str
    nav: Optional[float] = None
    price: Optional[float] = None
    premium_rate: Optional[float] = None
    total_assets: Optional[float] = None
    expense_ratio: Optional[float] = None
    tracking_index: Optional[str] = None
    top_holdings: Optional[list] = None
    sector_allocation: Optional[dict] = None

    class Config:
        from_attributes = True


# ========== 市场时间 ==========
class MarketHoursResponse(BaseModel):
    """市场交易时间响应"""
    market: str
    timezone: str
    current_time: str
    status: str  # open/closed/pre_market/after_hours
    open_time: str
    close_time: str
    next_open: Optional[str] = None


# ========== 跨市场套利 ==========
class ArbitrageResponse(BaseModel):
    """套利机会响应"""
    symbol_a: str
    market_a: str
    symbol_b: str
    market_b: str
    spread: float
    spread_pct: float
    z_score: Optional[float] = None
    is_profitable: bool
    estimated_pnl: Optional[float] = None
    confidence: Optional[float] = None


class ArbitrageCalculateRequest(BaseModel):
    """套利盈亏计算请求"""
    quantity_a: float = Field(..., gt=0, description="标的A数量")
    quantity_b: float = Field(..., gt=0, description="标的B数量")
    price_a: float = Field(..., gt=0, description="标的A价格")
    price_b: float = Field(..., gt=0, description="标的B价格")
    commission_rate: float = Field(0.001, ge=0, description="手续费率")


class ArbitrageCalculateResponse(BaseModel):
    """套利盈亏计算响应"""
    cost_a: float
    cost_b: float
    total_commission: float
    spread: float
    pnl: float
    pnl_pct: float
    is_profitable: bool
    risk_level: str


# ========== 全球市场概览 ==========
class GlobalOverviewResponse(BaseModel):
    """全球市场概览响应"""
    markets: list  # 各市场状态
    correlations: Optional[dict] = None
    arbitrage_opportunities: Optional[list] = None


# ==================== V1.6 社区与协作 Schema ====================

# ========== 用户资料 ==========
class UserProfileResponse(BaseModel):
    """用户资料响应"""
    user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[str] = None
    risk_preference: str = "medium"
    total_trades: int = 0
    win_rate: float = 0
    total_pnl: float = 0
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_following: Optional[bool] = None  # 当前用户是否关注了该用户


class UserProfileUpdate(BaseModel):
    """更新用户资料"""
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[str] = None
    risk_preference: Optional[str] = None


# ========== 讨论帖子 ==========
class PostCreate(BaseModel):
    """创建帖子"""
    title: str
    content: str
    category: str = "general"
    tags: Optional[list] = None


class PostResponse(BaseModel):
    """帖子响应"""
    id: int
    author_id: int
    author_name: str
    author_avatar: Optional[str] = None
    title: str
    content: str
    category: str
    tags: Optional[list] = None
    likes_count: int
    comments_count: int
    views_count: int
    is_pinned: bool
    is_featured: bool
    is_liked: Optional[bool] = None
    created_at: Optional[datetime] = None


# ========== 帖子评论 ==========
class CommentCreate(BaseModel):
    """创建评论"""
    content: str
    parent_id: Optional[int] = None


class CommentResponse(BaseModel):
    """评论响应"""
    id: int
    author_id: int
    author_name: str
    content: str
    parent_id: Optional[int] = None
    likes_count: int
    created_at: Optional[datetime] = None


# ========== 交易分享 ==========
class TradeShareCreate(BaseModel):
    """创建交易分享"""
    is_anonymous: bool = False
    symbol: str
    market: str
    side: str
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    strategy_name: Optional[str] = None
    reasoning: Optional[str] = None


class TradeShareResponse(BaseModel):
    """交易分享响应"""
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None  # 匿名时为 None
    is_anonymous: bool
    symbol: str
    market: str
    side: str
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    strategy_name: Optional[str] = None
    reasoning: Optional[str] = None
    likes_count: int
    comments_count: int
    created_at: Optional[datetime] = None


# ========== 私信 ==========
class MessageCreate(BaseModel):
    """发送私信"""
    receiver_id: int
    content: str


class MessageResponse(BaseModel):
    """私信响应"""
    id: int
    sender_id: int
    receiver_id: int
    content: str
    is_read: bool
    created_at: Optional[datetime] = None


class ConversationResponse(BaseModel):
    """会话列表响应"""
    other_user_id: int
    other_user_name: str
    other_user_avatar: Optional[str] = None
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    unread_count: int = 0


# ========== 排行榜 ==========
class LeaderboardEntry(BaseModel):
    """排行榜条目"""
    rank: int
    user_id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    value: float  # 排行值（收益率/胜率/交易数）
    total_trades: int = 0
    win_rate: float = 0
    total_pnl: float = 0
