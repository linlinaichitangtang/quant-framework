import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
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
