import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


class MarketType(enum.Enum):
    A = "A"  # A股
    HK = "HK"  # 港股
    US = "US"  # 美股


class BarType(enum.Enum):
    DAILY = "1d"  # 日线
    MINUTE = "1m"  # 1分钟
    FIVE_MINUTE = "5m"  # 5分钟
    FIFTEEN_MINUTE = "15m"  # 15分钟
    HOUR = "1h"  # 小时


# 历史行情数据表
class HistoricalBar(Base):
    __tablename__ = "historical_bars"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False, comment="股票代码")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    bar_type = Column(Enum(BarType), nullable=False, comment="K线类型")
    timestamp = Column(DateTime, nullable=False, comment="时间戳")
    open = Column(Float, nullable=False, comment="开盘价")
    high = Column(Float, nullable=False, comment="最高价")
    low = Column(Float, nullable=False, comment="最低价")
    close = Column(Float, nullable=False, comment="收盘价")
    volume = Column(Float, nullable=False, comment="成交量")
    turnover = Column(Float, comment="成交额")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    
    __table_args__ = {'comment': '历史行情K线数据'}
    
    def __repr__(self):
        return f"<HistoricalBar {self.symbol} {self.timestamp}>"


# 股票基础信息表
class StockInfo(Base):
    __tablename__ = "stock_info"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, index=True, nullable=False, comment="股票代码")
    name = Column(String(100), nullable=False, comment="股票名称")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    is_listed = Column(Boolean, default=True, comment="是否上市")
    industry = Column(String(50), comment="行业")
    list_date = Column(Date, comment="上市日期")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = {'comment': '股票基础信息表'}
    
    def __repr__(self):
        return f"<StockInfo {self.symbol} {self.name}>"


# 持仓信息表
class Position(Base):
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False, comment="股票代码")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    quantity = Column(Float, nullable=False, comment="持仓数量")
    avg_cost = Column(Float, nullable=False, comment="平均成本")
    current_price = Column(Float, comment="当前价格")
    market_value = Column(Float, comment="市值")
    profit_pct = Column(Float, comment="盈亏比例")
    profit_amount = Column(Float, comment="盈亏金额")
    is_option = Column(Boolean, default=False, comment="是否期权")
    option_type = Column(String(10), comment="期权类型 CALL/PUT")
    strike_price = Column(Float, comment="行权价")
    expiry_date = Column(Date, comment="到期日")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = {'comment': '当前持仓信息'}
    
    def __repr__(self):
        return f"<Position {self.symbol} {self.quantity}>"


# 交易记录表
class TradeRecord(Base):
    __tablename__ = "trade_records"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True, comment="订单ID")
    symbol = Column(String(20), index=True, nullable=False, comment="股票代码")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    side = Column(String(10), nullable=False, comment="方向 BUY/SELL")
    quantity = Column(Float, nullable=False, comment="数量")
    price = Column(Float, nullable=False, comment="成交价格")
    amount = Column(Float, nullable=False, comment="成交金额")
    commission = Column(Float, default=0, comment="手续费")
    strategy_id = Column(String(50), comment="策略ID")
    strategy_name = Column(String(100), comment="策略名称")
    signal_id = Column(Integer, ForeignKey("trading_signals.id"), comment="信号ID")
    fmz_order_id = Column(String(50), comment="FMZ订单ID")
    status = Column(String(20), nullable=False, comment="状态 FILLED/PENDING/CANCELLED")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    signal = relationship("TradingSignal", back_populates="trades")
    
    __table_args__ = {'comment': '交易记录表'}
    
    def __repr__(self):
        return f"<TradeRecord {self.side} {self.symbol} {self.quantity}@{self.price}>"


# 交易信号表
class TradingSignal(Base):
    __tablename__ = "trading_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(50), unique=True, index=True, comment="信号ID")
    symbol = Column(String(20), index=True, nullable=False, comment="股票代码")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    side = Column(String(10), nullable=False, comment="方向 BUY/SELL")
    strategy_id = Column(String(50), comment="策略ID")
    strategy_name = Column(String(100), comment="策略名称")
    signal_type = Column(String(20), comment="信号类型 OPEN/CLOSE")
    confidence = Column(Float, comment="置信度")
    target_price = Column(Float, comment="目标价格")
    stop_loss = Column(Float, comment="止损价")
    take_profit = Column(Float, comment="止盈价")
    quantity = Column(Float, comment="建议数量")
    status = Column(String(20), default="PENDING", comment="状态 PENDING/EXECUTED/FAILED/EXPIRED")
    reason = Column(Text, comment="信号理由")
    executed_at = Column(DateTime, comment="执行时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    
    trades = relationship("TradeRecord", back_populates="signal", cascade="all, delete-orphan")
    
    __table_args__ = {'comment': '交易信号表'}
    
    def __repr__(self):
        return f"<TradingSignal {self.side} {self.symbol} {self.status}>"


# 选股结果表
class StockSelection(Base):
    __tablename__ = "stock_selections"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), index=True, nullable=False, comment="股票代码")
    name = Column(String(100), nullable=False, comment="股票名称")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    strategy_id = Column(String(50), comment="策略ID")
    strategy_name = Column(String(100), comment="策略名称")
    score = Column(Float, comment="选股评分")
    reason = Column(Text, comment="选股理由")
    selection_date = Column(DateTime, nullable=False, comment="选股日期")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    
    __table_args__ = {'comment': '选股结果表'}
    
    def __repr__(self):
        return f"<StockSelection {self.symbol} {self.score:.2f}>"


