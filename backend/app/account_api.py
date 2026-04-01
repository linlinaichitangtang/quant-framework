"""
交易账户与风控管理 API 端点
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field

from .database import get_db
from . import crud, schemas


router = APIRouter(prefix="/api/v1", tags=["accounts"])


# ========== 请求/响应模型 ==========

class TradingAccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="账户名称")
    market: schemas.MarketType = Field(..., description="市场")
    fmz_account_id: Optional[int] = Field(None, description="FMZ 账户ID")
    fmz_api_key: Optional[str] = Field(None, max_length=200, description="FMZ API Key")
    fmz_secret_key: Optional[str] = Field(None, max_length=200, description="FMZ Secret Key")
    status: str = Field("active", description="状态 active/disabled")
    risk_params: Optional[str] = Field(None, description="风控参数(JSON)")


class TradingAccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    market: Optional[schemas.MarketType] = None
    fmz_account_id: Optional[int] = None
    fmz_api_key: Optional[str] = Field(None, max_length=200)
    fmz_secret_key: Optional[str] = Field(None, max_length=200)
    status: Optional[str] = None
    risk_params: Optional[str] = None
    total_pnl: Optional[float] = None
    today_pnl: Optional[float] = None
    total_trades: Optional[int] = None


class RiskRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="规则名称")
    rule_type: str = Field(..., min_length=1, max_length=50, description="规则类型 position_limit/stop_loss/daily_loss/sector_limit")
    market: schemas.MarketType = Field(..., description="适用市场")
    account_id: Optional[int] = Field(None, description="绑定账户ID，NULL为全局规则")
    params: str = Field(..., min_length=1, description="规则参数(JSON)")
    is_enabled: bool = Field(True, description="是否启用")
    priority: int = Field(0, description="优先级，数字越大越优先")


class RiskRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    rule_type: Optional[str] = Field(None, max_length=50)
    market: Optional[schemas.MarketType] = None
    account_id: Optional[int] = None
    params: Optional[str] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None


class RiskCheckRequest(BaseModel):
    account_id: int = Field(..., description="账户ID")
    market: schemas.MarketType = Field(..., description="市场")


class RiskCheckResultItem(BaseModel):
    rule_name: str
    rule_type: str
    status: str  # pass / violated
    message: str


# ========== 交易账户端点 ==========

@router.get("/accounts")
def list_accounts(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    status: Optional[str] = Query(None, description="状态"),
    db: Session = Depends(get_db),
):
    """获取交易账户列表"""
    return crud.get_trading_accounts(db, market=market, status=status)


@router.post("/accounts")
def create_account(
    account: TradingAccountCreate,
    db: Session = Depends(get_db),
):
    """创建交易账户"""
    return crud.create_trading_account(db, **account.model_dump())


@router.put("/accounts/{account_id}")
def update_account(
    account_id: int,
    account: TradingAccountUpdate,
    db: Session = Depends(get_db),
):
    """更新交易账户"""
    db_account = crud.update_trading_account(db, account_id, **account.model_dump(exclude_unset=True))
    if not db_account:
        raise HTTPException(status_code=404, detail=f"交易账户 {account_id} 不存在")
    return db_account


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
):
    """删除交易账户"""
    db_account = crud.delete_trading_account(db, account_id)
    if not db_account:
        raise HTTPException(status_code=404, detail=f"交易账户 {account_id} 不存在")
    return {"message": f"交易账户 {account_id} 已删除"}


@router.post("/accounts/{account_id}/set-default")
def set_default(
    account_id: int,
    db: Session = Depends(get_db),
):
    """设置默认交易账户"""
    db_account = crud.set_default_account(db, account_id)
    if not db_account:
        raise HTTPException(status_code=404, detail=f"交易账户 {account_id} 不存在")
    return db_account


# ========== 风控规则端点 ==========

@router.get("/risk/rules")
def list_risk_rules(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    enabled_only: bool = Query(False, description="仅返回启用的规则"),
    db: Session = Depends(get_db),
):
    """获取风控规则列表"""
    return crud.get_risk_rules(db, market=market, account_id=account_id, enabled_only=enabled_only)


@router.post("/risk/rules")
def create_risk_rule(
    rule: RiskRuleCreate,
    db: Session = Depends(get_db),
):
    """创建风控规则"""
    return crud.create_risk_rule(db, **rule.model_dump())


@router.put("/risk/rules/{rule_id}")
def update_risk_rule(
    rule_id: int,
    rule: RiskRuleUpdate,
    db: Session = Depends(get_db),
):
    """更新风控规则"""
    db_rule = crud.update_risk_rule(db, rule_id, **rule.model_dump(exclude_unset=True))
    if not db_rule:
        raise HTTPException(status_code=404, detail=f"风控规则 {rule_id} 不存在")
    return db_rule


@router.delete("/risk/rules/{rule_id}")
def delete_risk_rule(
    rule_id: int,
    db: Session = Depends(get_db),
):
    """删除风控规则"""
    db_rule = crud.delete_risk_rule(db, rule_id)
    if not db_rule:
        raise HTTPException(status_code=404, detail=f"风控规则 {rule_id} 不存在")
    return {"message": f"风控规则 {rule_id} 已删除"}


# ========== 风控事件端点 ==========

@router.get("/risk/events")
def list_risk_events(
    market: Optional[schemas.MarketType] = Query(None, description="市场"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    severity: Optional[str] = Query(None, description="严重级别 info/warning/critical"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取风控事件列表（分页）"""
    skip = (page - 1) * page_size
    data = crud.get_risk_events(
        db, market=market, account_id=account_id,
        severity=severity, skip=skip, limit=page_size
    )
    total = crud.count_risk_events(
        db, market=market, account_id=account_id, severity=severity
    )
    return schemas.PaginatedResponse(
        total=total, page=page, page_size=page_size, data=data
    )


# ========== 风控检查端点 ==========

@router.post("/risk/check", response_model=List[RiskCheckResultItem])
def run_risk_check(
    request: RiskCheckRequest,
    db: Session = Depends(get_db),
):
    """触发风控检查（获取所有启用规则并逐一检查）"""
    rules = crud.get_risk_rules(
        db, market=request.market, account_id=request.account_id, enabled_only=True
    )
    results = []
    for rule in rules:
        # 当前为占位实现，所有规则均返回 pass
        # 后续可根据 rule.rule_type 和 rule.params 实现具体检查逻辑
        results.append(RiskCheckResultItem(
            rule_name=rule.name,
            rule_type=rule.rule_type,
            status="pass",
            message=f"规则 [{rule.name}] 检查通过",
        ))
    return results
