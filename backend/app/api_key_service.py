"""
开放 API Key 管理服务

提供 API Key 的创建、吊销、验证、轮换、调用日志记录和使用统计等功能。
"""

import logging
import json
import secrets
import hashlib
import hmac
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from .database import SessionLocal

logger = logging.getLogger(__name__)

# API Key 前缀
API_KEY_PREFIX = "oc_"


class APIKeyService:
    """开放 API Key 管理服务"""

    @staticmethod
    def _generate_api_key() -> str:
        """
        生成随机 API Key

        Returns:
            oc_ 前缀 + 32位随机十六进制字符串
        """
        random_part = secrets.token_hex(16)  # 32位十六进制
        return f"{API_KEY_PREFIX}{random_part}"

    @staticmethod
    def _generate_api_secret() -> str:
        """
        生成随机 API Secret

        Returns:
            40位随机十六进制字符串
        """
        return secrets.token_hex(20)

    @staticmethod
    def _hash_secret(secret: str) -> str:
        """
        哈希 API Secret（使用 SHA-256）

        Args:
            secret: 原始 Secret

        Returns:
            哈希后的十六进制字符串
        """
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def create_api_key(
        db: Session,
        tenant_id: str,
        user_id: int,
        data,
    ) -> dict:
        """
        创建 API Key

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            user_id: 用户ID
            data: OpenAPIKeyCreate schema 对象

        Returns:
            包含 API Key 和 Secret 的字典（Secret 仅在创建时返回一次）
        """
        from .models import OpenAPIKey

        # 生成 API Key 和 Secret
        api_key = APIKeyService._generate_api_key()
        api_secret = APIKeyService._generate_api_secret()
        hashed_secret = APIKeyService._hash_secret(api_secret)

        # 检查同一租户下的 Key 名称是否重复
        existing = db.query(OpenAPIKey).filter(
            OpenAPIKey.tenant_id == tenant_id,
            OpenAPIKey.key_name == data.name,
            OpenAPIKey.status == "active",
        ).first()
        if existing:
            raise ValueError(f"API Key 名称 '{data.name}' 已存在")

        key_record = OpenAPIKey(
            tenant_id=tenant_id,
            user_id=user_id,
            key_name=data.name,
            name=data.name,
            api_key=api_key,
            api_secret_hash=hashed_secret,
            permissions=json.dumps(data.permissions, ensure_ascii=False) if hasattr(data, "permissions") and data.permissions else json.dumps(["read"], ensure_ascii=False),
            rate_limit=data.rate_limit if hasattr(data, "rate_limit") else 60,
            expires_at=data.expires_at if hasattr(data, "expires_at") else None,
            status="active",
        )

        db.add(key_record)
        db.commit()
        db.refresh(key_record)

        logger.info(f"API Key 创建成功: {api_key} (租户: {tenant_id})")

        # 解析 permissions（数据库中存的是 JSON 字符串）
        permissions = key_record.permissions
        if isinstance(permissions, str):
            try:
                permissions = json.loads(permissions)
            except (json.JSONDecodeError, TypeError):
                permissions = ["read"]

        # Secret 仅在创建时返回一次
        return {
            "id": key_record.id,
            "name": key_record.key_name or key_record.name,
            "api_key": api_key,
            "api_secret": api_secret,  # 仅此一次
            "permissions": permissions,
            "rate_limit": key_record.rate_limit,
            "expires_at": key_record.expires_at,
            "created_at": key_record.created_at,
        }

    @staticmethod
    def revoke_api_key(db: Session, key_id: int) -> bool:
        """
        吊销 API Key

        Args:
            db: 数据库会话
            key_id: API Key 记录ID

        Returns:
            是否吊销成功
        """
        from .models import OpenAPIKey

        key_record = db.query(OpenAPIKey).filter(OpenAPIKey.id == key_id).first()
        if not key_record:
            return False

        key_record.status = "revoked"
        db.commit()

        logger.info(f"API Key 已吊销: {key_record.api_key} (ID: {key_id})")
        return True

    @staticmethod
    def validate_api_key(db: Session, api_key: str) -> Optional[Any]:
        """
        验证 API Key 是否有效

        Args:
            db: 数据库会话
            api_key: API Key 字符串

        Returns:
            有效的 API Key 记录对象，无效则返回 None
        """
        from .models import OpenAPIKey

        key_record = db.query(OpenAPIKey).filter(
            OpenAPIKey.api_key == api_key,
            OpenAPIKey.status == "active",
        ).first()

        if not key_record:
            logger.warning(f"API Key 验证失败: Key 不存在或已吊销")
            return None

        # 检查是否过期
        if key_record.expires_at and key_record.expires_at < datetime.now():
            logger.warning(f"API Key 已过期: {api_key}")
            return None

        return key_record

    @staticmethod
    def verify_api_secret(api_secret: str, secret_hash: str) -> bool:
        """
        验证 API Secret 是否匹配

        Args:
            api_secret: 原始 Secret
            secret_hash: 存储的哈希值

        Returns:
            是否匹配
        """
        computed_hash = APIKeyService._hash_secret(api_secret)
        return hmac.compare_digest(computed_hash, secret_hash)

    @staticmethod
    def list_api_keys(db: Session, tenant_id: str) -> List[Any]:
        """
        列出租户的所有 API Key

        Args:
            db: 数据库会话
            tenant_id: 租户标识

        Returns:
            API Key 记录列表（不包含 secret）
        """
        from .models import OpenAPIKey

        return db.query(OpenAPIKey).filter(
            OpenAPIKey.tenant_id == tenant_id,
        ).order_by(desc(OpenAPIKey.created_at)).all()

    @staticmethod
    def rotate_api_key(db: Session, key_id: int) -> dict:
        """
        轮换 API Key（生成新的 Key 和 Secret，吊销旧的）

        Args:
            db: 数据库会话
            key_id: API Key 记录ID

        Returns:
            新的 API Key 和 Secret
        """
        from .models import OpenAPIKey

        key_record = db.query(OpenAPIKey).filter(OpenAPIKey.id == key_id).first()
        if not key_record:
            raise ValueError(f"API Key 不存在: {key_id}")

        if key_record.status != "active":
            raise ValueError(f"API Key 状态异常: {key_record.status}")

        # 生成新的 Key 和 Secret
        new_api_key = APIKeyService._generate_api_key()
        new_api_secret = APIKeyService._generate_api_secret()
        new_hashed_secret = APIKeyService._hash_secret(new_api_secret)

        # 更新记录
        old_key = key_record.api_key
        key_record.api_key = new_api_key
        key_record.api_secret_hash = new_hashed_secret
        key_record.last_rotated_at = datetime.now()
        db.commit()
        db.refresh(key_record)

        logger.info(f"API Key 轮换成功: {old_key} -> {new_api_key}")

        return {
            "id": key_record.id,
            "name": key_record.key_name or key_record.name,
            "api_key": new_api_key,
            "api_secret": new_api_secret,
            "rotated_at": key_record.last_rotated_at,
        }

    @staticmethod
    def log_api_call(
        db: Session,
        api_key_id: int,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Any:
        """
        记录 API 调用日志

        Args:
            db: 数据库会话
            api_key_id: API Key 记录ID
            endpoint: 请求端点
            method: HTTP 方法
            status_code: 响应状态码
            response_time_ms: 响应时间（毫秒）
            ip: 客户端IP
            user_agent: User-Agent

        Returns:
            API 调用日志记录
        """
        from .models import APICallLog

        log = APICallLog(
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            ip=ip,
            user_agent=user_agent,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_api_usage(
        db: Session,
        tenant_id: str,
        period: str = "day",
    ) -> Dict[str, Any]:
        """
        获取 API 使用统计

        Args:
            db: 数据库会话
            tenant_id: 租户标识
            period: 统计周期（day / week / month）

        Returns:
            使用统计字典
        """
        from .models import APICallLog, OpenAPIKey
        from sqlalchemy import func
        from datetime import timedelta

        now = datetime.now()

        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        else:  # month
            start = now - timedelta(days=30)

        # 获取租户的所有 API Key ID
        key_ids = db.query(OpenAPIKey.id).filter(
            OpenAPIKey.tenant_id == tenant_id,
            OpenAPIKey.status == "active",
        ).all()
        key_id_list = [k.id for k in key_ids]

        if not key_id_list:
            return {
                "tenant_id": tenant_id,
                "period": period,
                "total_calls": 0,
                "avg_response_time_ms": 0,
                "error_rate": 0,
                "by_endpoint": {},
            }

        # 总调用次数
        total_calls = db.query(func.count(APICallLog.id)).filter(
            APICallLog.api_key_id.in_(key_id_list),
            APICallLog.created_at >= start,
        ).scalar() or 0

        # 平均响应时间
        avg_response = db.query(func.avg(APICallLog.response_time_ms)).filter(
            APICallLog.api_key_id.in_(key_id_list),
            APICallLog.created_at >= start,
        ).scalar() or 0

        # 错误率
        error_calls = db.query(func.count(APICallLog.id)).filter(
            APICallLog.api_key_id.in_(key_id_list),
            APICallLog.created_at >= start,
            APICallLog.status_code >= 400,
        ).scalar() or 0

        # 按端点分组统计
        endpoint_stats = db.query(
            APICallLog.endpoint,
            func.count(APICallLog.id).label("calls"),
            func.avg(APICallLog.response_time_ms).label("avg_time"),
        ).filter(
            APICallLog.api_key_id.in_(key_id_list),
            APICallLog.created_at >= start,
        ).group_by(APICallLog.endpoint).all()

        by_endpoint = {}
        for stat in endpoint_stats:
            by_endpoint[stat.endpoint] = {
                "calls": stat.calls,
                "avg_response_time_ms": round(stat.avg_time, 2) if stat.avg_time else 0,
            }

        return {
            "tenant_id": tenant_id,
            "period": period,
            "total_calls": total_calls,
            "avg_response_time_ms": round(avg_response, 2),
            "error_rate": round(error_calls / total_calls, 4) if total_calls > 0 else 0,
            "by_endpoint": by_endpoint,
        }
