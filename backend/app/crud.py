from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
from datetime import datetime, date

from . import models, schemas


# ========== 股票基础信息 ==========
def get_stock_info(db: Session, symbol: str):
    return db.query(models.StockInfo).filter(models.StockInfo.symbol == symbol).first()


def get_stock_list(db: Session, market: Optional[schemas.MarketType] = None, skip: int = 0, limit: int = 100):
    query = db.query(models.StockInfo)
    if market:
        query = query.filter(models.StockInfo.market == market)
    return query.offset(skip).limit(limit).all()


def create_stock_info(db: Session, stock: schemas.StockInfoCreate):
    db_stock = models.StockInfo(**stock.model_dump())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock


def update_stock_info(db: Session, symbol: str, stock: schemas.StockInfoUpdate):
    db_stock = get_stock_info(db, symbol)
    if db_stock:
        for key, value in stock.model_dump(exclude_unset=True).items():
            setattr(db_stock, key, value)
        db.commit()
        db.refresh(db_stock)
    return db_stock


# ========== 历史行情 ==========
def get_historical_bars(
    db: Session, 
    symbol: str, 
    bar_type: schemas.BarType = schemas.BarType.DAILY,
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None,
    skip: int = 0, 
    limit: int = 1000
):
    query = db.query(models.HistoricalBar).filter(
        models.HistoricalBar.symbol == symbol,
        models.HistoricalBar.bar_type == bar_type
    )
    if start_date:
        query = query.filter(models.HistoricalBar.timestamp >= start_date)
    if end_date:
        query = query.filter(models.HistoricalBar.timestamp <= end_date)
    return query.order_by(models.HistoricalBar.timestamp).offset(skip).limit(limit).all()


def count_historical_bars(
    db: Session, 
    symbol: str, 
    bar_type: schemas.BarType,
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None
):
    query = db.query(models.HistoricalBar).filter(
        models.HistoricalBar.symbol == symbol,
        models.HistoricalBar.bar_type == bar_type
    )
    if start_date:
        query = query.filter(models.HistoricalBar.timestamp >= start_date)
    if end_date:
        query = query.filter(models.HistoricalBar.timestamp <= end_date)
    return query.count()


def create_historical_bar(db: Session, bar: schemas.HistoricalBarCreate):
    db_bar = models.HistoricalBar(**bar.model_dump())
    db.add(db_bar)
    db.commit()
    db.refresh(db_bar)
    return db_bar


def bulk_create_historical_bars(db: Session, bars: List[schemas.HistoricalBarCreate]):
    db_bars = [models.HistoricalBar(**bar.model_dump()) for bar in bars]
    db.bulk_save_objects(db_bars)
    db.commit()
    return db_bars


# ========== 持仓信息 ==========
def get_position(db: Session, position_id: int):
    return db.query(models.Position).filter(models.Position.id == position_id).first()


def get_position_by_symbol(db: Session, symbol: str):
    return db.query(models.Position).filter(models.Position.symbol == symbol).first()


def get_all_positions(db: Session, market: Optional[schemas.MarketType] = None):
    query = db.query(models.Position)
    if market:
        query = query.filter(models.Position.market == market)
    return query.all()


def create_position(db: Session, position: schemas.PositionCreate):
    db_position = models.Position(**position.model_dump())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position


def update_position(db: Session, position_id: int, position: schemas.PositionUpdate):
    db_position = get_position(db, position_id)
    if db_position:
        for key, value in position.model_dump(exclude_unset=True).items():
            setattr(db_position, key, value)
        db.commit()
        db.refresh(db_position)
    return db_position


def delete_position(db: Session, position_id: int):
    db_position = get_position(db, position_id)
    if db_position:
        db.delete(db_position)
        db.commit()
    return db_position


# ========== 交易信号 ==========
def get_trading_signal(db: Session, signal_id: int):
    return db.query(models.TradingSignal).filter(models.TradingSignal.id == signal_id).first()


def get_trading_signal_by_uuid(db: Session, signal_uuid: str):
    return db.query(models.TradingSignal).filter(models.TradingSignal.signal_id == signal_uuid).first()


def get_trading_signals(
    db: Session, 
    market: Optional[schemas.MarketType] = None,
    status: Optional[str] = None,
    side: Optional[str] = None,
    strategy_id: Optional[str] = None,
    skip: int = 0, 
    limit: int = 50
):
    query = db.query(models.TradingSignal)
    if market:
        query = query.filter(models.TradingSignal.market == market)
    if status:
        query = query.filter(models.TradingSignal.status == status)
    if side:
        query = query.filter(models.TradingSignal.side == side)
    if strategy_id:
        query = query.filter(models.TradingSignal.strategy_id == strategy_id)
    return query.order_by(desc(models.TradingSignal.created_at)).offset(skip).limit(limit).all()


