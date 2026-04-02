"""
开放 API 路由

路由前缀 /api/v1/open，使用 API Key 认证（非 JWT）。
提供行情数据、交易信号、订单管理、账户信息等开放接口。
"""

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .api_key_service import APIKeyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/open", tags=["开放API"])


# ========== API Key 认证依赖 ==========

def verify_api_key(request: Request, db: Session = Depends(get_db)):
    """
    验证 API Key（FastAPI 依赖）

    从请求头 X-API-Key 读取 API Key，验证其有效性。
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 API Key，请在请求头中提供 X-API-Key",
        )

    key_record = APIKeyService.validate_api_key(db, api_key)
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key 无效、已吊销或已过期",
        )

    # 将 API Key 信息注入请求状态
    request.state.api_key = key_record
    return key_record


# ========== 请求/响应 Schema ==========

class TokenRequest(BaseModel):
    """获取访问令牌请求"""
    api_key: str = Field(..., description="API Key")
    api_secret: str = Field(..., description="API Secret")


class TokenResponse(BaseModel):
    """访问令牌响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class SignalCreateRequest(BaseModel):
    """创建交易信号请求"""
    symbol: str = Field(..., description="股票代码")
    market: str = Field("A", description="市场 A/HK/US")
    side: str = Field(..., description="方向 BUY/SELL")
    strategy_id: Optional[str] = Field(None, description="策略ID")
    strategy_name: Optional[str] = Field(None, description="策略名称")
    signal_type: Optional[str] = Field("OPEN", description="信号类型 OPEN/CLOSE")
    confidence: Optional[float] = Field(None, description="置信度 0-1")
    target_price: Optional[float] = Field(None, description="目标价格")
    stop_loss: Optional[float] = Field(None, description="止损价")
    take_profit: Optional[float] = Field(None, description="止盈价")
    quantity: Optional[float] = Field(None, description="建议数量")
    reason: Optional[str] = Field(None, description="信号理由")


class OrderCreateRequest(BaseModel):
    """创建订单请求"""
    symbol: str = Field(..., description="股票代码")
    market: str = Field("A", description="市场 A/HK/US")
    side: str = Field(..., description="方向 BUY/SELL")
    quantity: float = Field(..., gt=0, description="数量")
    price: Optional[float] = Field(None, description="限价（不填则为市价单）")
    order_type: str = Field("market", description="订单类型 market/limit")
    strategy_id: Optional[str] = Field(None, description="策略ID")


# ========== 接口实现 ==========

@router.post("/auth/token", response_model=TokenResponse)
def get_access_token(
    request: TokenRequest,
    db: Session = Depends(get_db),
):
    """
    获取访问令牌（使用 API Key + Secret）

    验证 API Key 和 Secret 后返回访问令牌。
    """
    from .auth import create_access_token

    key_record = APIKeyService.validate_api_key(db, request.api_key)
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key 无效或已吊销",
        )

    # 验证 Secret
    if not APIKeyService.verify_api_secret(request.api_secret, key_record.api_secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Secret 不匹配",
        )

    # 生成访问令牌
    token_data = {
        "sub": f"api_key:{key_record.id}",
        "tenant_id": key_record.tenant_id,
        "type": "open_api",
    }
    access_token = create_access_token(token_data)

    # 记录 API 调用
    APIKeyService.log_api_call(
        db=db,
        api_key_id=key_record.id,
        endpoint="/api/v1/open/auth/token",
        method="POST",
        status_code=200,
        response_time_ms=0,
    )

    return TokenResponse(access_token=access_token)


