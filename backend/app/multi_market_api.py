"""
V1.7 多市场扩展 API 端点 — 期货、加密货币、ETF、跨市场套利、全球时区
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from .database import get_db
from .multi_market_service import MultiMarketService


router = APIRouter(prefix="/api/v1/multi-market", tags=["多市场扩展"])


# ==================== 期货相关 ====================

@router.get("/futures/contracts")
def get_futures_contracts(
    exchange: Optional[str] = Query(None, description="交易所 CFFE/SHFE/DCE/CZCE"),
    underlying: Optional[str] = Query(None, description="标的代码"),
    db: Session = Depends(get_db),
):
    """获取期货合约列表"""
    contracts = MultiMarketService.get_futures_contracts(db, exchange, underlying)
    return {"total": len(contracts), "contracts": contracts}


@router.get("/futures/quote/{symbol}")
def get_futures_quote(
    symbol: str,
    exchange: Optional[str] = Query(None, description="交易所"),
):
    """获取期货行情"""
    result = MultiMarketService.get_futures_quote(symbol, exchange)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/futures/margin")
def calculate_futures_margin(data: dict):
    """计算期货保证金"""
    required_fields = ["symbol", "quantity", "price"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=422, detail=f"缺少必填字段: {field}")
    result = MultiMarketService.calculate_futures_margin(
        symbol=data["symbol"],
        quantity=data["quantity"],
        price=data["price"],
        leverage=data.get("leverage", 1.0),
    )
    return result


# ==================== 加密货币相关 ====================

@router.get("/crypto/markets")
def get_crypto_markets():
    """获取加密货币市场列表"""
    markets = MultiMarketService.get_crypto_markets()
    return {"total": len(markets), "markets": markets}


@router.get("/crypto/quote/{symbol}")
def get_crypto_quote(symbol: str):
    """获取加密货币行情"""
    result = MultiMarketService.get_crypto_quote(symbol)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/crypto/klines/{symbol}")
def get_crypto_klines(
    symbol: str,
    interval: str = Query("1h", description="时间间隔 1m/5m/15m/1h/4h/1d"),
    limit: int = Query(100, ge=1, le=1000, description="数据条数"),
):
    """获取加密货币K线数据"""
    klines = MultiMarketService.get_crypto_klines(symbol, interval, limit)
    if not klines:
        raise HTTPException(status_code=404, detail="交易对不存在或无数据")
    return {"symbol": symbol, "interval": interval, "total": len(klines), "klines": klines}


# ==================== ETF 相关 ====================

@router.get("/etf/list")
def get_etf_list(
    market: Optional[str] = Query(None, description="市场 A/HK/US"),
):
    """获取 ETF 基金列表"""
    etfs = MultiMarketService.get_etf_list(market)
    return {"total": len(etfs), "etfs": etfs}


@router.get("/etf/detail/{symbol}")
def get_etf_detail(
    symbol: str,
    market: Optional[str] = Query(None, description="市场 A/HK/US"),
):
    """获取 ETF 详情（含净值/溢价率/持仓）"""
    result = MultiMarketService.get_etf_detail(symbol, market)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ==================== 市场时间 ====================

@router.get("/market-hours/{market}")
def get_market_hours(
    market: str,
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
):
    """获取市场交易时间（全球时区处理）"""
    result = MultiMarketService.get_market_hours(market, date)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/market-status")
def get_market_status():
    """获取所有市场当前状态（开/休/盘前/盘后）"""
    status_list = MultiMarketService.get_all_market_status()
    return {"total": len(status_list), "markets": status_list}


# ==================== 跨市场套利 ====================

@router.get("/arbitrage/opportunities")
def get_arbitrage_opportunities(
    symbol_a: Optional[str] = Query(None, description="标的A代码"),
    market_a: Optional[str] = Query(None, description="市场A"),
    symbol_b: Optional[str] = Query(None, description="标的B代码"),
    market_b: Optional[str] = Query(None, description="市场B"),
):
    """检测跨市场套利机会"""
    # 如果指定了具体标的对，返回单个结果
    if symbol_a and market_a and symbol_b and market_b:
        result = MultiMarketService.detect_arbitrage_opportunity(
            symbol_a, market_a, symbol_b, market_b
        )
        return {"total": 1, "opportunities": [result]}

    # 否则返回所有预设套利对的分析
    from .multi_market_service import MultiMarketService as svc
    opportunities = []
    for pair in svc._CROSS_MARKET_PAIRS:
        opp = MultiMarketService.detect_arbitrage_opportunity(
            pair["symbol_a"], pair["market_a"],
            pair["symbol_b"], pair["market_b"]
        )
        opp["name"] = pair["name"]
        opportunities.append(opp)
    return {"total": len(opportunities), "opportunities": opportunities}


@router.post("/arbitrage/calculate")
def calculate_arbitrage(data: dict):
    """计算套利盈亏"""
    required_fields = ["quantity_a", "quantity_b", "price_a", "price_b"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(status_code=422, detail=f"缺少必填字段: {field}")
    result = MultiMarketService.calculate_arbitrage_pnl(data)
    return result


@router.get("/correlation")
def get_cross_market_correlation(
    symbols: Optional[str] = Query(None, description="标的列表(逗号分隔)"),
    period: str = Query("30d", description="周期 7d/30d/90d/1y"),
):
    """获取跨市场相关性矩阵"""
    symbol_list = symbols.split(",") if symbols else None
    result = MultiMarketService.get_cross_market_correlation(symbol_list, period)
    return result


@router.get("/global-overview")
def get_global_overview():
    """全球市场概览（各市场主要指数、状态、套利机会）"""
    result = MultiMarketService.get_global_market_overview()
    return result