# 系统日志表
class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(10), nullable=False, comment="日志级别 DEBUG/INFO/WARNING/ERROR")
    module = Column(String(50), comment="模块名称")
    message = Column(Text, nullable=False, comment="日志消息")
    details = Column(Text, comment="详细信息(JSON)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    
    __table_args__ = {'comment': '系统日志表'}
    
    def __repr__(self):
        return f"<SystemLog {self.level} {self.module}: {self.message[:50]}>"


# 策略配置表
class StrategyConfig(Base):
    __tablename__ = "strategy_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(String(50), unique=True, index=True, nullable=False, comment="策略ID")
    strategy_name = Column(String(100), nullable=False, comment="策略名称")
    market = Column(Enum(MarketType), nullable=False, comment="适用市场")
    enabled = Column(Boolean, default=True, comment="是否启用")
    config = Column(Text, comment="配置(JSON)")
    max_position = Column(Float, comment="最大仓位")
    stop_loss_pct = Column(Float, comment="止损百分比")
    take_profit_pct = Column(Float, comment="止盈百分比")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = {'comment': '策略配置表'}
    
    def __repr__(self):
        return f"<StrategyConfig {self.strategy_id} {self.strategy_name}>"


# 用户表
class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="密码哈希")
    display_name = Column(String(100), comment="显示名称")
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False, comment="角色")
    is_active = Column(Boolean, default=True, comment="是否激活")
    last_login = Column(DateTime, comment="最后登录时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    
    __table_args__ = {'comment': '用户表'}
    
    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"


# 通知历史表
class NotificationLevel(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationHistory(Base):
    __tablename__ = "notification_history"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="通知标题")
    content = Column(Text, nullable=False, comment="通知内容")
    channel = Column(String(50), nullable=False, comment="通知频道")
    level = Column(Enum(NotificationLevel), default=NotificationLevel.INFO, comment="通知级别")
    is_read = Column(Boolean, default=False, comment="是否已读")
    recipients = Column(Text, comment="收件人(JSON)")
    data = Column(Text, comment="附加数据(JSON)")
    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")

    __table_args__ = {'comment': '通知历史记录表'}

    def __repr__(self):
        return f"<Notification {self.title[:30]}>"


# 回测结果表
class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="回测名称")
    strategy_type = Column(String(50), default="ml_stock_picker", comment="策略类型")
    market = Column(Enum(MarketType), default=MarketType.A, comment="市场")
    status = Column(String(20), default="completed", comment="状态 completed/failed/running")

    # 回测参数
    initial_capital = Column(Float, default=1_000_000, comment="初始资金")
    commission = Column(Float, default=0.0003, comment="佣金费率")
    stamp_tax = Column(Float, default=0.001, comment="印花税率")
    slippage = Column(Float, default=0.001, comment="滑点")
    start_date = Column(String(20), comment="回测开始日期")
    end_date = Column(String(20), comment="回测结束日期")
    params = Column(Text, comment="额外参数(JSON)")

    # 回测结果指标
    final_value = Column(Float, comment="最终资金")
    total_return = Column(Float, comment="总收益率")
    annual_return = Column(Float, comment="年化收益率")
    max_drawdown = Column(Float, comment="最大回撤")
    sharpe_ratio = Column(Float, comment="夏普比率")
    n_trades = Column(Integer, default=0, comment="交易次数")
    win_rate = Column(Float, comment="胜率")
    avg_pnl = Column(Float, comment="平均盈亏")
    avg_pnl_pct = Column(Float, comment="平均盈亏比例")
    profit_loss_ratio = Column(Float, comment="盈亏比")

    # 每日资产数据（JSON 数组）
    daily_values = Column(Text, comment="每日资产数据(JSON)")
    # 模型特征重要性（JSON）
    feature_importance = Column(Text, comment="特征重要性(JSON)")

    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")

    trades = relationship("BacktestTrade", back_populates="backtest", cascade="all, delete-orphan")

    __table_args__ = {'comment': '回测结果表'}

    def __repr__(self):
        return f"<BacktestResult {self.name} ({self.status})>"


# 回测交易明细表
class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(Integer, ForeignKey("backtest_results.id"), nullable=False, comment="回测ID")
    date = Column(String(20), nullable=False, comment="交易日期")
    action = Column(String(10), nullable=False, comment="方向 buy/sell")
    code = Column(String(20), nullable=False, comment="股票代码")
    price = Column(Float, nullable=False, comment="成交价格")
    shares = Column(Integer, nullable=False, comment="成交数量")
    cost = Column(Float, comment="成本/收入")
    commission = Column(Float, default=0, comment="佣金")
    stamp_tax = Column(Float, default=0, comment="印花税")
    pnl = Column(Float, comment="盈亏金额")
    pnl_pct = Column(Float, comment="盈亏比例")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    backtest = relationship("BacktestResult", back_populates="trades")

    __table_args__ = {'comment': '回测交易明细表'}

    def __repr__(self):
        return f"<BacktestTrade {self.action} {self.code} {self.shares}@{self.price}>"


# 策略模板表
class TemplateCategory(enum.Enum):
    STOCK_SELECTION = "stock_selection"  # 选股策略
    RISK_CONTROL = "risk_control"        # 风控模型
    BACKTEST = "backtest"               # 回测模板
    SIGNAL = "signal"                   # 信号策略
    OTHER = "other"                     # 其他


