"""
多租户中间件 — 根据请求头识别租户，注入到请求状态中

支持功能：
- 从请求头 X-Tenant-ID 读取租户标识
- 数据库验证租户是否存在且状态为 active
- 将 tenant 信息存入 request.state.tenant
- 白名单路径跳过租户检查
- 未启用多租户模式时自动跳过
"""

import logging
from typing import Optional, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import Depends, HTTPException, status

from .database import SessionLocal

logger = logging.getLogger(__name__)

# 是否启用多租户模式（可通过配置或环境变量控制）
MULTI_TENANT_ENABLED = True

# 白名单路径 — 这些路径不需要租户验证
WHITELIST_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/open/auth/token",
    "/api/v1/billing/plans",
    "/api/v1/plugins",
    "/metrics",
}


class TenantMiddleware(BaseHTTPMiddleware):
    """
    ASGI 多租户中间件

    从请求头 X-Tenant-ID 识别租户，验证后将租户信息注入 request.state.tenant。
    白名单路径和未启用多租户模式时自动跳过验证。
    """

    async def dispatch(self, request: Request, call_next: Callable):
        # 未启用多租户模式时直接放行
        if not MULTI_TENANT_ENABLED:
            return await call_next(request)

        # 白名单路径跳过租户检查
        if request.url.path in WHITELIST_PATHS:
            return await call_next(request)

        # 从请求头读取租户标识
        tenant_id = request.headers.get("X-Tenant-ID")
        if not tenant_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "缺少租户标识，请在请求头中提供 X-Tenant-ID"},
            )

        # 查询数据库验证租户
        db = SessionLocal()
        try:
            from .models import Tenant
            tenant = db.query(Tenant).filter(
                Tenant.tenant_id == tenant_id,
                Tenant.status == "active",
            ).first()

            if not tenant:
                logger.warning(f"租户不存在或已停用: {tenant_id}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": f"租户 {tenant_id} 不存在或已停用"},
                )

            # 将租户信息注入请求状态
            request.state.tenant = tenant
        finally:
            db.close()

        return await call_next(request)


def get_current_tenant(request: Request):
    """
    FastAPI 依赖 — 获取当前请求的租户对象

    用法：
        @router.get("/some-path")
        def some_handler(tenant = Depends(get_current_tenant)):
            ...
    """
    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前请求未关联租户",
        )
    return tenant


def require_tenant_feature(feature: str):
    """
    检查租户是否有某功能权限的工厂函数

    Args:
        feature: 功能标识，如 "api_access", "backtest", "options", "plugin"

    用法：
        @router.get("/advanced")
        def advanced_handler(tenant = Depends(require_tenant_feature("advanced_analytics"))):
            ...
    """
    def check_feature(request: Request):
        tenant = get_current_tenant(request)
        # 解析租户的功能权限列表
        features = []
        if hasattr(tenant, "features") and tenant.features:
            try:
                import json
                features = json.loads(tenant.features) if isinstance(tenant.features, str) else tenant.features
            except (json.JSONDecodeError, TypeError):
                features = []

        if feature not in features:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"当前租户未开通 {feature} 功能权限",
            )
        return tenant
    return check_feature
