"""
回测 API 端点
"""
import io
import csv
import json
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
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


@router.get("/results/{backtest_id}/export")
def export_backtest(
    backtest_id: int,
    format: str = Query("json", description="导出格式: csv/json"),
    db: Session = Depends(get_db),
):
    """导出回测结果（CSV / JSON）"""
    result = crud.get_backtest_result(db, backtest_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"回测结果 {backtest_id} 不存在")

    trades = crud.get_backtest_trades(db, backtest_id)

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["symbol", "direction", "entry_date", "exit_date", "entry_price", "exit_price", "pnl", "return_pct"])
        for t in trades:
            writer.writerow([
                getattr(t, "symbol", ""),
                getattr(t, "direction", ""),
                str(getattr(t, "entry_date", "")),
                str(getattr(t, "exit_date", "")),
                getattr(t, "entry_price", 0),
                getattr(t, "exit_price", 0),
                getattr(t, "pnl", 0),
                getattr(t, "return_pct", 0),
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=backtest_{backtest_id}.csv"},
        )

    # JSON 格式
    data = {
        "backtest_id": backtest_id,
        "exported_at": datetime.now().isoformat(),
        "result": {k: v for k, v in (result.__dict__ if hasattr(result, "__dict__") else {}).items()
                   if not k.startswith("_")},
        "trades": [
            {k: v for k, v in (t.__dict__ if hasattr(t, "__dict__") else {}).items()
             if not k.startswith("_")}
            for t in trades
        ],
    }
    return JSONResponse(content=data)
