"""
期权 API 端点
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from .database import get_db
from . import crud, schemas
from .options_engine import (
    calculate_greeks, calculate_implied_volatility,
    generate_option_chain, calculate_strategy_pnl,
)


router = APIRouter(prefix="/api/v1/options", tags=["options"])


@router.get("/chain")
def get_option_chain(
    symbol: str = Query(..., description="标的代码，如 AAPL"),
    underlying_price: float = Query(..., description="标的当前价格"),
    expiry_date: str = Query(..., description="到期日 YYYY-MM-DD"),
    risk_free_rate: float = Query(0.05, description="无风险利率"),
    base_volatility: float = Query(0.3, description="基础波动率"),
    n_strikes: int = Query(11, ge=3, le=31, description="行权价数量"),
):
    """获取期权链（含希腊字母）"""
    chain = generate_option_chain(
        symbol=symbol,
        S=underlying_price,
        expiry_date=expiry_date,
        r=risk_free_rate,
        base_sigma=base_volatility,
        n_strikes=n_strikes,
    )
    return {"symbol": symbol, "underlying_price": underlying_price, "expiry_date": expiry_date, "contracts": chain}


@router.get("/greeks")
def get_greeks(
    underlying_price: float = Query(..., description="标的价格"),
    strike_price: float = Query(..., description="行权价"),
    days_to_expiry: int = Query(..., description="距到期天数"),
    risk_free_rate: float = Query(0.05, description="无风险利率"),
    volatility: float = Query(0.3, description="隐含波动率"),
    option_type: str = Query("CALL", description="CALL 或 PUT"),
):
    """计算单个合约的希腊字母"""
    T = max(days_to_expiry / 365.0, 0.001)
    greeks = calculate_greeks(
        S=underlying_price,
        K=strike_price,
        T=T,
        r=risk_free_rate,
        sigma=volatility,
        option_type=option_type,
    )
    return {
        "underlying_price": underlying_price,
        "strike_price": strike_price,
        "days_to_expiry": days_to_expiry,
        "option_type": option_type,
        "volatility": volatility,
        **{
            "delta": greeks.delta,
            "gamma": greeks.gamma,
            "theta": greeks.theta,
            "vega": greeks.vega,
            "theoretical_price": greeks.theoretical_price,
        }
    }


@router.get("/iv")
def get_implied_volatility(
    underlying_price: float = Query(..., description="标的价格"),
    strike_price: float = Query(..., description="行权价"),
    days_to_expiry: int = Query(..., description="距到期天数"),
    risk_free_rate: float = Query(0.05, description="无风险利率"),
    market_price: float = Query(..., description="市场价格"),
    option_type: str = Query("CALL", description="CALL 或 PUT"),
):
    """计算隐含波动率"""
    T = max(days_to_expiry / 365.0, 0.001)
    iv = calculate_implied_volatility(
        S=underlying_price,
        K=strike_price,
        T=T,
        r=risk_free_rate,
        market_price=market_price,
        option_type=option_type,
    )
    if iv is None:
        raise HTTPException(status_code=400, detail="无法求解隐含波动率")
    return {"implied_volatility": round(iv, 6)}


@router.post("/strategy/pnl")
def get_strategy_pnl(legs: list, price_range: float = Query(0.2, description="标的价格浮动范围(±%)")):
    """
    计算期权组合盈亏图数据

    legs 格式:
    [{"option_type": "CALL", "strike": 100, "action": "buy", "quantity": 1, "premium": 5.0, "multiplier": 100}]
    """
    if not legs:
        raise HTTPException(status_code=400, detail="至少需要一条组合腿")

    # 以第一个腿的行权价为中心
    center = legs[0].get("strike", 100)
    low = center * (1 - price_range)
    high = center * (1 + price_range)
    step = (high - low) / 200
    prices = [round(low + i * step, 2) for i in range(201)]

    pnl_data = calculate_strategy_pnl(legs, prices)

    # 计算关键指标
    pnls = [p["pnl"] for p in pnl_data]
    max_profit = max(pnls)
    max_loss = min(pnls)

    # 盈亏平衡点
    breakevens = []
    for i in range(1, len(pnl_data)):
        if (pnl_data[i - 1]["pnl"] <= 0 and pnl_data[i]["pnl"] >= 0) or \
           (pnl_data[i - 1]["pnl"] >= 0 and pnl_data[i]["pnl"] <= 0):
            breakevens.append(round(pnl_data[i]["price"], 2))

    return {
        "pnl_data": pnl_data,
        "max_profit": max_profit,
        "max_loss": max_loss,
        "breakevens": breakevens,
    }


# ========== 期权组合持仓 CRUD ==========
@router.get("/positions")
def list_option_positions(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """获取期权组合持仓列表"""
    positions = crud.get_option_positions(db, status=status)
    return positions


@router.post("/positions")
def create_option_position(data: dict, db: Session = Depends(get_db)):
    """创建期权组合持仓"""
    position = crud.create_option_position(db, **data)
    return position


@router.delete("/positions/{position_id}")
def delete_option_position(position_id: int, db: Session = Depends(get_db)):
    """删除期权组合持仓"""
    result = crud.delete_option_position(db, position_id)
    if not result:
        raise HTTPException(status_code=404, detail="期权持仓不存在")
    return {"message": "已删除"}