@router.get("/market/quotes")
def get_market_quotes(
    symbols: str = Query(..., description="股票代码列表，逗号分隔"),
    market: str = Query("A", description="市场 A/HK/US"),
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    获取行情数据

    根据股票代码列表获取最新行情报价。
    """
    from . import crud

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="请提供至少一个股票代码")

    quotes = []
    for symbol in symbol_list:
        stock = crud.get_stock_info(db, symbol)
        if stock:
            # 获取最新K线数据作为行情
            bars = crud.get_historical_bars(db, symbol, limit=1)
            latest = bars[0] if bars else None
            quotes.append({
                "symbol": symbol,
                "name": stock.name,
                "market": market,
                "price": latest.close if latest else None,
                "volume": latest.volume if latest else None,
                "timestamp": latest.timestamp.isoformat() if latest else None,
            })

    return {"data": quotes}


@router.get("/market/klines")
def get_market_klines(
    symbol: str = Query(..., description="股票代码"),
    market: str = Query("A", description="市场 A/HK/US"),
    bar_type: str = Query("1d", description="K线类型 1d/1m/5m/15m/1h"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000, description="数据条数"),
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    获取K线数据

    根据股票代码和时间范围获取K线数据。
    """
    from . import schemas

    bar_type_enum = schemas.BarType(bar_type)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    bars = crud.get_historical_bars(
        db=db,
        symbol=symbol,
        bar_type=bar_type_enum,
        start_date=start_dt,
        end_date=end_dt,
        limit=limit,
    )

    data = [
        {
            "timestamp": bar.timestamp.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]

    return {"symbol": symbol, "bar_type": bar_type, "data": data}


@router.post("/signal/create")
def create_signal(
    request: SignalCreateRequest,
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    创建交易信号

    通过开放 API 创建交易信号。
    """
    from . import schemas, crud

    signal_data = schemas.TradingSignalCreate(
        symbol=request.symbol,
        market=schemas.MarketType(request.market),
        side=request.side,
        strategy_id=request.strategy_id,
        strategy_name=request.strategy_name,
        signal_type=request.signal_type,
        confidence=request.confidence,
        target_price=request.target_price,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        quantity=request.quantity,
        reason=request.reason,
    )

    signal = crud.create_trading_signal(db, signal_data)

    # 记录 API 调用
    APIKeyService.log_api_call(
        db=db,
        api_key_id=api_key.id,
        endpoint="/api/v1/open/signal/create",
        method="POST",
        status_code=200,
        response_time_ms=0,
    )

    return {"signal_id": signal.id, "status": signal.status}


@router.get("/signal/list")
def list_signals(
    market: Optional[str] = Query(None, description="市场筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    获取信号列表

    分页获取交易信号列表。
    """
    from . import schemas, crud

    market_enum = schemas.MarketType(market) if market else None
    skip = (page - 1) * page_size

    signals = crud.get_trading_signals(
        db=db,
        market=market_enum,
        status=status,
        skip=skip,
        limit=page_size,
    )
    total = crud.count_trading_signals(db=db, market=market_enum, status=status)

    data = [
        {
            "id": s.id,
            "signal_id": s.signal_id,
            "symbol": s.symbol,
            "side": s.side,
            "status": s.status,
            "confidence": s.confidence,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]

    return {"total": total, "page": page, "page_size": page_size, "data": data}


@router.get("/position/list")
def list_positions(
    market: Optional[str] = Query(None, description="市场筛选"),
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    获取持仓列表

    获取当前所有持仓信息。
    """
    from . import schemas, crud

    market_enum = schemas.MarketType(market) if market else None
    positions = crud.get_all_positions(db=db, market=market_enum)

    data = [
        {
            "id": p.id,
            "symbol": p.symbol,
            "quantity": p.quantity,
            "avg_cost": p.avg_cost,
            "current_price": p.current_price,
            "market_value": p.market_value,
            "profit_pct": p.profit_pct,
        }
        for p in positions
    ]

    return {"data": data}


@router.post("/order/create")
def create_order(
    request: OrderCreateRequest,
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    创建订单

    通过开放 API 创建交易订单。
    """
    import uuid
    from . import schemas, crud

    order_id = f"oc_{uuid.uuid4().hex[:12]}"
    amount = request.quantity * (request.price or 0)

    trade_data = schemas.TradeRecordCreate(
        order_id=order_id,
        symbol=request.symbol,
        market=schemas.MarketType(request.market),
        side=request.side,
        quantity=request.quantity,
        price=request.price or 0,
        amount=amount,
        strategy_id=request.strategy_id,
        status="PENDING",
    )

    trade = crud.create_trade_record(db, trade_data)

    # 记录 API 调用
    APIKeyService.log_api_call(
        db=db,
        api_key_id=api_key.id,
        endpoint="/api/v1/open/order/create",
        method="POST",
        status_code=200,
        response_time_ms=0,
    )

    return {
        "order_id": trade.order_id,
        "status": trade.status,
        "message": "订单已提交",
    }


@router.get("/order/status")
def get_order_status(
    order_id: str = Query(..., description="订单ID"),
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    查询订单状态

    根据订单ID查询订单当前状态。
    """
    from . import crud

    # 遍历交易记录查找订单
    trades = crud.get_trade_records(db=db, status=None, skip=0, limit=10000)
    order = None
    for t in trades:
        if t.order_id == order_id:
            order = t
            break

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "price": order.price,
        "amount": order.amount,
        "status": order.status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@router.get("/account/info")
def get_account_info(
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    获取账户信息

    获取当前 API Key 关联的租户账户信息。
    """
    from .tenant_service import TenantService

    tenant = TenantService.get_tenant(db, api_key.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")

    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "status": tenant.status,
        "max_users": tenant.max_users,
        "max_strategies": tenant.max_strategies,
        "max_api_calls": tenant.max_api_calls,
    }


@router.get("/usage")
def get_api_usage(
    period: str = Query("day", description="统计周期 day/week/month"),
    api_key=Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    获取 API 使用统计

    获取当前 API Key 所属租户的 API 调用统计信息。
    """
    usage = APIKeyService.get_api_usage(
        db=db,
        tenant_id=api_key.tenant_id,
        period=period,
    )
    return usage