class StrategyTemplate(Base):
    __tablename__ = "strategy_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="模板名称")
    description = Column(Text, comment="模板描述")
    category = Column(Enum(TemplateCategory), default=TemplateCategory.OTHER, comment="模板分类")
    cover_url = Column(String(500), comment="封面图URL")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="作者ID")
    author_name = Column(String(100), comment="作者名称")
    is_public = Column(Boolean, default=False, comment="是否公开到市场")
    # 策略配置 JSON（包含策略参数、因子配置、风控参数等）
    config = Column(Text, nullable=False, comment="策略配置(JSON)")
    # 统计数据
    install_count = Column(Integer, default=0, comment="安装次数")
    rating_avg = Column(Float, default=0, comment="平均评分")
    rating_count = Column(Integer, default=0, comment="评分人数")
    version = Column(Integer, default=1, comment="当前版本号")
    status = Column(String(20), default="active", comment="状态 active/archived")
    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    versions = relationship("TemplateVersion", back_populates="template", cascade="all, delete-orphan")

    __table_args__ = {'comment': '策略模板表'}

    def __repr__(self):
        return f"<StrategyTemplate {self.name} (v{self.version})>"


# 模板版本表
class TemplateVersion(Base):
    __tablename__ = "template_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("strategy_templates.id"), nullable=False, comment="模板ID")
    version = Column(Integer, nullable=False, comment="版本号")
    config = Column(Text, nullable=False, comment="该版本的策略配置(JSON)")
    changelog = Column(Text, comment="版本变更说明")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    template = relationship("StrategyTemplate", back_populates="versions")

    __table_args__ = (
        {'comment': '模板版本表'},
    )


# 期权合约表
class OptionContract(Base):
    __tablename__ = "option_contracts"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30), nullable=False, index=True, comment="标的代码")
    underlying_price = Column(Float, comment="标的当前价格")
    option_type = Column(String(4), nullable=False, comment="期权类型 CALL/PUT")
    strike_price = Column(Float, nullable=False, comment="行权价")
    expiry_date = Column(Date, nullable=False, index=True, comment="到期日")
    days_to_expiry = Column(Integer, comment="距到期天数")
    # 价格数据
    bid = Column(Float, comment="买价")
    ask = Column(Float, comment="卖价")
    last_price = Column(Float, comment="最新价")
    volume = Column(Integer, default=0, comment="成交量")
    open_interest = Column(Integer, default=0, comment="持仓量")
    # 希腊字母
    delta = Column(Float, comment="Delta")
    gamma = Column(Float, comment="Gamma")
    theta = Column(Float, comment="Theta")
    vega = Column(Float, comment="Vega")
    implied_vol = Column(Float, comment="隐含波动率")
    # 期权指标
    intrinsic_value = Column(Float, comment="内在价值")
    time_value = Column(Float, comment="时间价值")
    is_itm = Column(Boolean, default=False, comment="是否实值")
    # 元数据
    market = Column(Enum(MarketType), default=MarketType.US, comment="市场")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    __table_args__ = {'comment': '期权合约表'}

    def __repr__(self):
        return f"<OptionContract {self.symbol} {self.option_type} {self.strike_price} {self.expiry_date}>"


# 期权组合表
class OptionPosition(Base):
    __tablename__ = "option_positions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), comment="组合名称")
    strategy_type = Column(String(50), comment="策略类型 iron_condor/butterfly/calendar_spread 等")
    status = Column(String(20), default="open", comment="状态 open/closed/expired")
    underlying_symbol = Column(String(30), nullable=False, comment="标的代码")
    legs = Column(Text, nullable=False, comment="组合腿(JSON数组)")
    max_profit = Column(Float, comment="最大盈利")
    max_loss = Column(Float, comment="最大亏损")
    breakeven_low = Column(Float, comment="盈亏平衡下限")
    breakeven_high = Column(Float, comment="盈亏平衡上限")
    net_premium = Column(Float, comment="净权利金")
    current_pnl = Column(Float, default=0, comment="当前盈亏")
    opened_at = Column(DateTime, default=func.now(), comment="开仓时间")
    closed_at = Column(DateTime, comment="平仓时间")

    __table_args__ = {'comment': '期权组合持仓表'}

    def __repr__(self):
        return f"<OptionPosition {self.name} ({self.strategy_type})>"


# FMZ 交易账户表
class TradingAccount(Base):
    __tablename__ = "trading_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="账户名称")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    fmz_account_id = Column(Integer, comment="FMZ 账户ID")
    fmz_api_key = Column(String(200), comment="FMZ API Key")
    fmz_secret_key = Column(String(200), comment="FMZ Secret Key")
    status = Column(String(20), default="active", comment="状态 active/disabled")
    is_default = Column(Boolean, default=False, comment="是否默认账户")

    # 账户级风控参数（JSON，覆盖全局默认值）
    risk_params = Column(Text, comment="风控参数(JSON)")

    # 账户统计
    total_pnl = Column(Float, default=0, comment="累计盈亏")
    today_pnl = Column(Float, default=0, comment="今日盈亏")
    total_trades = Column(Integer, default=0, comment="总交易次数")

    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = {'comment': 'FMZ交易账户表'}

    def __repr__(self):
        return f"<TradingAccount {self.name} ({self.market})>"


# 风控规则表
class RiskRule(Base):
    __tablename__ = "risk_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="规则名称")
    rule_type = Column(String(50), nullable=False, comment="规则类型 position_limit/stop_loss/daily_loss/sector_limit")
    market = Column(Enum(MarketType), nullable=False, comment="适用市场")
    account_id = Column(Integer, ForeignKey("trading_accounts.id"), nullable=True, comment="绑定账户ID，NULL为全局规则")

    # 规则参数（JSON）
    params = Column(Text, nullable=False, comment="规则参数(JSON)")

    is_enabled = Column(Boolean, default=True, comment="是否启用")
    priority = Column(Integer, default=0, comment="优先级，数字越大越优先")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = {'comment': '风控规则表'}

    def __repr__(self):
        return f"<RiskRule {self.name} ({self.rule_type})>"


