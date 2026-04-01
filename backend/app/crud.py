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


# ========== 股票列表计数 ==========
def count_stock_list(db: Session, market: Optional[schemas.MarketType] = None):
    query = db.query(models.StockInfo)
    if market:
        query = query.filter(models.StockInfo.market == market)
    return query.count()


# ========== 策略配置 ==========
def get_strategy_config(db: Session, strategy_id: str):
    return db.query(models.StrategyConfig).filter(models.StrategyConfig.strategy_id == strategy_id).first()


def get_strategy_configs(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50
):
    query = db.query(models.StrategyConfig)
    if market:
        query = query.filter(models.StrategyConfig.market == market)
    if enabled is not None:
        query = query.filter(models.StrategyConfig.enabled == enabled)
    return query.offset(skip).limit(limit).all()


def count_strategy_configs(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    enabled: Optional[bool] = None
):
    query = db.query(models.StrategyConfig)
    if market:
        query = query.filter(models.StrategyConfig.market == market)
    if enabled is not None:
        query = query.filter(models.StrategyConfig.enabled == enabled)
    return query.count()


def create_strategy_config(db: Session, config: schemas.StrategyConfigCreate):
    db_config = models.StrategyConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


def update_strategy_config(db: Session, strategy_id: str, config: schemas.StrategyConfigUpdate):
    db_config = get_strategy_config(db, strategy_id)
    if db_config:
        for key, value in config.model_dump(exclude_unset=True).items():
            setattr(db_config, key, value)
        db.commit()
        db.refresh(db_config)
    return db_config


def delete_strategy_config(db: Session, strategy_id: str):
    db_config = get_strategy_config(db, strategy_id)
    if db_config:
        db.delete(db_config)
        db.commit()
    return db_config


# ========== 用户管理 ==========
def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 50):
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, username: str, email: str, hashed_password: str,
                display_name: Optional[str] = None, role: models.UserRole = models.UserRole.USER):
    db_user = models.User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        display_name=display_name or username,
        role=role,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, **kwargs):
    db_user = get_user_by_id(db, user_id)
    if db_user:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user


def update_user_last_login(db: Session, user_id: int):
    from datetime import datetime
    return update_user(db, user_id, last_login=datetime.now())


def init_default_admin(db: Session):
    """初始化默认管理员账户（如果不存在）"""
    from .auth import get_password_hash
    admin = get_user_by_username(db, "admin")
    if not admin:
        admin = create_user(
            db=db,
            username="admin",
            email="admin@openclaw.com",
            hashed_password=get_password_hash("admin123"),
            display_name="管理员",
            role=models.UserRole.ADMIN,
        )
        return admin
    return None


