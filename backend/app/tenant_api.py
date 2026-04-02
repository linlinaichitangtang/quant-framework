"""
租户管理 API 路由

路由前缀 /api/v1/tenant，需要管理员权限。
提供租户的创建、查询、更新、删除、用量统计、白标配置、订阅管理等功能。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user, require_role
from .tenant_service import TenantService
from .billing_service import BillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tenant", tags=["租户管理"])


# ========== 请求/响应 Schema ==========

class TenantCreate(BaseModel):
    """创建租户请求"""
    name: str = Field(..., min_length=1, max_length=200, description="租户名称")
    contact_email: Optional[str] = Field(None, description="联系邮箱")
    phone: Optional[str] = Field(None, description="联系电话")
    domain: Optional[str] = Field(None, description="自定义域名")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    features: Optional[list] = Field(None, description="功能权限列表")
    max_users: Optional[int] = Field(5, description="最大用户数")
    max_strategies: Optional[int] = Field(10, description="最大策略数")
    max_api_calls: Optional[int] = Field(10000, description="最大API调用数/月")
    status: Optional[str] = Field("active", description="状态 active/inactive")


class TenantUpdate(BaseModel):
    """更新租户请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    domain: Optional[str] = None
    logo_url: Optional[str] = None
    features: Optional[list] = None
    max_users: Optional[int] = None
    max_strategies: Optional[int] = None
    max_api_calls: Optional[int] = None
    status: Optional[str] = None


class WhitelabelConfigUpdate(BaseModel):
    """白标配置更新请求"""
    primary_color: Optional[str] = Field(None, description="主色调")
    secondary_color: Optional[str] = Field(None, description="副色调")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    favicon_url: Optional[str] = Field(None, description="Favicon URL")
    title: Optional[str] = Field(None, description="站点标题")
    footer_text: Optional[str] = Field(None, description="页脚文本")
    custom_css: Optional[str] = Field(None, description="自定义CSS")
    custom_domain: Optional[str] = Field(None, description="自定义域名")


class SubscribeRequest(BaseModel):
    """订阅计划请求"""
    plan_id: str = Field(..., description="计划标识")
    billing_cycle: str = Field("monthly", description="计费周期 monthly/yearly")


# ========== 接口实现 ==========

@router.post("")
def create_tenant(
    data: TenantCreate,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    创建租户（管理员）

    创建新的租户，自动生成租户ID。
    """
    tenant = TenantService.create_tenant(db, data)
    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "status": tenant.status,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
    }


@router.get("")
def list_tenants(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选"),
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    列出租户（管理员）

    分页列出租户列表，支持按状态筛选。
    """
    result = TenantService.list_tenants(db, page=page, page_size=page_size, status=status)

    data = [
        {
            "tenant_id": t.tenant_id,
            "name": t.name,
            "status": t.status,
            "contact_email": t.contact_email,
            "max_users": t.max_users,
            "max_strategies": t.max_strategies,
            "max_api_calls": t.max_api_calls,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in result["data"]
    ]

    return {
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "data": data,
    }


@router.get("/{tenant_id}")
def get_tenant(
    tenant_id: str,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    获取租户详情（管理员）

    根据租户ID获取租户详细信息。
    """
    tenant = TenantService.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")

    import json
    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "status": tenant.status,
        "contact_email": tenant.contact_email,
        "phone": tenant.phone,
        "domain": tenant.domain,
        "logo_url": tenant.logo_url,
        "features": json.loads(tenant.features) if tenant.features else [],
        "max_users": tenant.max_users,
        "max_strategies": tenant.max_strategies,
        "max_api_calls": tenant.max_api_calls,
        "whitelabel_config": json.loads(tenant.whitelabel_config) if tenant.whitelabel_config else None,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }


@router.put("/{tenant_id}")
def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    更新租户（管理员）

    更新租户信息。
    """
    tenant = TenantService.update_tenant(db, tenant_id, data)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")

    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "status": tenant.status,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }


@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: str,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    删除租户（管理员）

    软删除租户（状态设为 deleted）。
    """
    success = TenantService.delete_tenant(db, tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="租户不存在")

    return {"message": f"租户 {tenant_id} 已删除"}


@router.get("/{tenant_id}/usage")
def get_tenant_usage(
    tenant_id: str,
    period: str = Query("month", description="统计周期 day/week/month"),
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    获取租户用量统计（管理员）

    获取租户的用量统计和配额信息。
    """
    tenant = TenantService.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")

    stats = TenantService.get_usage_stats(db, tenant_id, period)
    return stats


@router.put("/{tenant_id}/whitelabel")
def update_whitelabel(
    tenant_id: str,
    config: WhitelabelConfigUpdate,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    更新白标配置（管理员）

    更新租户的白标配置（品牌定制）。
    """
    tenant = TenantService.update_whitelabel(db, tenant_id, config.model_dump(exclude_unset=True))
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")

    return {"message": "白标配置已更新", "tenant_id": tenant_id}


@router.post("/{tenant_id}/subscribe")
def subscribe_tenant(
    tenant_id: str,
    data: SubscribeRequest,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    订阅计划（管理员）

    为租户订阅指定的计费计划。
    """
    tenant = TenantService.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")

    try:
        subscription = BillingService.subscribe(db, tenant_id, data.plan_id, data.billing_cycle)
        return {
            "message": "订阅成功",
            "tenant_id": tenant_id,
            "plan_id": data.plan_id,
            "billing_cycle": data.billing_cycle,
            "status": subscription.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