# 风控事件记录表
class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, nullable=True, comment="触发的规则ID")
    rule_name = Column(String(200), comment="规则名称")
    rule_type = Column(String(50), comment="规则类型")
    market = Column(Enum(MarketType), nullable=False, comment="市场")
    account_id = Column(Integer, nullable=True, comment="账户ID")

    severity = Column(String(20), default="warning", comment="严重级别 info/warning/critical")
    action = Column(String(50), comment="执行动作 none/reduce/close/alert")
    message = Column(Text, comment="事件描述")
    detail = Column(Text, comment="详细信息(JSON)")

    created_at = Column(DateTime, default=func.now(), index=True, comment="触发时间")

    __table_args__ = {'comment': '风控事件记录表'}

    def __repr__(self):
        return f"<RiskEvent {self.rule_name} ({self.severity})>"


# ==================== V1.5 模型 ====================

# AI 对话会话表
class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(50), unique=True, index=True, nullable=False, comment="会话ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    title = Column(String(200), comment="会话标题")
    market = Column(String(10), comment="关联市场")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


# AI 对话消息表
class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(50), ForeignKey("ai_chat_sessions.session_id"), nullable=False, comment="会话ID")
    role = Column(String(20), nullable=False, comment="角色 user/assistant/system")
    content = Column(Text, nullable=False, comment="消息内容")
    metadata_ = Column("metadata", Text, comment="元数据(JSON)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")


# 市场情绪记录表
class MarketSentiment(Base):
    __tablename__ = "market_sentiments"
    id = Column(Integer, primary_key=True, index=True)
    market = Column(String(10), nullable=False, index=True, comment="市场 A/HK/US")
    sentiment_score = Column(Float, comment="情绪分数 -1到1")
    sentiment_label = Column(String(20), comment="情绪标签 bullish/bearish/neutral")
    news_count = Column(Integer, default=0, comment="分析新闻数")
    positive_count = Column(Integer, default=0, comment="正面新闻数")
    negative_count = Column(Integer, default=0, comment="负面新闻数")
    analysis_result = Column(Text, comment="分析结果(JSON)")
    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")


# 异常交易检测记录表
class AnomalyRecord(Base):
    __tablename__ = "anomaly_records"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True, comment="股票代码")
    market = Column(String(10), nullable=False, comment="市场")
    anomaly_type = Column(String(50), nullable=False, comment="异常类型 price_spike/volume_spike/pump_dump/correlation_break")
    severity = Column(String(20), default="medium", comment="严重程度 low/medium/high/critical")
    description = Column(Text, comment="异常描述")
    detail = Column(Text, comment="详细信息(JSON)")
    detected_at = Column(DateTime, default=func.now(), index=True, comment="检测时间")


# 策略归因分析记录表
class StrategyAttribution(Base):
    __tablename__ = "strategy_attributions"
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(String(50), nullable=False, index=True, comment="策略ID")
    strategy_name = Column(String(100), comment="策略名称")
    market = Column(String(10), comment="市场")
    total_return = Column(Float, comment="总收益率")
    alpha = Column(Float, comment="Alpha收益")
    beta_return = Column(Float, comment="Beta收益")
    timing_return = Column(Float, comment="择时收益")
    sector_contribution = Column(Text, comment="行业贡献(JSON)")
    risk_contribution = Column(Text, comment="风险贡献(JSON)")
    timing_analysis = Column(Text, comment="择时分析(JSON)")
    full_report = Column(Text, comment="完整报告(JSON)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")


# ==================== V2.0 模型 ====================

# 租户表
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), unique=True, index=True, nullable=False, comment="租户ID")
    name = Column(String(200), nullable=False, comment="租户名称")
    slug = Column(String(50), unique=True, index=True, comment="租户标识")
    status = Column(String(20), default="active", comment="状态 active/suspended/expired/deleted")
    plan = Column(String(20), default="free", comment="订阅计划 free/basic/pro/enterprise")
    max_users = Column(Integer, default=5, comment="最大用户数")
    max_strategies = Column(Integer, default=10, comment="最大策略数")
    max_api_calls = Column(Integer, default=10000, comment="每月最大API调用数")
    # 联系信息
    contact_email = Column(String(100), comment="联系邮箱")
    phone = Column(String(30), comment="联系电话")
    domain = Column(String(200), comment="自定义域名")
    logo_url = Column(String(500), comment="Logo URL")
    # 功能权限（JSON数组）
    features = Column(Text, comment="功能权限列表(JSON数组)")
    # 白标配置
    whitelabel_config = Column(Text, comment="白标配置(JSON)")
    brand_name = Column(String(200), comment="品牌名称")
    brand_logo = Column(String(500), comment="品牌Logo URL")
    primary_color = Column(String(20), default="#304156", comment="主色调")
    custom_domain = Column(String(200), comment="自定义域名")
    custom_css = Column(Text, comment="自定义CSS")
    # 统计
    current_users = Column(Integer, default=0, comment="当前用户数")
    current_api_calls = Column(Integer, default=0, comment="当月API调用数")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    expires_at = Column(DateTime, comment="到期时间")

    def __repr__(self):
        return f"<Tenant {self.tenant_id} ({self.name})>"


# 插件表
class Plugin(Base):
    __tablename__ = "plugins"
    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(String(50), unique=True, index=True, nullable=False, comment="插件ID")
    name = Column(String(200), nullable=False, comment="插件名称")
    description = Column(Text, comment="插件描述")
    version = Column(String(20), default="1.0.0", comment="版本号")
    author = Column(String(100), comment="作者")
    category = Column(String(50), comment="分类 strategy/indicator/data_source/notification")
    entry_point = Column(String(200), comment="入口文件/函数")
    config_schema = Column(Text, comment="配置Schema(JSON)")
    permissions = Column(Text, comment="所需权限(JSON数组)")
    is_public = Column(Boolean, default=False, comment="是否公开")
    is_verified = Column(Boolean, default=False, comment="是否官方验证")
    status = Column(String(20), default="active", comment="状态 active/disabled/deprecated")
    install_count = Column(Integer, default=0, comment="安装次数")
    rating_avg = Column(Float, default=0, comment="平均评分")
    rating_count = Column(Integer, default=0, comment="评分人数")
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, comment="开发者租户ID")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