def count_trading_signals(
    db: Session, 
    market: Optional[schemas.MarketType] = None,
    status: Optional[str] = None,
    side: Optional[str] = None,
    strategy_id: Optional[str] = None
):
    query = db.query(models.TradingSignal)
    if market:
        query = query.filter(models.TradingSignal.market == market)
    if status:
        query = query.filter(models.TradingSignal.status == status)
    if side:
        query = query.filter(models.TradingSignal.side == side)
    if strategy_id:
        query = query.filter(models.TradingSignal.strategy_id == strategy_id)
    return query.count()


def create_trading_signal(db: Session, signal: schemas.TradingSignalCreate):
    db_signal = models.TradingSignal(**signal.model_dump())
    db.add(db_signal)
    db.commit()
    db.refresh(db_signal)
    return db_signal


def update_trading_signal_status(db: Session, signal_id: int, status: str, executed_at: Optional[datetime] = None):
    db_signal = get_trading_signal(db, signal_id)
    if db_signal:
        db_signal.status = status
        if executed_at:
            db_signal.executed_at = executed_at
        db.commit()
        db.refresh(db_signal)
    return db_signal


# ========== 选股结果 ==========
def get_stock_selections(
    db: Session, 
    market: Optional[schemas.MarketType] = None,
    strategy_id: Optional[str] = None,
    selection_date: Optional[date] = None,
    skip: int = 0, 
    limit: int = 50
):
    query = db.query(models.StockSelection)
    if market:
        query = query.filter(models.StockSelection.market == market)
    if strategy_id:
        query = query.filter(models.StockSelection.strategy_id == strategy_id)
    if selection_date:
        query = query.filter(models.StockSelection.selection_date == selection_date)
    return query.order_by(desc(models.StockSelection.score)).offset(skip).limit(limit).all()


def count_stock_selections(
    db: Session, 
    market: Optional[schemas.MarketType] = None,
    strategy_id: Optional[str] = None,
    selection_date: Optional[date] = None
):
    query = db.query(models.StockSelection)
    if market:
        query = query.filter(models.StockSelection.market == market)
    if strategy_id:
        query = query.filter(models.StockSelection.strategy_id == strategy_id)
    if selection_date:
        query = query.filter(models.StockSelection.selection_date == selection_date)
    return query.count()


def create_stock_selection(db: Session, selection: schemas.StockSelectionCreate):
    db_selection = models.StockSelection(**selection.model_dump())
    db.add(db_selection)
    db.commit()
    db.refresh(db_selection)
    return db_selection


def bulk_create_stock_selections(db: Session, selections: List[schemas.StockSelectionCreate]):
    db_selections = [models.StockSelection(**s.model_dump()) for s in selections]
    db.bulk_save_objects(db_selections)
    db.commit()
    return db_selections


# ========== 交易记录 ==========
def get_trade_record(db: Session, trade_id: int):
    return db.query(models.TradeRecord).filter(models.TradeRecord.id == trade_id).first()


def get_trade_records(
    db: Session, 
    symbol: Optional[str] = None,
    market: Optional[schemas.MarketType] = None,
    side: Optional[str] = None,
    strategy_id: Optional[str] = None,
    signal_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0, 
    limit: int = 50
):
    query = db.query(models.TradeRecord)
    if symbol:
        query = query.filter(models.TradeRecord.symbol == symbol)
    if market:
        query = query.filter(models.TradeRecord.market == market)
    if side:
        query = query.filter(models.TradeRecord.side == side)
    if strategy_id:
        query = query.filter(models.TradeRecord.strategy_id == strategy_id)
    if signal_id:
        query = query.filter(models.TradeRecord.signal_id == signal_id)
    if status:
        query = query.filter(models.TradeRecord.status == status)
    return query.order_by(desc(models.TradeRecord.created_at)).offset(skip).limit(limit).all()


def count_trade_records(
    db: Session, 
    symbol: Optional[str] = None,
    market: Optional[schemas.MarketType] = None,
    side: Optional[str] = None,
    strategy_id: Optional[str] = None,
    signal_id: Optional[int] = None,
    status: Optional[str] = None
):
    query = db.query(models.TradeRecord)
    if symbol:
        query = query.filter(models.TradeRecord.symbol == symbol)
    if market:
        query = query.filter(models.TradeRecord.market == market)
    if side:
        query = query.filter(models.TradeRecord.side == side)
    if strategy_id:
        query = query.filter(models.TradeRecord.strategy_id == strategy_id)
    if signal_id:
        query = query.filter(models.TradeRecord.signal_id == signal_id)
    if status:
        query = query.filter(models.TradeRecord.status == status)
    return query.count()


def create_trade_record(db: Session, trade: schemas.TradeRecordCreate):
    db_trade = models.TradeRecord(**trade.model_dump())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    return db_trade


# ========== 系统日志 ==========
def create_system_log(db: Session, level: str, module: str, message: str, details: Optional[str] = None):
    log = models.SystemLog(level=level, module=module, message=message, details=details)
    db.add(log)
    db.commit()
    return log
