"""
计费管理 API 路由

路由前缀 /api/v1/billing，提供订阅计划浏览、订阅管理、用量统计、账单查询等功能。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .tenant_middleware import get_current_tenant
from .billing_service import BillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["计费管理"])


# ========== 请求/响应 Schema ==========

class SubscribeRequest(BaseModel):
    """订阅计划请求"""
    plan_id: str = Field(..., description="计划标识")
    billing_cycle: str = Field("monthly", description="计费周期 monthly/yearly")


# ========== 接口实现 ==========

@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    """
    列出订阅计划

    获取所有可用的订阅计划列表。
    """
    import json

    plans = BillingService.list_plans(db)

    data = [
        {
            "plan_id": p.plan_id,
            "name": p.name,
            "description": p.description,
            "price": p.price,
            "billing_cycle": p.billing_cycle,
            "max_users": p.max_users,
            "max_strategies": p.max_strategies,
            "max_api_calls": p.max_api_calls,
            "max_api_calls_per_minute": p.max_api_calls_per_minute,
            "features": json.loads(p.features) if p.features else [],
            "trial_days": p.trial_days,
        }
        for p in plans
    ]

    return {"data": data}


@router.get("/current")
def get_current_subscription(
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    获取当前订阅

    获取当前租户的订阅状态和计划信息。
    """
    result = BillingService.check_subscription(db, tenant.tenant_id)
    return result


@router.post("/subscribe")
def subscribe_plan(
    data: SubscribeRequest,
    current_user: dict = Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    订阅计划

    为当前租户订阅指定的计费计划。
    """
    try:
        subscription = BillingService.subscribe(
            db=db,
            tenant_id=tenant.tenant_id,
            plan_id=data.plan_id,
            billing_cycle=data.billing_cycle,
        )

        return {
            "message": "订阅成功",
            "plan_id": data.plan_id,
            "billing_cycle": data.billing_cycle,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel")
def cancel_subscription(
    current_user: dict = Depends(get_current_user),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    取消订阅

    取消当前租户的活跃订阅。
    """
    success = BillingService.cancel_subscription(db, tenant.tenant_id)
    if not success:
        raise HTTPException(status_code=400, detail="无活跃订阅可取消")

    return {"message": "订阅已取消"}


@router.get("/usage")
def get_usage_stats(
    period: str = Query("month", description="统计周期 day/week/month"),
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    获取用量统计

    获取当前租户的用量统计信息。
    """
    from .tenant_service import TenantService

    stats = TenantService.get_usage_stats(db, tenant.tenant_id, period)
    return stats


@router.get("/invoices")
def get_billing_history(
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    获取账单历史

    获取当前租户的所有账单记录。
    """
    invoices = BillingService.get_billing_history(db, tenant.tenant_id)

    data = [
        {
            "invoice_id": inv.invoice_id,
            "plan_id": inv.plan_id,
            "amount": inv.amount,
            "billing_cycle": inv.billing_cycle,
            "status": inv.status,
            "period_start": inv.period_start.isoformat() if inv.period_start else None,
            "period_end": inv.period_end.isoformat() if inv.period_end else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }
        for inv in invoices
    ]

    return {"data": data}


@router.get("/invoices/{invoice_id}")
def get_invoice_detail(
    invoice_id: str,
    tenant=Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    获取账单详情

    根据账单ID获取账单详细信息。
    """
    from .models import Invoice

    invoice = db.query(Invoice).filter(
        Invoice.invoice_id == invoice_id,
        Invoice.tenant_id == tenant.tenant_id,
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="账单不存在")

    return {
        "invoice_id": invoice.invoice_id,
        "tenant_id": invoice.tenant_id,
        "plan_id": invoice.plan_id,
        "amount": invoice.amount,
        "billing_cycle": invoice.billing_cycle,
        "status": invoice.status,
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
    }