# 插件安装记录表
class PluginInstallation(Base):
    __tablename__ = "plugin_installations"
    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(Integer, ForeignKey("plugins.id"), nullable=False, comment="插件ID")
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, comment="租户ID")
    config = Column(Text, comment="安装配置(JSON)")
    status = Column(String(20), default="active", comment="状态 active/disabled")
    installed_at = Column(DateTime, default=func.now(), comment="安装时间")
    __table_args__ = (
        # 每个租户对同一插件只能安装一次
        {'comment': '插件安装记录表'},
    )


# 开放API Key表
class OpenAPIKey(Base):
    __tablename__ = "openapi_keys"
    id = Column(Integer, primary_key=True, index=True)
    key_name = Column(String(200), nullable=False, comment="Key名称")
    name = Column(String(200), comment="Key显示名称（兼容字段）")
    api_key = Column(String(100), unique=True, index=True, nullable=False, comment="API Key")
    api_secret_hash = Column(String(255), comment="API Secret哈希")
    tenant_id = Column(String(50), nullable=False, index=True, comment="租户ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="创建用户ID")
    permissions = Column(Text, comment="权限范围(JSON数组)")
    rate_limit = Column(Integer, default=60, comment="每分钟请求限制")
    is_active = Column(Boolean, default=True, comment="是否激活")
    status = Column(String(20), default="active", comment="状态 active/revoked")
    last_used_at = Column(DateTime, comment="最后使用时间")
    last_rotated_at = Column(DateTime, comment="最后轮换时间")
    total_calls = Column(Integer, default=0, comment="总调用次数")
    expires_at = Column(DateTime, comment="过期时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<OpenAPIKey {self.api_key[:12]}...>"


# API 调用日志表
class APICallLog(Base):
    __tablename__ = "api_call_logs"
    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("openapi_keys.id"), nullable=True, comment="API Key ID")
    tenant_id = Column(String(50), nullable=True, comment="租户ID")
    endpoint = Column(String(200), nullable=False, comment="请求端点")
    method = Column(String(10), nullable=False, comment="HTTP方法")
    status_code = Column(Integer, comment="响应状态码")
    response_time_ms = Column(Integer, comment="响应时间(毫秒)")
    ip = Column(String(50), comment="请求IP")
    ip_address = Column(String(50), comment="请求IP（兼容字段）")
    user_agent = Column(String(500), comment="User-Agent")
    created_at = Column(DateTime, default=func.now(), index=True, comment="请求时间")

    def __repr__(self):
        return f"<APICallLog {self.endpoint} {self.status_code}>"


# 订阅计划表
class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(50), unique=True, index=True, nullable=False, comment="计划ID")
    name = Column(String(100), nullable=False, comment="计划名称")
    description = Column(Text, comment="计划描述")
    price = Column(Float, default=0, comment="价格")
    price_monthly = Column(Float, default=0, comment="月价格")
    price_yearly = Column(Float, default=0, comment="年价格")
    billing_cycle = Column(String(20), default="monthly", comment="默认计费周期 monthly/yearly")
    max_users = Column(Integer, default=5, comment="最大用户数")
    max_strategies = Column(Integer, default=10, comment="最大策略数")
    max_api_calls = Column(Integer, default=10000, comment="每月API调用数")
    max_api_calls_per_minute = Column(Integer, default=60, comment="每分钟API调用数")
    features = Column(Text, comment="功能列表(JSON数组)")
    trial_days = Column(Integer, default=0, comment="试用期天数")
    is_active = Column(Boolean, default=True, comment="是否可用")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<SubscriptionPlan {self.plan_id} ({self.name})>"


# 订阅记录表
class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False, index=True, comment="租户ID")
    plan_id = Column(String(50), nullable=False, comment="计划ID")
    status = Column(String(20), default="active", comment="状态 active/cancelled/expired")
    billing_cycle = Column(String(10), default="monthly", comment="计费周期 monthly/yearly")
    current_period_start = Column(DateTime, nullable=False, comment="当前周期开始")
    current_period_end = Column(DateTime, nullable=False, comment="当前周期结束")
    amount = Column(Float, nullable=False, comment="金额")
    trial_end = Column(DateTime, comment="试用期结束时间")
    cancelled_at = Column(DateTime, comment="取消时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<Subscription {self.tenant_id} -> {self.plan_id}>"


# 用量记录表
class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, comment="租户ID")
    metric = Column(String(50), nullable=False, comment="指标类型 api_calls/strategies/users/storage")
    value = Column(Integer, default=1, comment="使用量")
    period = Column(String(20), nullable=False, comment="周期 2026-04")
    recorded_at = Column(DateTime, default=func.now(), comment="记录时间")
    __table_args__ = (
        {'comment': '用量记录表'},
    )


