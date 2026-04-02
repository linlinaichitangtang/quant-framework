"""
V1.9 算法交易 API 路由
提供 TWAP/VWAP/冰山/智能拆单等算法交易端点
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field

from .database import get_db
from .algo_engine import AlgoEngine


router = APIRouter(prefix="/api/v1/algo", tags=["算法交易"])


# ========== 请求模型 ==========

class TWAPOrderRequest(BaseModel):
    """TWAP 订单请求"""
    symbol: str = Field(..., min_length=1, max_length=20, description="标的代码")
    market: str = Field("A", description="市场")
    side: str = Field(..., description="方向 BUY/SELL")
    quantity: float = Field(..., gt=0, description="总数量")
    duration_minutes: int = Field(60, ge=1, description="持续时间（分钟）")
    start_time: Optional[str] = Field(None, description="开始时间 ISO格式")
    end_time: Optional[str] = Field(None, description="结束时间 ISO格式")
    randomize: bool = Field(True, description="是否随机化拆单")
    max_participation_rate: float = Field(0.1, ge=0.01, le=1.0, description="最大参与率")


class VWAPOrderRequest(BaseModel):
    """VWAP 订单请求"""
    symbol: str = Field(..., min_length=1, max_length=20, description="标的代码")
    market: str = Field("A", description="市场")
    side: str = Field(..., description="方向 BUY/SELL")
    quantity: float = Field(..., gt=0, description="总数量")
    duration_minutes: int = Field(60, ge=1, description="持续时间（分钟）")
    volume_profile: Optional[str] = Field(None, description="成交量分布 auto/front_loaded/back_loaded")


class IcebergOrderRequest(BaseModel):
    """冰山订单请求"""
    symbol: str = Field(..., min_length=1, max_length=20, description="标的代码")
    market: str = Field("A", description="市场")
    side: str = Field(..., description="方向 BUY/SELL")
    quantity: float = Field(..., gt=0, description="总数量")
    display_quantity: float = Field(..., gt=0, description="每次显示数量")
    random_variance: float = Field(0.2, ge=0, le=1.0, description="随机方差")
    min_display: Optional[float] = Field(None, description="最小显示数量")


class SmartOrderRequest(BaseModel):
    """智能拆单请求"""
    symbol: str = Field(..., min_length=1, max_length=20, description="标的代码")
    market: str = Field("A", description="市场")
    side: str = Field(..., description="方向 BUY/SELL")
    quantity: float = Field(..., gt=0, description="总数量")
    urgency: str = Field("medium", description="紧急程度 low/medium/high")
    max_impact_pct: float = Field(0.5, ge=0.01, le=5.0, description="最大市场冲击百分比")
    strategy: Optional[str] = Field(None, description="指定策略 auto/twap/vwap/iceberg")


# ========== 算法订单创建 ==========

@router.post("/orders/twap")
def create_twap_order(req: TWAPOrderRequest, db: Session = Depends(get_db)):
    """创建 TWAP（时间加权平均价格）订单"""
    engine = AlgoEngine(db)
    result = engine.create_twap_order(req.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "创建订单失败"))
    return result


@router.post("/orders/vwap")
def create_vwap_order(req: VWAPOrderRequest, db: Session = Depends(get_db)):
    """创建 VWAP（成交量加权平均价格）订单"""
    engine = AlgoEngine(db)
    result = engine.create_vwap_order(req.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "创建订单失败"))
    return result


@router.post("/orders/iceberg")
def create_iceberg_order(req: IcebergOrderRequest, db: Session = Depends(get_db)):
    """创建冰山订单"""
    engine = AlgoEngine(db)
    result = engine.create_iceberg_order(req.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "创建订单失败"))
    return result


@router.post("/orders/smart")
def create_smart_order(req: SmartOrderRequest, db: Session = Depends(get_db)):
    """智能拆单"""
    engine = AlgoEngine(db)
    result = engine.create_smart_order(req.model_dump())
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "创建订单失败"))
    return result


# ========== 订单查询与管理 ==========

@router.get("/orders")
def get_algo_orders(
    algo_type: Optional[str] = Query(None, description="算法类型 twap/vwap/iceberg/smart"),
    status: Optional[str] = Query(None, description="订单状态"),
    symbol: Optional[str] = Query(None, description="标的代码"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    db: Session = Depends(get_db),
):
    """获取算法订单列表"""
    engine = AlgoEngine(db)
    params = {}
    if algo_type:
        params["algo_type"] = algo_type
    if status:
        params["status"] = status
    if symbol:
        params["symbol"] = symbol
    params["limit"] = limit
    return {"orders": engine.get_algo_orders(params)}


@router.get("/orders/{order_id}")
def get_algo_order(order_id: str, db: Session = Depends(get_db)):
    """获取算法订单详情"""
    engine = AlgoEngine(db)
    result = engine.get_order_execution_status(order_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "订单不存在"))
    return result


@router.get("/orders/{order_id}/status")
def get_algo_order_status(order_id: str, db: Session = Depends(get_db)):
    """获取算法订单执行状态"""
    engine = AlgoEngine(db)
    result = engine.get_order_execution_status(order_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "订单不存在"))
    return result


@router.post("/orders/{order_id}/cancel")
def cancel_algo_order(order_id: str, db: Session = Depends(get_db)):
    """取消算法订单"""
    engine = AlgoEngine(db)
    result = engine.cancel_algo_order(order_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "取消失败"))
    return result


@router.get("/orders/{order_id}/quality")
def get_execution_quality(order_id: str, db: Session = Depends(get_db)):
    """获取执行质量评估"""
    engine = AlgoEngine(db)
    result = engine.get_execution_quality(order_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "订单不存在"))
    return result


@router.get("/executions/history")
def get_execution_history(
    algo_type: Optional[str] = Query(None, description="算法类型"),
    status: Optional[str] = Query(None, description="订单状态"),
    symbol: Optional[str] = Query(None, description="标的代码"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    db: Session = Depends(get_db),
):
    """获取历史执行记录"""
    engine = AlgoEngine(db)
    params = {}
    if algo_type:
        params["algo_type"] = algo_type
    if status:
        params["status"] = status
    if symbol:
        params["symbol"] = symbol
    params["limit"] = limit
    return {"executions": engine.get_historical_executions(params)}
