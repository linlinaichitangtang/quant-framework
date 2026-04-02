"""
计费服务

提供订阅计划的创建、订阅管理、用量处理、账单生成等功能。
内置默认计划：Free / Basic / Pro / Enterprise
"""

import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func

from .database import SessionLocal

logger = logging.getLogger(__name__)


# ========== 内置默认计划 ==========
DEFAULT_PLANS = [
    {
        "plan_id": "free",
        "name": "Free",
        "description": "免费体验版",
        "price": 0,
        "billing_cycle": "monthly",
        "max_users": 1,
        "max_strategies": 3,
        "max_api_calls": 1000,
        "max_api_calls_per_minute": 10,
        "features": ["basic_signals", "market_data"],
        "trial_days": 0,
        "is_active": True,
    },
    {
        "plan_id": "basic",
        "name": "Basic",
        "description": "基础版",
        "price": 99,
        "billing_cycle": "monthly",
        "max_users": 5,
        "max_strategies": 10,
        "max_api_calls": 10000,
        "max_api_calls_per_minute": 30,
        "features": ["basic_signals", "market_data", "backtest", "api_access"],
        "trial_days": 7,
        "is_active": True,
    },
    {
        "plan_id": "pro",
        "name": "Pro",
        "description": "专业版",
        "price": 299,
        "billing_cycle": "monthly",
        "max_users": 20,
        "max_strategies": 50,
        "max_api_calls": 100000,
        "max_api_calls_per_minute": 60,
        "features": ["basic_signals", "advanced_signals", "market_data", "backtest", "api_access", "options", "plugins"],
        "trial_days": 14,
        "is_active": True,
    },
    {
        "plan_id": "enterprise",
        "name": "Enterprise",
        "description": "企业版",
        "price": 999,
        "billing_cycle": "monthly",
        "max_users": -1,  # 无限
        "max_strategies": -1,  # 无限
        "max_api_calls": -1,  # 无限
        "max_api_calls_per_minute": 200,
        "features": ["basic_signals", "advanced_signals", "market_data", "backtest", "api_access", "options", "plugins", "whitelabel", "priority_support", "custom_indicators"],
        "trial_days": 30,
        "is_active": True,
    },
]