# 租户月度用量统计表
class TenantUsage(Base):
    __tablename__ = "tenant_usage"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False, index=True, comment="租户ID")
    metric = Column(String(50), nullable=False, comment="指标名称 users/strategies/api_calls")
    value = Column(Integer, default=0, comment="用量值")
    period_start = Column(DateTime, nullable=False, comment="周期开始时间")
    period_end = Column(DateTime, nullable=False, comment="周期结束时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = {'comment': '租户月度用量统计表'}

    def __repr__(self):
        return f"<TenantUsage {self.tenant_id} {self.metric}={self.value}>"


# 租户插件安装表
class TenantPlugin(Base):
    __tablename__ = "tenant_plugins"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False, index=True, comment="租户ID")
    plugin_id = Column(String(50), nullable=False, index=True, comment="插件ID")
    config = Column(Text, comment="插件配置(JSON)")
    status = Column(String(20), default="active", comment="状态 active/uninstalled")
    created_at = Column(DateTime, default=func.now(), comment="安装时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        {'comment': '租户插件安装表'},
    )

    def __repr__(self):
        return f"<TenantPlugin {self.plugin_id} -> {self.tenant_id}>"


# 账单表
class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String(50), unique=True, index=True, nullable=False, comment="账单ID")
    tenant_id = Column(String(50), nullable=False, index=True, comment="租户ID")
    subscription_id = Column(Integer, comment="订阅记录ID")
    plan_id = Column(String(50), nullable=False, comment="计划ID")
    amount = Column(Float, nullable=False, comment="金额")
    billing_cycle = Column(String(20), comment="计费周期 monthly/yearly")
    status = Column(String(20), default="pending", comment="状态 pending/paid/overdue/cancelled")
    period_start = Column(DateTime, comment="周期开始")
    period_end = Column(DateTime, comment="周期结束")
    paid_at = Column(DateTime, comment="支付时间")
    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")

    __table_args__ = {'comment': '账单表'}

    def __repr__(self):
        return f"<Invoice {self.invoice_id} {self.amount}>"


# ==================== V1.8 高可用与灾备模型 ====================

class DatabaseBackup(Base):
    """数据库备份记录表"""
    __tablename__ = "database_backups"
    id = Column(Integer, primary_key=True, index=True)
    backup_id = Column(String(50), unique=True, index=True, nullable=False, comment="备份ID")
    backup_type = Column(String(20), nullable=False, comment="备份类型 full/incremental")
    status = Column(String(20), default="pending", comment="状态 pending/running/completed/failed")
    file_path = Column(String(500), comment="备份文件路径")
    file_size = Column(Integer, comment="文件大小(bytes)")
    duration_seconds = Column(Integer, comment="耗时(秒)")
    tables_count = Column(Integer, comment="表数量")
    rows_count = Column(Integer, comment="总行数")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime, default=func.now(), index=True)

    def __repr__(self):
        return f"<DatabaseBackup {self.backup_id} ({self.status})>"


class ClusterNode(Base):
    """集群节点表"""
    __tablename__ = "cluster_nodes"
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(50), unique=True, index=True, nullable=False, comment="节点ID")
    node_type = Column(String(20), nullable=False, comment="节点类型 primary/replica/worker")
    host = Column(String(200), nullable=False, comment="主机地址")
    port = Column(Integer, default=3306, comment="端口")
    status = Column(String(20), default="unknown", comment="状态 online/offline/degraded/unknown")
    role = Column(String(20), comment="当前角色 master/slave")
    replication_lag = Column(Integer, default=0, comment="复制延迟(秒)")
    last_heartbeat = Column(DateTime, comment="最后心跳时间")
    region = Column(String(50), comment="区域")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ClusterNode {self.node_id} ({self.status})>"


class AlertRule(Base):
    """告警规则表"""
    __tablename__ = "alert_rules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="规则名称")
    metric = Column(String(50), nullable=False, comment="监控指标 cpu/memory/disk/database_latency/error_rate")
    condition = Column(String(20), nullable=False, comment="条件 gt/lt/eq/neq")
    threshold = Column(Float, nullable=False, comment="阈值")
    duration = Column(Integer, default=60, comment="持续时间(秒)")
    severity = Column(String(20), default="warning", comment="严重程度 info/warning/critical")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    notify_channels = Column(Text, comment="通知渠道(JSON数组)")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AlertRule {self.name} ({self.metric} {self.condition} {self.threshold})>"


class SystemAlert(Base):
    """系统告警表"""
    __tablename__ = "system_alerts"
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=True, comment="规则ID")
    rule_name = Column(String(200), comment="规则名称")
    severity = Column(String(20), default="warning", comment="严重程度")
    message = Column(Text, nullable=False, comment="告警消息")
    detail = Column(Text, comment="详细信息(JSON)")
    status = Column(String(20), default="firing", comment="状态 firing/acknowledged/resolved")
    fired_at = Column(DateTime, default=func.now(), index=True, comment="触发时间")
    acknowledged_at = Column(DateTime, comment="确认时间")
    resolved_at = Column(DateTime, comment="解决时间")
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="确认人")

    def __repr__(self):
        return f"<SystemAlert {self.rule_name} ({self.severity})>"


# ==================== V1.9 算法交易增强模型 ====================

class AlgoOrderType(enum.Enum):
    """算法订单类型"""
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"
    SMART = "smart"


