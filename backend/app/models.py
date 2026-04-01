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
