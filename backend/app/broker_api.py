"""
券商适配器 API 端点

提供多券商切换和管理接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .broker_adapter import BrokerAdapterManager, BrokerType, BrokerAdapter
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/broker", tags=["broker"])


class BrokerConfigRequest(BaseModel):
    """券商配置请求"""
    broker_type: str = Field(..., description="券商类型: fmz, futu, ib")
    config: Dict[str, Any] = Field(..., description="券商配置")


class BrokerSwitchRequest(BaseModel):
    """切换券商请求"""
    broker_type: str = Field(..., description="目标券商类型")


class OrderRequest(BaseModel):
    """下单请求"""
    symbol: str = Field(..., description="股票代码")
    market: str = Field(..., description="市场: CN/HK/US")
    side: str = Field(..., description="方向: buy/sell")
    order_type: str = Field("market", description="订单类型: market/limit")
    quantity: int = Field(..., gt=0, description="数量")
    price: Optional[float] = Field(None, description="限价")
    stop_price: Optional[float] = Field(None, description="止损价")
    strategy_id: Optional[str] = Field(None, description="策略ID")


class PositionResponse(BaseModel):
    """持仓响应"""
    symbol: str
    market: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    profit_amount: float
    profit_pct: float


class AccountInfoResponse(BaseModel):
    """账户信息响应"""
    broker: str
    account_id: str
    total_assets: float
    cash: float
    market_value: float
    buying_power: float
    positions: List[PositionResponse]


@router.get("/list")
def list_brokers(current_user: dict = Depends(get_current_user)):
    """获取已注册的券商列表"""
    return {
        "registered": BrokerAdapterManager.list_registered(),
        "active": BrokerAdapterManager.get_active_broker()
    }


@router.post("/config")
def configure_broker(
    request: BrokerConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    配置券商

    不同的券商需要不同的配置：
    - fmz: api_key, secret_key
    - futu: host, port, trd_env
    - ib: host, port, client_id
    """
    try:
        broker_type = BrokerType(request.broker_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的券商类型: {request.broker_type}")

    adapter = BrokerAdapterManager.get_adapter(broker_type)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"券商 {request.broker_type} 未注册")

    # 更新配置
    adapter.config.update(request.config)

    return {"message": f"券商 {request.broker_type} 配置已更新"}


@router.post("/switch")
def switch_broker(
    request: BrokerSwitchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    切换活跃券商

    切换后所有交易都会使用新的券商执行。
    """
    try:
        broker_type = BrokerType(request.broker_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的券商类型: {request.broker_type}")

    success = BrokerAdapterManager.set_active(broker_type)
    if not success:
        raise HTTPException(status_code=500, detail="券商切换失败")

    return {"message": f"已切换到券商: {request.broker_type}"}


@router.get("/active")
def get_active_broker(current_user: dict = Depends(get_current_user)):
    """获取当前活跃的券商"""
    active = BrokerAdapterManager.get_active_broker()
    if not active:
        return {"active": None, "message": "没有活跃的券商"}
    return {"active": active}


@router.post("/connect")
def connect_broker(
    broker_type: str = Field(..., description="券商类型"),
    current_user: dict = Depends(get_current_user)
):
    """连接券商"""
    try:
        bt = BrokerType(broker_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的券商类型: {broker_type}")

    adapter = BrokerAdapterManager.get_adapter(bt)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"券商 {broker_type} 未注册")

    if adapter.is_connected():
        return {"message": f"券商 {broker_type} 已连接"}

    success = adapter.connect()
    if not success:
        raise HTTPException(status_code=500, detail=f"券商 {broker_type} 连接失败")

    return {"message": f"券商 {broker_type} 连接成功"}


@router.post("/disconnect")
def disconnect_broker(
    broker_type: str = Field(..., description="券商类型"),
    current_user: dict = Depends(get_current_user)
):
    """断开券商连接"""
    try:
        bt = BrokerType(broker_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的券商类型: {broker_type}")

    adapter = BrokerAdapterManager.get_adapter(bt)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"券商 {broker_type} 未注册")

    adapter.disconnect()
    return {"message": f"券商 {broker_type} 已断开"}


@router.post("/order")
def place_order(
    request: OrderRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    下单交易

    使用当前活跃的券商执行。
    """
    from .broker_adapter import OrderRequest as BrokerOrderRequest, OrderResponse

    adapter = BrokerAdapterManager.get_active_adapter()
    if not adapter:
        raise HTTPException(status_code=400, detail="没有活跃的券商，请先连接")

    broker_order = BrokerOrderRequest(
        symbol=request.symbol,
        market=request.market,
        side=request.side,
        order_type=request.order_type,
        quantity=request.quantity,
        price=request.price,
        stop_price=request.stop_price,
        strategy_id=request.strategy_id
    )

    result = adapter.place_order(broker_order)

    return {
        "success": result.success,
        "order_id": result.order_id,
        "message": result.message,
        "filled_quantity": result.filled_quantity,
        "filled_price": result.filled_price
    }


@router.get("/positions", response_model=List[PositionResponse])
def get_positions(current_user: dict = Depends(get_current_user)):
    """获取当前持仓"""
    adapter = BrokerAdapterManager.get_active_adapter()
    if not adapter:
        raise HTTPException(status_code=400, detail="没有活跃的券商")

    positions = adapter.get_positions()
    return [
        PositionResponse(
            symbol=p.symbol,
            market=p.market,
            quantity=p.quantity,
            avg_cost=p.avg_cost,
            current_price=p.current_price,
            market_value=p.market_value,
            profit_amount=p.profit_amount,
            profit_pct=p.profit_pct
        )
        for p in positions
    ]


@router.get("/account", response_model=AccountInfoResponse)
def get_account_info(current_user: dict = Depends(get_current_user)):
    """获取账户信息"""
    adapter = BrokerAdapterManager.get_active_adapter()
    if not adapter:
        raise HTTPException(status_code=400, detail="没有活跃的券商")

    info = adapter.get_account_info()
    return AccountInfoResponse(
        broker=info.broker,
        account_id=info.account_id,
        total_assets=info.total_assets,
        cash=info.cash,
        market_value=info.market_value,
        buying_power=info.buying_power,
        positions=[
            PositionResponse(
                symbol=p.symbol,
                market=p.market,
                quantity=p.quantity,
                avg_cost=p.avg_cost,
                current_price=p.current_price,
                market_value=p.market_value,
                profit_amount=p.profit_amount,
                profit_pct=p.profit_pct
            )
            for p in info.positions
        ]
    )


@router.get("/quote/{market}/{symbol}")
def get_quote(
    market: str,
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """获取实时行情"""
    adapter = BrokerAdapterManager.get_active_adapter()
    if not adapter:
        raise HTTPException(status_code=400, detail="没有活跃的券商")

    quote = adapter.get_quote(symbol, market)
    if not quote:
        raise HTTPException(status_code=404, detail="行情获取失败")

    return quote