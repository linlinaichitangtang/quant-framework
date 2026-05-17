"""
实时行情 API 端点

提供行情订阅和管理接口。
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from typing import Optional, List

from .market_data import market_data_provider, start_market_subscription, stop_market_subscription, TickerData
from .websocket import ws_manager, Channels

router = APIRouter(prefix="/api/v1/market", tags=["market"])


class MarketSubscribeRequest(BaseModel):
    """行情订阅请求"""
    symbols: List[str]
    market: str = "CN"


class MarketTickerResponse(BaseModel):
    """行情数据响应"""
    symbol: str
    market: str
    last_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    amount: float
    change_pct: float
    change_amount: float
    timestamp: str


@router.post("/subscribe")
def subscribe_market(request: MarketSubscribeRequest):
    """
    订阅行情

    订阅后可通过 WebSocket 接收实时行情更新。
    订阅频道: market:ticker
    """
    for symbol in request.symbols:
        start_market_subscription(symbol, request.market)
    return {
        "message": f"已订阅 {len(request.symbols)} 只股票",
        "symbols": request.symbols,
        "market": request.market,
        "websocket_channel": Channels.MARKET_TICKER
    }


@router.post("/unsubscribe")
def unsubscribe_market(request: MarketSubscribeRequest):
    """
    取消订阅行情
    """
    for symbol in request.symbols:
        stop_market_subscription(symbol)
    return {
        "message": f"已取消订阅 {len(request.symbols)} 只股票",
        "symbols": request.symbols
    }


@router.get("/ticker/{symbol}")
def get_ticker(symbol: str, market: str = Query("CN", description="市场: CN/HK/US")) -> MarketTickerResponse:
    """
    获取单只股票实时行情

    如果未订阅，先启动订阅。
    """
    if not market_data_provider.get_current_data(symbol):
        start_market_subscription(symbol, market)

    data = market_data_provider.get_current_data(symbol)
    if not data:
        return MarketTickerResponse(
            symbol=symbol,
            market=market,
            last_price=0,
            open_price=0,
            high_price=0,
            low_price=0,
            volume=0,
            amount=0,
            change_pct=0,
            change_amount=0,
            timestamp=""
        )

    return MarketTickerResponse(**data)


@router.get("/tickers")
def get_tickers(symbols: str = Query(..., description="股票代码列表，逗号分隔")) -> List[MarketTickerResponse]:
    """
    批量获取股票行情

    示例: GET /api/v1/market/tickers?symbols=000001,600000
    """
    result = []
    for symbol in symbols.split(","):
        symbol = symbol.strip()
        data = market_data_provider.get_current_data(symbol)
        if data:
            result.append(MarketTickerResponse(**data))
    return result


@router.get("/watching")
def get_watching_symbols():
    """获取当前关注的所有股票"""
    return {
        "count": len(market_data_provider._watching_symbols),
        "symbols": list(market_data_provider._watching_symbols.keys())
    }