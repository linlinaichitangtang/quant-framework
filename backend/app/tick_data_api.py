"""
高频 Tick 数据 API 端点

提供 Tick 数据存储、查询和微观结构分析接口。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

from .tick_data import TickData, TickDataStore, MicrostructureAnalyzer, tick_data_store
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/market/tick", tags=["tick_data"])


class TickDataItem(BaseModel):
    """单条 Tick 数据"""
    symbol: str
    timestamp: str  # ISO 格式
    last_price: float
    bid_price: float
    ask_price: float
    bid_size: int
    ask_size: int
    volume: int
    turnover: float


class TickDataWriteRequest(BaseModel):
    """写入 Tick 数据请求"""
    ticks: List[TickDataItem]


class TickQueryRequest(BaseModel):
    """查询 Tick 数据请求"""
    symbol: str
    start_time: str  # ISO 格式
    end_time: str    # ISO 格式


class MicrostructureAnalysisRequest(BaseModel):
    """微观结构分析请求"""
    symbol: str
    start_time: str
    end_time: str


@router.post("/write")
def write_tick_data(
    request: TickDataWriteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    写入 Tick 数据

    批量写入 Tick 数据用于存储和分析。
    """
    try:
        ticks = []
        for item in request.ticks:
            ts = datetime.fromisoformat(item.timestamp.replace("Z", "+00:00"))
            ticks.append(TickData(
                symbol=item.symbol,
                timestamp=ts,
                last_price=item.last_price,
                bid_price=item.bid_price,
                ask_price=item.ask_price,
                bid_size=item.bid_size,
                ask_size=item.ask_size,
                volume=item.volume,
                turnover=item.turnover,
                date=ts.strftime("%Y%m%d")
            ))

        tick_data_store.put(ticks)

        return {
            "message": f"成功写入 {len(ticks)} 条 Tick 数据",
            "n_ticks": len(ticks)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/query")
def query_tick_data(
    request: TickQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    查询 Tick 数据

    返回指定时间范围内的 Tick 数据。
    """
    try:
        start_time = datetime.fromisoformat(request.start_time.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(request.end_time.replace("Z", "+00:00"))

        ticks = tick_data_store.query(request.symbol, start_time, end_time)

        return {
            "symbol": request.symbol,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "n_ticks": len(ticks),
            "ticks": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "last_price": t.last_price,
                    "bid_price": t.bid_price,
                    "ask_price": t.ask_price,
                    "bid_size": t.bid_size,
                    "ask_size": t.ask_size,
                    "volume": t.volume
                }
                for t in ticks[:1000]  # 最多返回1000条
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
def get_tick_stats(current_user: dict = Depends(get_current_user)):
    """获取 Tick 数据存储统计"""
    stats = tick_data_store.get_stats()
    return stats


@router.post("/analyze/microstructure")
def analyze_microstructure(
    request: MicrostructureAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    市场微观结构分析

    基于 Tick 数据计算买卖价差、流动性等指标。
    """
    try:
        start_time = datetime.fromisoformat(request.start_time.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(request.end_time.replace("Z", "+00:00"))

        ticks = tick_data_store.query(request.symbol, start_time, end_time)

        if not ticks:
            return {"message": "没有找到 Tick 数据", "n_ticks": 0}

        # 计算各项指标
        spread = MicrostructureAnalyzer.compute_spread(ticks)
        volume_profile = MicrostructureAnalyzer.compute_volume_profile(ticks)
        roll = MicrostructureAnalyzer.compute_roll_impact(ticks)
        vwap = MicrostructureAnalyzer.compute_vwap(ticks)
        depth = MicrostructureAnalyzer.compute_market_depth(ticks)

        return {
            "symbol": request.symbol,
            "n_ticks": len(ticks),
            "spread": spread,
            "volume_profile": volume_profile,
            "roll_impact": roll,
            "vwap": vwap,
            "market_depth": depth,
            "price_range": {
                "min": float(np.min([t.last_price for t in ticks])),
                "max": float(np.max([t.last_price for t in ticks])),
                "mean": float(np.mean([t.last_price for t in ticks]))
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/spread")
def analyze_spread(
    symbol: str = Query(..., description="股票代码"),
    start_time: str = Query(..., description="开始时间"),
    end_time: str = Query(..., description="结束时间"),
    current_user: dict = Depends(get_current_user)
):
    """分析买卖价差"""
    try:
        st = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        et = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        ticks = tick_data_store.query(symbol, st, et)
        if not ticks:
            return {"message": "没有找到数据"}

        spread = MicrostructureAnalyzer.compute_spread(ticks)
        return {"symbol": symbol, "spread": spread, "n_ticks": len(ticks)}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze/vwap")
def compute_vwap(
    symbol: str = Query(...),
    start_time: str = Query(...),
    end_time: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """计算 VWAP"""
    try:
        st = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        et = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        ticks = tick_data_store.query(symbol, st, et)
        if not ticks:
            return {"message": "没有找到数据"}

        vwap = MicrostructureAnalyzer.compute_vwap(ticks)
        return {"symbol": symbol, "vwap": vwap, "n_ticks": len(ticks)}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/clear")
def clear_old_data(
    n_days: int = Query(1, ge=1, le=30, description="清除天数"),
    current_user: dict = Depends(get_current_user)
):
    """清除旧数据释放内存"""
    tick_data_store.clear_oldest(n_days)
    return {"message": f"已清除最近 {n_days} 天的数据"}