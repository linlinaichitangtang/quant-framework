from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date

from .database import get_db
from . import crud, schemas, models
from .fmz_client import FMZClient


router = APIRouter(prefix="/api/v1", tags=["api"])


# ========== 股票信息 ==========
@router.get("/stocks", response_model=schemas.PaginatedResponse[schemas.StockInfoResponse])
def get_stocks(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    data = crud.get_stock_list(db, market=market, skip=skip, limit=page_size)
    total = len(data)  # 简化版，实际应该单独count
    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=data
    )


@router.get("/stocks/{symbol}", response_model=schemas.StockInfoResponse)
def get_stock(symbol: str, db: Session = Depends(get_db)):
    return crud.get_stock_info(db, symbol)


# ========== 历史行情 ==========
@router.get("/bars/{symbol}", response_model=schemas.PaginatedResponse[schemas.HistoricalBarResponse])
def get_bars(
    symbol: str,
    bar_type: schemas.BarType = Query(schemas.BarType.DAILY),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1),
    page_size: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    data = crud.get_historical_bars(
        db, symbol=symbol, bar_type=bar_type, 
        start_date=start_date, end_date=end_date,
        skip=skip, limit=page_size
    )
    total = crud.count_historical_bars(
        db, symbol=symbol, bar_type=bar_type,
        start_date=start_date, end_date=end_date
    )
    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=data
    )


# ========== 持仓查询 ==========
@router.get("/positions", response_model=list[schemas.PositionResponse])
def get_positions(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    db: Session = Depends(get_db)
):
    return crud.get_all_positions(db, market=market)


@router.get("/positions/{position_id}", response_model=schemas.PositionResponse)
def get_position(position_id: int, db: Session = Depends(get_db)):
    return crud.get_position(db, position_id)


# ========== 选股结果 ==========
@router.get("/selections", response_model=schemas.PaginatedResponse[schemas.StockSelectionResponse])
def get_stock_selections(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    strategy_id: Optional[str] = Query(None, description="策略ID"),
    selection_date: Optional[date] = Query(None, description="选股日期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    data = crud.get_stock_selections(
        db, market=market, strategy_id=strategy_id, 
        selection_date=selection_date, skip=skip, limit=page_size
    )
    total = crud.count_stock_selections(
        db, market=market, strategy_id=strategy_id, selection_date=selection_date
    )
    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=data
    )


# ========== 交易信号 ==========
@router.get("/signals", response_model=schemas.PaginatedResponse[schemas.TradingSignalResponse])
def get_trading_signals(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    status: Optional[str] = Query(None, description="状态"),
    side: Optional[str] = Query(None, description="BUY/SELL"),
    strategy_id: Optional[str] = Query(None, description="策略ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    data = crud.get_trading_signals(
        db, market=market, status=status, side=side, 
        strategy_id=strategy_id, skip=skip, limit=page_size
    )
    total = crud.count_trading_signals(
        db, market=market, status=status, side=side, strategy_id=strategy_id
    )
    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=data
    )


@router.get("/signals/{signal_id}", response_model=schemas.TradingSignalResponse)
def get_trading_signal(signal_id: int, db: Session = Depends(get_db)):
    return crud.get_trading_signal(db, signal_id)


@router.post("/signals", response_model=schemas.TradingSignalResponse)
def create_trading_signal(
    signal: schemas.TradingSignalCreate,
    db: Session = Depends(get_db)
):
    return crud.create_trading_signal(db, signal)


# ========== 交易记录 ==========
@router.get("/trades", response_model=schemas.PaginatedResponse[schemas.TradeRecordResponse])
def get_trade_records(
    symbol: Optional[str] = Query(None, description="股票代码"),
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    side: Optional[str] = Query(None, description="BUY/SELL"),
    strategy_id: Optional[str] = Query(None, description="策略ID"),
    signal_id: Optional[int] = Query(None, description="信号ID"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    data = crud.get_trade_records(
        db, symbol=symbol, market=market, side=side, strategy_id=strategy_id,
        signal_id=signal_id, status=status, skip=skip, limit=page_size
    )
    total = crud.count_trade_records(
        db, symbol=symbol, market=market, side=side, strategy_id=strategy_id,
        signal_id=signal_id, status=status
    )
    return schemas.PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=data
    )


@router.post("/trades", response_model=schemas.TradeRecordResponse)
def create_trade_record(
    trade: schemas.TradeRecordCreate,
    db: Session = Depends(get_db)
):
    return crud.create_trade_record(db, trade)


# ========== 统计概览 ==========
@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """获取账户概览信息"""
    positions = crud.get_all_positions(db)
    total_market_value = sum(p.market_value for p in positions if p.market_value)
    total_profit = sum(p.profit_amount for p in positions if p.profit_amount)
    
    recent_trades = crud.get_trade_records(db, limit=10)
    pending_signals = crud.get_trading_signals(db, status="PENDING", limit=10)
    
    return {
        "total_positions": len(positions),
        "total_market_value": total_market_value,
        "total_unrealized_profit": total_profit,
        "pending_signals_count": len(pending_signals),
        "recent_trades": recent_trades
    }


# ========== FMZ执行 ==========
@router.post("/fmz/execute/{signal_id}", response_model=schemas.FMZExecuteResponse)
def execute_signal_on_fmz(
    signal_id: int,
    request: schemas.FMZExecuteRequest = None,
    db: Session = Depends(get_db)
):
    """将交易信号发送到FMZ执行"""
    signal = crud.get_trading_signal(db, signal_id)
    if not signal:
        return schemas.FMZExecuteResponse(
            success=False,
            message=f"信号 {signal_id} 不存在"
        )
    
    client = FMZClient(
        api_key=request.api_key if request else None,
        secret_key=request.secret_key if request else None,
        cid=request.cid if request else None
    )
    
    result = client.execute_signal(signal)
    
    if result.success:
        # 更新信号状态
        crud.update_trading_signal_status(db, signal_id, "EXECUTED", executed_at=datetime.now())
        # 创建交易记录
        from app.schemas import TradeRecordCreate
        side = "BUY" if signal.side.upper() == "BUY" else "SELL"
        trade = TradeRecordCreate(
            symbol=signal.symbol,
            market=signal.market,
            side=side,
            quantity=signal.quantity if signal.quantity else 0,
            price=result.data.get("filled_price", signal.target_price),
            amount=(signal.quantity if signal.quantity else 0) * (result.data.get("filled_price", signal.target_price)),
            strategy_id=signal.strategy_id,
            strategy_name=signal.strategy_name,
            signal_id=signal.id,
            fmz_order_id=result.order_id,
            status="FILLED"
        )
        crud.create_trade_record(db, trade)
    
    return result


@router.get("/fmz/account")
def get_fmz_account():
    """获取FMZ账户信息"""
    client = FMZClient()
    return client.get_account_info()


@router.get("/fmz/positions/{exchange}")
def get_fmz_positions(exchange: str):
    """获取FMZ持仓信息"""
    client = FMZClient()
    return client.get_position(exchange)
