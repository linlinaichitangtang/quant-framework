"""
V2.1 PWA 推送通知 API

提供 Web Push 订阅管理、通知发送和历史查询功能。
使用 pywebpush 或手动 requests 实现推送通知。
"""

import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import PushSubscription, PushNotificationHistory
from .schemas import CommonResponse
from .config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== 依赖 ==========

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== 请求/响应 Schema ==========

class PushSubscribeRequest(BaseModel):
    """推送订阅请求"""
    endpoint: str = Field(..., description="推送订阅端点URL")
    keys_auth: str = Field(..., alias="keys.auth", description="认证密钥")
    keys_p256dh: str = Field(..., alias="keys.p256dh", description="P-256 DH 公钥")

    class Config:
        populate_by_name = True


class PushUnsubscribeRequest(BaseModel):
    """取消推送订阅请求"""
    endpoint: str = Field(..., description="推送订阅端点URL")


class PushSendRequest(BaseModel):
    """发送推送通知请求"""
    title: str = Field(..., min_length=1, max_length=200, description="通知标题")
    body: str = Field(..., min_length=1, description="通知内容")
    url: Optional[str] = Field(None, description="点击跳转URL")
    icon: Optional[str] = Field(None, description="通知图标URL")
    user_id: Optional[int] = Field(None, description="目标用户ID，为空则推送给所有订阅者")


class PushSubscriptionResponse(BaseModel):
    """推送订阅响应"""
    id: int
    user_id: int
    endpoint: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PushHistoryResponse(BaseModel):
    """推送历史响应"""
    id: int
    user_id: Optional[int]
    title: str
    body: str
    url: Optional[str]
    icon: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ========== Web Push 实现 ==========

VAPID_PUBLIC_KEY = getattr(settings, 'vapid_public_key', '')
VAPID_PRIVATE_KEY = getattr(settings, 'vapid_private_key', '')
VAPID_SUBJECT = getattr(settings, 'vapid_subject', 'mailto:support@openclaw.com')


def _build_vapid_headers():
    """构建 VAPID 认证头（简化实现）"""
    import base64
    import hashlib
    import time
    import struct

    if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
        return {}

    # VAPID JWT token
    audience = ""
    exp = int(time.time()) + 12 * 60 * 60  # 12小时过期

    # 简化实现：使用 pywebpush 库（如果可用）
    try:
        from pywebpush import WebPushException
        return {"use_pywebpush": True}
    except ImportError:
        # 手动实现基础 VAPID
        return {}


async def _send_web_push(subscription: PushSubscription, payload: dict):
    """
    发送 Web Push 通知

    优先使用 pywebpush 库，如果不可用则使用 httpx 手动实现。
    """
    message = json.dumps(payload)

    try:
        # 尝试使用 pywebpush
        from pywebpush import webpush
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "auth": subscription.keys_auth,
                "p256dh": subscription.keys_p256dh
            }
        }
        webpush(
            subscription_info=subscription_info,
            data=message,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT}
        )
        return True, None
    except ImportError:
        # pywebpush 不可用，使用 httpx 手动发送
        try:
            headers = {
                "Content-Type": "application/octet-stream",
                "TTL": "2419200",
            }
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    subscription.endpoint,
                    content=message.encode('utf-8'),
                    headers=headers
                )
                if response.status_code in (200, 201):
                    return True, None
                else:
                    return False, f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


# ========== API 端点 ==========

@router.post("/subscribe", summary="注册推送订阅")
async def subscribe_push(
    data: PushSubscribeRequest,
    db: Session = Depends(get_db)
):
    """
    注册 Web Push 推送订阅。

    将客户端的推送订阅信息保存到数据库。
    如果相同 endpoint 已存在则更新。
    """
    # 检查是否已存在
    existing = db.query(PushSubscription).filter(
        PushSubscription.endpoint == data.endpoint
    ).first()

    if existing:
        # 更新已有订阅
        existing.keys_auth = data.keys_auth
        existing.keys_p256dh = data.keys_p256dh
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return CommonResponse(
            code=0,
            message="订阅已更新",
            data={"id": existing.id}
        )

    # 创建新订阅
    subscription = PushSubscription(
        user_id=1,  # 默认用户，后续可从 JWT token 获取
        endpoint=data.endpoint,
        keys_auth=data.keys_auth,
        keys_p256dh=data.keys_p256dh,
        is_active=True
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    logger.info(f"新推送订阅已注册: {subscription.endpoint[:50]}...")

    return CommonResponse(
        code=0,
        message="订阅成功",
        data={"id": subscription.id}
    )


@router.post("/unsubscribe", summary="取消推送订阅")
async def unsubscribe_push(
    data: PushUnsubscribeRequest,
    db: Session = Depends(get_db)
):
    """
    取消 Web Push 推送订阅。

    将指定 endpoint 的订阅标记为非激活状态。
    """
    subscription = db.query(PushSubscription).filter(
        PushSubscription.endpoint == data.endpoint,
        PushSubscription.is_active == True
    ).first()

    if not subscription:
        return CommonResponse(
            code=0,
            message="订阅不存在或已取消"
        )

    subscription.is_active = False
    db.commit()

    logger.info(f"推送订阅已取消: {subscription.endpoint[:50]}...")

    return CommonResponse(
        code=0,
        message="已取消订阅"
    )


@router.post("/send", summary="发送推送通知")
async def send_push_notification(
    data: PushSendRequest,
    db: Session = Depends(get_db)
):
    """
    发送 Web Push 推送通知。

    可以指定目标用户，如果不指定则推送给所有激活的订阅者。
    """
    payload = {
        "title": data.title,
        "body": data.body,
        "url": data.url or "/",
        "icon": data.icon or "/pwa-192x192.png",
        "timestamp": datetime.now().isoformat()
    }

    # 查询目标订阅
    query = db.query(PushSubscription).filter(PushSubscription.is_active == True)
    if data.user_id:
        query = query.filter(PushSubscription.user_id == data.user_id)

    subscriptions = query.all()

    if not subscriptions:
        return CommonResponse(
            code=0,
            message="没有活跃的推送订阅",
            data={"sent_count": 0, "failed_count": 0}
        )

    sent_count = 0
    failed_count = 0

    for sub in subscriptions:
        success, error = await _send_web_push(sub, payload)

        # 记录推送历史
        history = PushNotificationHistory(
            user_id=sub.user_id,
            title=data.title,
            body=data.body,
            url=data.url,
            icon=data.icon,
            status="sent" if success else "failed",
            error_message=error
        )
        db.add(history)

        if success:
            sent_count += 1
        else:
            failed_count += 1
            logger.warning(f"推送失败 (user_id={sub.user_id}): {error}")

    db.commit()

    logger.info(f"推送通知完成: 发送 {sent_count}, 失败 {failed_count}")

    return CommonResponse(
        code=0,
        message="推送完成",
        data={
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_count": len(subscriptions)
        }
    )


@router.get("/history", summary="获取推送通知历史")
async def get_push_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: Optional[int] = Query(None, description="筛选用户ID"),
    db: Session = Depends(get_db)
):
    """
    获取推送通知历史记录。

    支持分页和按用户筛选。
    """
    query = db.query(PushNotificationHistory)
    if user_id:
        query = query.filter(PushNotificationHistory.user_id == user_id)

    total = query.count()
    records = query.order_by(
        PushNotificationHistory.created_at.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()

    return CommonResponse(
        code=0,
        message="success",
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "title": r.title,
                    "body": r.body,
                    "url": r.url,
                    "icon": r.icon,
                    "status": r.status,
                    "error_message": r.error_message,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in records
            ]
        }
    )