# ========== 通知历史 ==========
def create_notification_history(
    db: Session,
    title: str,
    content: str,
    channel: str,
    level: str = "info",
    recipients: Optional[list] = None,
    data: Optional[dict] = None
):
    import json
    notif = models.NotificationHistory(
        title=title,
        content=content,
        channel=channel,
        level=models.NotificationLevel(level),
        recipients=json.dumps(recipients) if recipients else None,
        data=json.dumps(data) if data else None,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def get_notifications(
    db: Session,
    is_read: Optional[bool] = None,
    channel: Optional[str] = None,
    level: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    query = db.query(models.NotificationHistory)
    if is_read is not None:
        query = query.filter(models.NotificationHistory.is_read == is_read)
    if channel:
        query = query.filter(models.NotificationHistory.channel == channel)
    if level:
        query = query.filter(models.NotificationHistory.level == level)
    return query.order_by(models.NotificationHistory.created_at.desc()).offset(skip).limit(limit).all()


def count_notifications(
    db: Session,
    is_read: Optional[bool] = None,
    channel: Optional[str] = None
):
    query = db.query(models.NotificationHistory)
    if is_read is not None:
        query = query.filter(models.NotificationHistory.is_read == is_read)
    if channel:
        query = query.filter(models.NotificationHistory.channel == channel)
    return query.count()


def mark_notification_read(db: Session, notification_id: int):
    notif = db.query(models.NotificationHistory).filter(
        models.NotificationHistory.id == notification_id
    ).first()
    if notif:
        notif.is_read = True
        db.commit()
    return notif


def mark_all_notifications_read(db: Session):
    db.query(models.NotificationHistory).filter(
        models.NotificationHistory.is_read == False
    ).update({"is_read": True})
    db.commit()


# ========== 回测结果 ==========
def get_backtest_result(db: Session, backtest_id: int):
    return db.query(models.BacktestResult).filter(models.BacktestResult.id == backtest_id).first()


def get_backtest_results(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    strategy_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    query = db.query(models.BacktestResult)
    if market:
        query = query.filter(models.BacktestResult.market == market)
    if strategy_type:
        query = query.filter(models.BacktestResult.strategy_type == strategy_type)
    if status:
        query = query.filter(models.BacktestResult.status == status)
    return query.order_by(desc(models.BacktestResult.created_at)).offset(skip).limit(limit).all()


def count_backtest_results(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    strategy_type: Optional[str] = None,
    status: Optional[str] = None
):
    query = db.query(models.BacktestResult)
    if market:
        query = query.filter(models.BacktestResult.market == market)
    if strategy_type:
        query = query.filter(models.BacktestResult.strategy_type == strategy_type)
    if status:
        query = query.filter(models.BacktestResult.status == status)
    return query.count()


def create_backtest_result(db: Session, **kwargs) -> models.BacktestResult:
    db_result = models.BacktestResult(**kwargs)
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


def update_backtest_result(db: Session, backtest_id: int, **kwargs):
    db_result = get_backtest_result(db, backtest_id)
    if db_result:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_result, key, value)
        db.commit()
        db.refresh(db_result)
    return db_result


def delete_backtest_result(db: Session, backtest_id: int):
    db_result = get_backtest_result(db, backtest_id)
    if db_result:
        db.delete(db_result)
        db.commit()
    return db_result


def get_backtest_trades(db: Session, backtest_id: int):
    return db.query(models.BacktestTrade).filter(
        models.BacktestTrade.backtest_id == backtest_id
    ).order_by(models.BacktestTrade.date).all()


def create_backtest_trades(db: Session, backtest_id: int, trades: list):
    db_trades = []
    for t in trades:
        db_trade = models.BacktestTrade(
            backtest_id=backtest_id,
            date=t.get("date", ""),
            action=t.get("action", ""),
            code=t.get("code", ""),
            price=t.get("price", 0),
            shares=int(t.get("shares", 0)),
            cost=t.get("cost") or t.get("proceeds"),
            commission=t.get("commission", 0),
            stamp_tax=t.get("stamp_tax", 0),
            pnl=t.get("pnl"),
            pnl_pct=t.get("pnl_pct"),
        )
        db.add(db_trade)
        db_trades.append(db_trade)
    db.commit()
    for t in db_trades:
        db.refresh(t)
    return db_trades


# ========== 策略模板 ==========
def get_template(db: Session, template_id: int):
    return db.query(models.StrategyTemplate).filter(
        models.StrategyTemplate.id == template_id,
        models.StrategyTemplate.status == "active"
    ).first()


def get_my_templates(
    db: Session,
    author_id: int,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    query = db.query(models.StrategyTemplate).filter(
        models.StrategyTemplate.author_id == author_id,
        models.StrategyTemplate.status == "active"
    )
    if category:
        query = query.filter(models.StrategyTemplate.category == category)
    return query.order_by(desc(models.StrategyTemplate.updated_at)).offset(skip).limit(limit).all()


def count_my_templates(db: Session, author_id: int, category: Optional[str] = None):
    query = db.query(models.StrategyTemplate).filter(
        models.StrategyTemplate.author_id == author_id,
        models.StrategyTemplate.status == "active"
    )
    if category:
        query = query.filter(models.StrategyTemplate.category == category)
    return query.count()


def get_market_templates(
    db: Session,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "install_count",
    skip: int = 0,
    limit: int = 50
):
    query = db.query(models.StrategyTemplate).filter(
        models.StrategyTemplate.is_public == True,
        models.StrategyTemplate.status == "active"
    )
    if category:
        query = query.filter(models.StrategyTemplate.category == category)
    if search:
        query = query.filter(models.StrategyTemplate.name.contains(search))

    if sort_by == "rating":
        query = query.order_by(desc(models.StrategyTemplate.rating_avg))
    elif sort_by == "newest":
        query = query.order_by(desc(models.StrategyTemplate.created_at))
    else:
        query = query.order_by(desc(models.StrategyTemplate.install_count))

    return query.offset(skip).limit(limit).all()


def count_market_templates(db: Session, category: Optional[str] = None, search: Optional[str] = None):
    query = db.query(models.StrategyTemplate).filter(
        models.StrategyTemplate.is_public == True,
        models.StrategyTemplate.status == "active"
    )
    if category:
        query = query.filter(models.StrategyTemplate.category == category)
    if search:
        query = query.filter(models.StrategyTemplate.name.contains(search))
    return query.count()


def create_template(db: Session, **kwargs) -> models.StrategyTemplate:
    db_template = models.StrategyTemplate(**kwargs)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    # 创建初始版本
    version = models.TemplateVersion(
        template_id=db_template.id,
        version=1,
        config=kwargs.get("config", "{}"),
        changelog="初始版本",
    )
    db.add(version)
    db.commit()
    return db_template


def update_template(db: Session, template_id: int, **kwargs):
    db_template = get_template(db, template_id)
    if not db_template:
        return None

    config_changed = "config" in kwargs and kwargs["config"] != db_template.config
    for key, value in kwargs.items():
        if value is not None:
            setattr(db_template, key, value)

    if config_changed:
        db_template.version += 1
        version = models.TemplateVersion(
            template_id=db_template.id,
            version=db_template.version,
            config=kwargs["config"],
            changelog=f"更新至 v{db_template.version}",
        )
        db.add(version)

    db.commit()
    db.refresh(db_template)
    return db_template


def delete_template(db: Session, template_id: int):
    db_template = get_template(db, template_id)
    if db_template:
        db_template.status = "archived"
        db.commit()
        db.refresh(db_template)
    return db_template


def install_template(db: Session, template_id: int):
    """安装模板（增加安装计数）"""
    db_template = get_template(db, template_id)
    if db_template:
        db_template.install_count = (db_template.install_count or 0) + 1
        db.commit()
        db.refresh(db_template)
    return db_template


def rate_template(db: Session, template_id: int, score: int):
    """更新模板评分（简单平均）"""
    db_template = get_template(db, template_id)
    if not db_template:
        return None
    old_avg = db_template.rating_avg or 0
    old_count = db_template.rating_count or 0
    new_count = old_count + 1
    new_avg = (old_avg * old_count + score) / new_count
    db_template.rating_avg = round(new_avg, 2)
    db_template.rating_count = new_count
    db.commit()
    db.refresh(db_template)
    return db_template


# ========== 期权组合持仓 ==========
def get_option_positions(db: Session, status: Optional[str] = None):
    query = db.query(models.OptionPosition)
    if status:
        query = query.filter(models.OptionPosition.status == status)
    return query.order_by(desc(models.OptionPosition.opened_at)).all()


def create_option_position(db: Session, **kwargs) -> models.OptionPosition:
    db_pos = models.OptionPosition(**kwargs)
    db.add(db_pos)
    db.commit()
    db.refresh(db_pos)
    return db_pos


def delete_option_position(db: Session, position_id: int):
    db_pos = db.query(models.OptionPosition).filter(
        models.OptionPosition.id == position_id
    ).first()
    if db_pos:
        db.delete(db_pos)
        db.commit()
    return db_pos


# ========== 交易账户管理 ==========
def get_trading_accounts(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    status: Optional[str] = None,
):
    query = db.query(models.TradingAccount)
    if market:
        query = query.filter(models.TradingAccount.market == market)
    if status:
        query = query.filter(models.TradingAccount.status == status)
    return query.order_by(desc(models.TradingAccount.created_at)).all()


def get_trading_account(db: Session, account_id: int):
    return db.query(models.TradingAccount).filter(models.TradingAccount.id == account_id).first()


def create_trading_account(db: Session, **kwargs) -> models.TradingAccount:
    db_account = models.TradingAccount(**kwargs)
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account


def update_trading_account(db: Session, account_id: int, **kwargs):
    db_account = get_trading_account(db, account_id)
    if db_account:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_account, key, value)
        db.commit()
        db.refresh(db_account)
    return db_account


def delete_trading_account(db: Session, account_id: int):
    db_account = get_trading_account(db, account_id)
    if db_account:
        db.delete(db_account)
        db.commit()
    return db_account


def set_default_account(db: Session, account_id: int):
    """设置默认账户（先取消其他默认，再设置当前）"""
    db_account = get_trading_account(db, account_id)
    if not db_account:
        return None
    # 取消所有账户的默认状态
    db.query(models.TradingAccount).filter(
        models.TradingAccount.is_default == True
    ).update({"is_default": False})
    # 设置当前账户为默认
    db_account.is_default = True
    db.commit()
    db.refresh(db_account)
    return db_account


# ========== 风控规则管理 ==========
def get_risk_rules(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    account_id: Optional[int] = None,
    enabled_only: bool = False,
):
    query = db.query(models.RiskRule)
    if market:
        query = query.filter(models.RiskRule.market == market)
    if account_id is not None:
        query = query.filter(
            (models.RiskRule.account_id == account_id) | (models.RiskRule.account_id.is_(None))
        )
    if enabled_only:
        query = query.filter(models.RiskRule.is_enabled == True)
    return query.order_by(desc(models.RiskRule.priority)).all()


def get_risk_rule(db: Session, rule_id: int):
    return db.query(models.RiskRule).filter(models.RiskRule.id == rule_id).first()


def create_risk_rule(db: Session, **kwargs) -> models.RiskRule:
    db_rule = models.RiskRule(**kwargs)
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


def update_risk_rule(db: Session, rule_id: int, **kwargs):
    db_rule = get_risk_rule(db, rule_id)
    if db_rule:
        for key, value in kwargs.items():
            if value is not None:
                setattr(db_rule, key, value)
        db.commit()
        db.refresh(db_rule)
    return db_rule


def delete_risk_rule(db: Session, rule_id: int):
    db_rule = get_risk_rule(db, rule_id)
    if db_rule:
        db.delete(db_rule)
        db.commit()
    return db_rule


# ========== 风控事件记录 ==========
def create_risk_event(db: Session, **kwargs) -> models.RiskEvent:
    db_event = models.RiskEvent(**kwargs)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def get_risk_events(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    account_id: Optional[int] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    query = db.query(models.RiskEvent)
    if market:
        query = query.filter(models.RiskEvent.market == market)
    if account_id is not None:
        query = query.filter(models.RiskEvent.account_id == account_id)
    if severity:
        query = query.filter(models.RiskEvent.severity == severity)
    return query.order_by(desc(models.RiskEvent.created_at)).offset(skip).limit(limit).all()


def count_risk_events(
    db: Session,
    market: Optional[schemas.MarketType] = None,
    account_id: Optional[int] = None,
    severity: Optional[str] = None,
) -> int:
    query = db.query(models.RiskEvent)
    if market:
        query = query.filter(models.RiskEvent.market == market)
    if account_id is not None:
        query = query.filter(models.RiskEvent.account_id == account_id)
    if severity:
        query = query.filter(models.RiskEvent.severity == severity)
    return query.count()