class BillingService:
    """计费服务"""

    @staticmethod
    def init_default_plans(db: Session) -> None:
        """初始化内置默认计划（如果不存在）"""
        from .models import SubscriptionPlan

        for plan_data in DEFAULT_PLANS:
            existing = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.plan_id == plan_data["plan_id"]
            ).first()
            if not existing:
                plan = SubscriptionPlan(
                    plan_id=plan_data["plan_id"],
                    name=plan_data["name"],
                    description=plan_data["description"],
                    price=plan_data["price"],
                    billing_cycle=plan_data["billing_cycle"],
                    max_users=plan_data["max_users"],
                    max_strategies=plan_data["max_strategies"],
                    max_api_calls=plan_data["max_api_calls"],
                    max_api_calls_per_minute=plan_data.get("max_api_calls_per_minute", 60),
                    features=json.dumps(plan_data["features"], ensure_ascii=False),
                    trial_days=plan_data.get("trial_days", 0),
                    is_active=plan_data.get("is_active", True),
                )
                db.add(plan)

        db.commit()
        logger.info("默认订阅计划初始化完成")

    @staticmethod
    def create_plan(db: Session, data) -> Any:
        """
        创建订阅计划

        Args:
            db: 数据库会话
            data: 计划创建 schema

        Returns:
            创建的计划对象
        """
        from .models import SubscriptionPlan

        plan_id = data.plan_id or f"plan_{uuid.uuid4().hex[:8]}"

        plan = SubscriptionPlan(
            plan_id=plan_id,
            name=data.name,
            description=data.description if hasattr(data, "description") else "",
            price=data.price,
            billing_cycle=data.billing_cycle,
            max_users=data.max_users,
            max_strategies=data.max_strategies,
            max_api_calls=data.max_api_calls,
            max_api_calls_per_minute=data.max_api_calls_per_minute if hasattr(data, "max_api_calls_per_minute") else 60,
            features=json.dumps(data.features, ensure_ascii=False) if hasattr(data, "features") and data.features else json.dumps([]),
            trial_days=data.trial_days if hasattr(data, "trial_days") else 0,
            is_active=data.is_active if hasattr(data, "is_active") else True,
        )

        db.add(plan)
        db.commit()
        db.refresh(plan)

        logger.info(f"订阅计划创建成功: {plan_id} ({data.name})")
        return plan

    @staticmethod
    def update_plan(db: Session, plan_id: str, data) -> Optional[Any]:
        """
        更新订阅计划

        Args:
            db: 数据库会话
            plan_id: 计划标识
            data: 更新数据

        Returns:
            更新后的计划对象
        """
        from .models import SubscriptionPlan

        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_id == plan_id).first()
        if not plan:
            return None

        update_fields = data.model_dump(exclude_unset=True)

        # 处理 features 字段
        if "features" in update_fields and update_fields["features"] is not None:
            update_fields["features"] = json.dumps(update_fields["features"], ensure_ascii=False)

        for key, value in update_fields.items():
            setattr(plan, key, value)

        db.commit()
        db.refresh(plan)

        logger.info(f"订阅计划已更新: {plan_id}")
        return plan

    @staticmethod
    def list_plans(db: Session) -> List[Any]:
        """
        列出所有活跃的订阅计划

        Args:
            db: 数据库会话

        Returns:
            计划列表
        """
        from .models import SubscriptionPlan

        return db.query(SubscriptionPlan).filter(
            SubscriptionPlan.is_active == True,
        ).order_by(SubscriptionPlan.price).all()

    @staticmethod
    def subscribe(
        db: Session,
        tenant_id: str,
        plan_id: str,
        billing_cycle: str = "monthly",
    ) -> Any:
        """
        订阅计划

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            plan_id: 计划标识
            billing_cycle: 计费周期（monthly / yearly）

        Returns:
            订阅记录对象
        """
        from .models import SubscriptionPlan, Subscription

        # 检查计划是否存在
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_id == plan_id,
            SubscriptionPlan.is_active == True,
        ).first()
        if not plan:
            raise ValueError(f"订阅计划不存在或已停用: {plan_id}")

        # 检查是否已有活跃订阅
        existing = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "active",
        ).first()
        if existing:
            # 升级/降级计划
            existing.plan_id = plan_id
            existing.billing_cycle = billing_cycle
            existing.updated_at = datetime.now()
            db.commit()
            db.refresh(existing)
            logger.info(f"租户订阅已更新: {tenant_id} -> {plan_id}")
            return existing

        # 计算试用期
        trial_end = None
        if plan.trial_days and plan.trial_days > 0:
            trial_end = datetime.now() + timedelta(days=plan.trial_days)

        # 计算订阅周期
        now = datetime.now()
        if billing_cycle == "yearly":
            period_end = now + timedelta(days=365)
        else:
            period_end = now + timedelta(days=30)

        subscription = Subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            status="active",
            billing_cycle=billing_cycle,
            current_period_start=now,
            current_period_end=period_end,
            trial_end=trial_end,
        )

        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        logger.info(f"租户订阅成功: {tenant_id} -> {plan_id} ({billing_cycle})")
        return subscription

    @staticmethod
    def cancel_subscription(db: Session, tenant_id: str) -> bool:
        """
        取消订阅

        Args:
            db: 数据库会话
            tenant_id: 租户标识

        Returns:
            是否取消成功
        """
        from .models import Subscription

        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "active",
        ).first()
        if not subscription:
            return False

        subscription.status = "cancelled"
        subscription.cancelled_at = datetime.now()
        db.commit()

        logger.info(f"租户订阅已取消: {tenant_id}")
        return True

    @staticmethod
    def check_subscription(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        检查订阅状态

        Args:
            db: 数据库会话
            tenant_id: 租户标识

        Returns:
            订阅状态字典
        """
        from .models import Subscription, SubscriptionPlan

        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
        ).order_by(desc(Subscription.created_at)).first()

        if not subscription:
            return {
                "tenant_id": tenant_id,
                "status": "none",
                "plan": None,
                "trial": False,
            }

        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_id == subscription.plan_id,
        ).first()

        # 检查订阅是否过期
        is_expired = False
        if subscription.current_period_end and subscription.current_period_end < datetime.now():
            if subscription.status == "active":
                subscription.status = "expired"
                db.commit()
            is_expired = True

        # 检查试用期
        in_trial = False
        if subscription.trial_end and subscription.trial_end > datetime.now() and subscription.status == "active":
            in_trial = True

        return {
            "tenant_id": tenant_id,
            "status": subscription.status,
            "plan": {
                "plan_id": plan.plan_id if plan else None,
                "name": plan.name if plan else None,
                "price": plan.price if plan else 0,
            },
            "billing_cycle": subscription.billing_cycle,
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "trial": in_trial,
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
            "is_expired": is_expired,
        }

    @staticmethod
    def process_usage(
        db: Session,
        tenant_id: str,
        metric: str,
        value: int = 1,
    ) -> Dict[str, Any]:
        """
        处理用量（检查是否超额）

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            metric: 指标名称（api_calls / strategies / users）
            value: 用量值

        Returns:
            处理结果字典
        """
        from .models import Subscription, SubscriptionPlan

        # 获取订阅信息
        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "active",
        ).first()

        if not subscription:
            return {"allowed": True, "message": "无活跃订阅", "current": value, "limit": -1}

        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_id == subscription.plan_id,
        ).first()

        if not plan:
            return {"allowed": True, "message": "计划不存在", "current": value, "limit": -1}

        # 获取配额限制
        limit_map = {
            "api_calls": plan.max_api_calls,
            "strategies": plan.max_strategies,
            "users": plan.max_users,
        }
        limit = limit_map.get(metric, -1)

        # -1 表示无限制
        if limit == -1:
            return {"allowed": True, "message": "无限制", "current": value, "limit": -1}

        # 检查是否超额
        if value > limit:
            logger.warning(f"租户用量超额: {tenant_id} {metric}={value}/{limit}")
            return {
                "allowed": False,
                "message": f"{metric} 用量已超出配额限制",
                "current": value,
                "limit": limit,
            }

        return {"allowed": True, "message": "正常", "current": value, "limit": limit}

    @staticmethod
    def generate_invoice(db: Session, tenant_id: str, period: str = "current") -> Dict[str, Any]:
        """
        生成账单

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            period: 账单周期（current / previous）

        Returns:
            账单信息字典
        """
        from .models import Subscription, SubscriptionPlan, Invoice

        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
        ).order_by(desc(Subscription.created_at)).first()

        if not subscription:
            raise ValueError(f"租户无订阅记录: {tenant_id}")

        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_id == subscription.plan_id,
        ).first()

        if not plan:
            raise ValueError(f"订阅计划不存在: {subscription.plan_id}")

        # 检查是否已有该周期的账单
        invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
        now = datetime.now()

        # 计算账单金额
        amount = plan.price
        if subscription.billing_cycle == "yearly":
            amount = plan.price * 12 * 0.9  # 年付9折

        # 试用期免费
        if subscription.trial_end and subscription.trial_end > now:
            amount = 0

        invoice = Invoice(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            subscription_id=subscription.id,
            plan_id=subscription.plan_id,
            amount=amount,
            billing_cycle=subscription.billing_cycle,
            status="pending",
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        logger.info(f"账单已生成: {invoice_id} (租户: {tenant_id}, 金额: {amount})")

        return {
            "invoice_id": invoice_id,
            "tenant_id": tenant_id,
            "plan_name": plan.name,
            "amount": amount,
            "billing_cycle": subscription.billing_cycle,
            "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
            "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
            "status": invoice.status,
            "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        }

    @staticmethod
    def get_billing_history(db: Session, tenant_id: str) -> List[Any]:
        """
        获取账单历史

        Args:
            db: 数据库会话
            tenant_id: 租户标识

        Returns:
            账单记录列表
        """
        from .models import Invoice

        return db.query(Invoice).filter(
            Invoice.tenant_id == tenant_id,
        ).order_by(desc(Invoice.created_at)).all()

    @staticmethod
    def check_trial(db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        检查试用期状态

        Args:
            db: 数据库会话
            tenant_id: 租户标识

        Returns:
            试用期状态字典
        """
        from .models import Subscription, SubscriptionPlan

        subscription = db.query(Subscription).filter(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "active",
        ).first()

        if not subscription or not subscription.trial_end:
            return {
                "tenant_id": tenant_id,
                "in_trial": False,
                "trial_end": None,
                "days_remaining": 0,
            }

        now = datetime.now()
        in_trial = subscription.trial_end > now
        days_remaining = max(0, (subscription.trial_end - now).days) if in_trial else 0

        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_id == subscription.plan_id,
        ).first()

        return {
            "tenant_id": tenant_id,
            "in_trial": in_trial,
            "plan_name": plan.name if plan else None,
            "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
            "days_remaining": days_remaining,
        }