class AlgoOrderStatus(enum.Enum):
    """算法订单状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AlgoOrder(Base):
    """算法订单表"""
    __tablename__ = "algo_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True, nullable=False, comment="订单ID")
    algo_type = Column(Enum(AlgoOrderType), nullable=False, comment="算法类型")
    status = Column(Enum(AlgoOrderStatus), default=AlgoOrderStatus.PENDING, comment="状态")
    symbol = Column(String(20), nullable=False, comment="标的代码")
    market = Column(String(10), nullable=False, comment="市场")
    side = Column(String(10), nullable=False, comment="方向 BUY/SELL")
    total_quantity = Column(Float, nullable=False, comment="总数量")
    filled_quantity = Column(Float, default=0, comment="已成交数量")
    avg_fill_price = Column(Float, comment="平均成交价")
    target_price = Column(Float, comment="目标价格")
    params = Column(Text, comment="算法参数(JSON)")
    child_orders = Column(Text, comment="子订单列表(JSON)")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建人")
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AlgoOrder {self.order_id} ({self.algo_type.value if self.algo_type else ''})>"


class AlgoExecution(Base):
    """算法执行明细表"""
    __tablename__ = "algo_executions"
    id = Column(Integer, primary_key=True, index=True)
    algo_order_id = Column(String(50), ForeignKey("algo_orders.order_id"), nullable=False, comment="算法订单ID")
    child_order_id = Column(String(50), comment="子订单ID")
    symbol = Column(String(20), nullable=False, comment="标的代码")
    side = Column(String(10), nullable=False, comment="方向")
    quantity = Column(Float, nullable=False, comment="数量")
    fill_price = Column(Float, comment="成交价")
    fill_time = Column(DateTime, comment="成交时间")
    execution_time_ms = Column(Integer, comment="执行耗时(毫秒)")
    slippage = Column(Float, comment="滑点")
    market_impact = Column(Float, comment="市场冲击")
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<AlgoExecution {self.algo_order_id} {self.quantity}@{self.fill_price}>"


# ==================== V1.7 多市场扩展模型 ====================

class AssetType(enum.Enum):
    """资产类型"""
    STOCK = "stock"
    FUTURES = "futures"
    CRYPTO = "crypto"
    ETF = "etf"
    OPTION = "option"
    FOREX = "forex"


class FuturesContract(Base):
    """期货合约"""
    __tablename__ = "futures_contracts"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30), unique=True, index=True, nullable=False, comment="合约代码")
    name = Column(String(100), nullable=False, comment="合约名称")
    exchange = Column(String(20), nullable=False, comment="交易所 CFFE/SHFE/DCE/CZCE/ICE/CME")
    underlying = Column(String(20), comment="标的代码")
    contract_month = Column(String(10), comment="合约月份")
    multiplier = Column(Float, default=1, comment="合约乘数")
    margin_rate = Column(Float, default=0.1, comment="保证金率")
    tick_size = Column(Float, comment="最小变动价位")
    last_price = Column(Float, comment="最新价")
    change_pct = Column(Float, comment="涨跌幅")
    volume = Column(Float, comment="成交量")
    open_interest = Column(Float, comment="持仓量")
    settlement_price = Column(Float, comment="结算价")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<FuturesContract {self.symbol} ({self.exchange})>"


class CryptoMarket(Base):
    """加密货币市场"""
    __tablename__ = "crypto_markets"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, index=True, nullable=False, comment="交易对 BTC/USDT")
    name = Column(String(50), nullable=False, comment="名称")
    base_currency = Column(String(10), comment="基础货币")
    quote_currency = Column(String(10), default="USDT", comment="计价货币")
    last_price = Column(Float, comment="最新价")
    change_24h = Column(Float, comment="24h涨跌幅")
    high_24h = Column(Float, comment="24h最高")
    low_24h = Column(Float, comment="24h最低")
    volume_24h = Column(Float, comment="24h成交量")
    market_cap = Column(Float, comment="市值")
    circulating_supply = Column(Float, comment="流通量")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CryptoMarket {self.symbol} ({self.name})>"


class ETFInfo(Base):
    """ETF 基金信息"""
    __tablename__ = "etf_info"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, index=True, nullable=False, comment="代码")
    name = Column(String(100), nullable=False, comment="名称")
    market = Column(String(10), nullable=False, comment="市场 A/HK/US")
    nav = Column(Float, comment="净值")
    price = Column(Float, comment="市价")
    premium_rate = Column(Float, comment="溢价率")
    total_assets = Column(Float, comment="总资产")
    expense_ratio = Column(Float, comment="管理费率")
    tracking_index = Column(String(100), comment="跟踪指数")
    top_holdings = Column(Text, comment="前十大持仓(JSON)")
    sector_allocation = Column(Text, comment="行业配置(JSON)")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ETFInfo {self.symbol} ({self.market})>"


class ArbitrageOpportunity(Base):
    """跨市场套利机会"""
    __tablename__ = "arbitrage_opportunities"
    id = Column(Integer, primary_key=True, index=True)
    symbol_a = Column(String(20), nullable=False, comment="标的A代码")
    market_a = Column(String(10), nullable=False, comment="市场A")
    symbol_b = Column(String(20), nullable=False, comment="标的B代码")
    market_b = Column(String(10), nullable=False, comment="市场B")
    spread = Column(Float, comment="价差")
    spread_pct = Column(Float, comment="价差百分比")
    historical_avg_spread = Column(Float, comment="历史平均价差")
    z_score = Column(Float, comment="Z-Score")
    is_profitable = Column(Boolean, default=False, comment="是否有利可图")
    estimated_pnl = Column(Float, comment="预估盈亏")
    confidence = Column(Float, comment="置信度")
    detected_at = Column(DateTime, default=func.now(), index=True, comment="检测时间")

    def __repr__(self):
        return f"<ArbitrageOpportunity {self.symbol_a}/{self.symbol_b}>"


# ==================== V1.6 社区与协作模型 ====================

# 用户资料扩展表
class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, comment="用户ID")
    avatar_url = Column(String(500), comment="头像URL")
    bio = Column(String(500), comment="个人简介")
    expertise = Column(String(200), comment="擅长策略")
    risk_preference = Column(String(20), default="medium", comment="风险偏好 conservative/medium/aggressive")
    total_trades = Column(Integer, default=0, comment="总交易数")
    win_rate = Column(Float, default=0, comment="胜率")
    total_pnl = Column(Float, default=0, comment="总盈亏")
    followers_count = Column(Integer, default=0, comment="粉丝数")
    following_count = Column(Integer, default=0, comment="关注数")
    posts_count = Column(Integer, default=0, comment="帖子数")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = {'comment': '用户资料扩展表'}

    def __repr__(self):
        return f"<UserProfile user_id={self.user_id}>"


# 用户关注关系表
class UserFollow(Base):
    __tablename__ = "user_follows"
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="关注者ID")
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="被关注者ID")
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        # 唯一约束：同一用户不能重复关注
        {'comment': '用户关注关系表'},
    )

    def __repr__(self):
        return f"<UserFollow {self.follower_id}->{self.following_id}>"


# 讨论帖子表
class DiscussionPost(Base):
    __tablename__ = "discussion_posts"
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="作者ID")
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="内容")
    category = Column(String(50), default="general", comment="分类 strategy/market/risk/general/question")
    tags = Column(String(500), comment="标签(JSON数组)")
    likes_count = Column(Integer, default=0, comment="点赞数")
    comments_count = Column(Integer, default=0, comment="评论数")
    views_count = Column(Integer, default=0, comment="浏览数")
    is_pinned = Column(Boolean, default=False, comment="是否置顶")
    is_featured = Column(Boolean, default=False, comment="是否精华")
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = {'comment': '讨论帖子表'}

    def __repr__(self):
        return f"<DiscussionPost {self.title[:30]}>"


# 帖子评论表
class PostComment(Base):
    __tablename__ = "post_comments"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("discussion_posts.id"), nullable=False, comment="帖子ID")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="评论者ID")
    content = Column(Text, nullable=False, comment="评论内容")
    parent_id = Column(Integer, ForeignKey("post_comments.id"), nullable=True, comment="父评论ID")
    likes_count = Column(Integer, default=0, comment="点赞数")
    created_at = Column(DateTime, default=func.now())

    __table_args__ = {'comment': '帖子评论表'}

    def __repr__(self):
        return f"<PostComment post_id={self.post_id}>"


# 帖子点赞表
class PostLike(Base):
    __tablename__ = "post_likes"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("discussion_posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        # 唯一约束：同一用户对同一帖子只能点赞一次
        {'comment': '帖子点赞表'},
    )

    def __repr__(self):
        return f"<PostLike user_id={self.user_id} post_id={self.post_id}>"


# 交易分享表
class TradeShare(Base):
    __tablename__ = "trade_shares"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="分享者ID")
    is_anonymous = Column(Boolean, default=False, comment="是否匿名")
    symbol = Column(String(20), nullable=False, comment="股票代码")
    market = Column(String(10), nullable=False, comment="市场")
    side = Column(String(10), nullable=False, comment="方向 BUY/SELL")
    entry_price = Column(Float, comment="入场价")
    exit_price = Column(Float, comment="出场价")
    quantity = Column(Float, comment="数量")
    pnl = Column(Float, comment="盈亏金额")
    pnl_pct = Column(Float, comment="盈亏比例")
    strategy_name = Column(String(100), comment="策略名称")
    reasoning = Column(Text, comment="交易逻辑")
    screenshot_url = Column(String(500), comment="截图URL")
    likes_count = Column(Integer, default=0, comment="点赞数")
    comments_count = Column(Integer, default=0, comment="评论数")
    created_at = Column(DateTime, default=func.now(), index=True)

    __table_args__ = {'comment': '交易分享表'}

    def __repr__(self):
        return f"<TradeShare {self.symbol} {self.side}>"


# 私信表
class PrivateMessage(Base):
    __tablename__ = "private_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="发送者ID")
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="接收者ID")
    content = Column(Text, nullable=False, comment="消息内容")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, default=func.now(), index=True)

    __table_args__ = {'comment': '私信表'}

    def __repr__(self):
        return f"<PrivateMessage {self.sender_id}->{self.receiver_id}>"


# ==================== 项目分享与导出模型 ====================

class ProjectExport(Base):
    """项目导出记录表"""
    __tablename__ = "project_exports"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="导出文件名称")
    file_path = Column(String(500), comment="导出文件路径")
    file_size = Column(Integer, default=0, comment="文件大小(bytes)")
    status = Column(String(20), default="pending", comment="状态 pending/completed/failed")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建用户ID")
    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")

    __table_args__ = {'comment': '项目导出记录表'}

    def __repr__(self):
        return f"<ProjectExport {self.name} ({self.status})>"


class ShareLink(Base):
    """分享链接表"""
    __tablename__ = "share_links"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(100), unique=True, index=True, nullable=False, comment="分享令牌")
    permission = Column(String(20), default="read", comment="权限 read/edit")
    expires_at = Column(DateTime, nullable=True, comment="过期时间")
    views = Column(Integer, default=0, comment="访问次数")
    is_active = Column(Boolean, default=True, comment="是否有效")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建用户ID")
    created_at = Column(DateTime, default=func.now(), index=True, comment="创建时间")

    __table_args__ = {'comment': '分享链接表'}

    def __repr__(self):
        return f"<ShareLink {self.token[:12]}... ({self.permission})>"


class AccessLog(Base):
    """访问日志表"""
    __tablename__ = "access_logs"
    id = Column(Integer, primary_key=True, index=True)
    share_link_id = Column(Integer, ForeignKey("share_links.id"), nullable=True, comment="分享链接ID")
    visitor_ip = Column(String(50), comment="访客IP")
    visitor_user_agent = Column(String(500), comment="访客User-Agent")
    action = Column(String(100), comment="操作类型")
    created_at = Column(DateTime, default=func.now(), index=True, comment="访问时间")

    __table_args__ = {'comment': '访问日志表'}

    def __repr__(self):
        return f"<AccessLog link={self.share_link_id} {self.action}>"
