"""
回测 API 端点
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from .database import get_db
from . import crud, schemas
from .backtest_service import run_backtest


router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


@router.get("/results", response_model=schemas.PaginatedResponse[schemas.BacktestSummaryResponse])
def list_backtest_results(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    strategy_type: Optional[str] = Query(None, description="策略类型"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取回测结果列表（摘要）"""
    skip = (page - 1) * page_size
    data = crud.get_backtest_results(
        db, market=market, strategy_type=strategy_type,
        status=status, skip=skip, limit=page_size
    )
    total = crud.count_backtest_results(
        db, market=market, strategy_type=strategy_type, status=status
    )
    return schemas.PaginatedResponse(
        total=total, page=page, page_size=page_size, data=data
    )


@router.get("/results/{backtest_id}", response_model=schemas.BacktestResultResponse)
def get_backtest_detail(backtest_id: int, db: Session = Depends(get_db)):
    """获取回测结果详情（含交易明细）"""
    result = crud.get_backtest_result(db, backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"回测结果 {backtest_id} 不存在")
    return result


@router.get("/results/{backtest_id}/trades", response_model=list[schemas.BacktestTradeResponse])
def get_backtest_trades(backtest_id: int, db: Session = Depends(get_db)):
    """获取回测交易明细"""
    result = crud.get_backtest_result(db, backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"回测结果 {backtest_id} 不存在")
    return crud.get_backtest_trades(db, backtest_id)


@router.post("/run", response_model=schemas.BacktestResultResponse)
def run_new_backtest(
    config: schemas.BacktestConfig,
    db: Session = Depends(get_db),
):
    """运行新回测"""
    try:
        result = run_backtest(db, config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


@router.delete("/results/{backtest_id}")
def delete_backtest(backtest_id: int, db: Session = Depends(get_db)):
    """删除回测结果"""
    result = crud.delete_backtest_result(db, backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"回测结果 {backtest_id} 不存在")
    return {"message": f"回测结果 {backtest_id} 已删除"}
