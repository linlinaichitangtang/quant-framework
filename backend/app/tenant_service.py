"""
租户管理服务

提供租户的 CRUD 操作、配额检查、用量统计、白标配置等功能。
"""

import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func

from .models import Tenant, TenantUsage
from .database import SessionLocal

logger = logging.getLogger(__name__)


class TenantService:
    """租户管理服务"""

    @staticmethod
    def create_tenant(db: Session, data) -> "Tenant":
        """
        创建租户

        Args:
            db: 数据库会话
            data: TenantCreate schema 对象

        Returns:
            创建的租户对象
        """
        # 自动生成租户ID（t_ 前缀 + 8位随机字符串）
        tenant_id = f"t_{uuid.uuid4().hex[:8]}"

        # 检查租户ID是否已存在（极低概率冲突）
        existing = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        while existing:
            tenant_id = f"t_{uuid.uuid4().hex[:8]}"
            existing = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()

        tenant = Tenant(
            tenant_id=tenant_id,
            name=data.name,
            status=data.status if hasattr(data, "status") else "active",
            contact_email=data.contact_email if hasattr(data, "contact_email") else None,
            phone=data.phone if hasattr(data, "phone") else None,
            domain=data.domain if hasattr(data, "domain") else None,
            logo_url=data.logo_url if hasattr(data, "logo_url") else None,
            features=json.dumps(data.features) if hasattr(data, "features") and data.features else json.dumps([]),
            max_users=data.max_users if hasattr(data, "max_users") else 5,
            max_strategies=data.max_strategies if hasattr(data, "max_strategies") else 10,
            max_api_calls=data.max_api_calls if hasattr(data, "max_api_calls") else 10000,
            whitelabel_config=json.dumps(data.whitelabel_config) if hasattr(data, "whitelabel_config") and data.whitelabel_config else None,
        )

        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        logger.info(f"租户创建成功: {tenant_id} ({data.name})")
        return tenant

    @staticmethod
    def get_tenant(db: Session, tenant_id: str) -> Optional["Tenant"]:
        """
        获取租户

        Args:
            db: 数据库会话
            tenant_id: 租户标识

        Returns:
            租户对象，不存在则返回 None
        """
        return db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()

    @staticmethod
    def update_tenant(db: Session, tenant_id: str, data) -> Optional["Tenant"]:
        """
        更新租户信息

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            data: TenantUpdate schema 对象

        Returns:
            更新后的租户对象，不存在则返回 None
        """
        tenant = TenantService.get_tenant(db, tenant_id)
        if not tenant:
            return None

        update_fields = data.model_dump(exclude_unset=True)

        # 处理 features 字段（列表转 JSON 字符串）
        if "features" in update_fields and update_fields["features"] is not None:
            update_fields["features"] = json.dumps(update_fields["features"])

        # 处理 whitelabel_config 字段（字典转 JSON 字符串）
        if "whitelabel_config" in update_fields and update_fields["whitelabel_config"] is not None:
            update_fields["whitelabel_config"] = json.dumps(update_fields["whitelabel_config"])

        for key, value in update_fields.items():
            setattr(tenant, key, value)

        db.commit()
        db.refresh(tenant)

        logger.info(f"租户更新成功: {tenant_id}")
        return tenant

    @staticmethod
    def delete_tenant(db: Session, tenant_id: str) -> bool:
        """
        删除租户（软删除 — 将状态设为 deleted）

        Args:
            db: 数据库会话
            tenant_id: 租户标识

        Returns:
            是否删除成功
        """
        tenant = TenantService.get_tenant(db, tenant_id)
        if not tenant:
            return False

        tenant.status = "deleted"
        db.commit()

        logger.info(f"租户已软删除: {tenant_id}")
        return True

    @staticmethod
    def list_tenants(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        列出租户（分页）

        Args:
            db: 数据库会话
            page: 页码（从1开始）
            page_size: 每页数量
            status: 按状态筛选

        Returns:
            包含分页信息和租户列表的字典
        """
        query = db.query(Tenant).filter(Tenant.status != "deleted")
        if status:
            query = query.filter(Tenant.status == status)

        total = query.count()
        tenants = query.order_by(desc(Tenant.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": tenants,
        }

    @staticmethod
    def check_tenant_limit(tenant: "Tenant", metric: str) -> bool:
        """
        检查租户配额是否超限

        Args:
            tenant: 租户对象
            metric: 指标名称（users / strategies / api_calls）

        Returns:
            True 表示未超限，False 表示已超限
        """
        limits = {
            "users": tenant.max_users or 5,
            "strategies": tenant.max_strategies or 10,
            "api_calls": tenant.max_api_calls or 10000,
        }

        limit = limits.get(metric)
        if limit is None or limit == -1:
            # -1 表示无限制
            return True

        # 查询当前用量
        db = SessionLocal()
        try:
            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            usage = db.query(func.sum(TenantUsage.value)).filter(
                TenantUsage.tenant_id == tenant.tenant_id,
                TenantUsage.metric == metric,
                TenantUsage.period_start >= month_start,
            ).scalar() or 0

            return int(usage) < limit
        finally:
            db.close()

    @staticmethod
    def increment_usage(
        db: Session,
        tenant_id: str,
        metric: str,
        value: int = 1,
    ) -> "TenantUsage":
        """
        增加租户用量计数

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            metric: 指标名称
            value: 增加的值（默认为1）

        Returns:
            用量记录对象
        """
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 查找当月是否已有记录
        usage = db.query(TenantUsage).filter(
            TenantUsage.tenant_id == tenant_id,
            TenantUsage.metric == metric,
            TenantUsage.period_start == month_start,
        ).first()

        if usage:
            usage.value = (usage.value or 0) + value
            usage.updated_at = now
        else:
            usage = TenantUsage(
                tenant_id=tenant_id,
                metric=metric,
                value=value,
                period_start=month_start,
                period_end=month_start + timedelta(days=32),  # 简单取下月初
            )
            db.add(usage)

        db.commit()
        db.refresh(usage)
        return usage

    @staticmethod
    def get_usage_stats(
        db: Session,
        tenant_id: str,
        period: str = "month",
    ) -> Dict[str, Any]:
        """
        获取租户用量统计

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            period: 统计周期（day / week / month）

        Returns:
            用量统计字典
        """
        now = datetime.now()

        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # month
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        usages = db.query(TenantUsage).filter(
            TenantUsage.tenant_id == tenant_id,
            TenantUsage.period_start >= start,
        ).all()

        stats = {}
        for u in usages:
            stats[u.metric] = {
                "value": u.value or 0,
                "period_start": u.period_start.isoformat() if u.period_start else None,
                "period_end": u.period_end.isoformat() if u.period_end else None,
            }

        # 获取租户配额信息
        tenant = TenantService.get_tenant(db, tenant_id)
        limits = {}
        if tenant:
            limits = {
                "users": tenant.max_users,
                "strategies": tenant.max_strategies,
                "api_calls": tenant.max_api_calls,
            }

        return {
            "tenant_id": tenant_id,
            "period": period,
            "usage": stats,
            "limits": limits,
        }

    @staticmethod
    def update_whitelabel(
        db: Session,
        tenant_id: str,
        config: dict,
    ) -> Optional["Tenant"]:
        """
        更新租户白标配置

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            config: 白标配置字典

        Returns:
            更新后的租户对象
        """
        tenant = TenantService.get_tenant(db, tenant_id)
        if not tenant:
            return None

        tenant.whitelabel_config = json.dumps(config, ensure_ascii=False)
        db.commit()
        db.refresh(tenant)

        logger.info(f"租户白标配置已更新: {tenant_id}")
        return tenant
