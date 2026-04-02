"""
插件管理 API 路由

路由前缀 /api/v1/plugins，提供插件市场浏览、插件发布、安装/卸载、执行、评分等功能。
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .plugin_system import PluginManager
from .tenant_middleware import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/plugins", tags=["插件管理"])


# ========== 请求/响应 Schema ==========

class PluginCreateRequest(BaseModel):
    """发布插件请求"""
    name: str = Field(..., min_length=1, max_length=200, description="插件名称")
    description: Optional[str] = Field(None, max_length=2000, description="插件描述")
    version: str = Field("1.0.0", description="版本号")
    category: str = Field("other", description="分类 signal/risk_control/data_analysis/other")
    author: Optional[str] = Field(None, description="作者")
    hooks: Optional[List[str]] = Field(None, description="钩子列表")
    config_schema: Optional[dict] = Field(None, description="配置Schema")


class PluginUpdateRequest(BaseModel):
    """更新插件请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    version: Optional[str] = None
    category: Optional[str] = None
    hooks: Optional[List[str]] = None
    config_schema: Optional[dict] = None
    status: Optional[str] = None


class PluginInstallRequest(BaseModel):
    """安装插件请求"""
    config: Optional[dict] = Field(None, description="插件配置")


class PluginExecuteRequest(BaseModel):
    """执行插件方法请求"""
    method: str = Field(..., description="方法名称")
    params: Optional[dict] = Field(None, description="方法参数")


class PluginRateRequest(BaseModel):
    """评分插件请求"""
    score: int = Field(..., ge=1, le=5, description="评分 1-5")


# ========== 接口实现 ==========

@router.get("")
def list_plugins(
    category: Optional[str] = Query(None, description="按分类筛选"),
    plugin_status: Optional[str] = Query(None, alias="status", description="按状态筛选"),
):
    """
    列出插件市场

    浏览所有可用插件，支持按分类和状态筛选。
    """
    manager = PluginManager.get_instance()
    plugins = manager.list_plugins(category=category, status=plugin_status)

    data = [
        {
            "plugin_id": p["plugin_id"],
            "name": p["name"],
            "description": p["description"],
            "version": p["version"],
            "category": p["category"],
            "author": p["author"],
            "hooks": p["hooks"],
            "status": p["status"],
            "rating_avg": p.get("rating_avg", 0),
            "rating_count": p.get("rating_count", 0),
            "install_count": p.get("install_count", 0),
        }
        for p in plugins
    ]

    return {"total": len(data), "data": data}


@router.get("/{plugin_id}")
def get_plugin_detail(plugin_id: str):
    """
    获取插件详情

    根据插件ID获取插件的详细信息。
    """
    manager = PluginManager.get_instance()
    plugin = manager.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    return {
        "plugin_id": plugin["plugin_id"],
        "name": plugin["name"],
        "description": plugin["description"],
        "version": plugin["version"],
        "category": plugin["category"],
        "author": plugin["author"],
        "hooks": plugin["hooks"],
        "config_schema": plugin.get("config_schema", {}),
        "status": plugin["status"],
        "rating_avg": plugin.get("rating_avg", 0),
        "rating_count": plugin.get("rating_count", 0),
        "install_count": plugin.get("install_count", 0),
        "created_at": plugin.get("created_at"),
        "updated_at": plugin.get("updated_at"),
    }


@router.post("")
def publish_plugin(
    data: PluginCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    发布插件（需要认证）

    发布新插件到插件市场。
    """
    manager = PluginManager.get_instance()

    plugin_info = {
        "name": data.name,
        "description": data.description,
        "version": data.version,
        "category": data.category,
        "author": data.author or current_user.get("username", "anonymous"),
        "hooks": data.hooks or [],
        "config_schema": data.config_schema or {},
    }

    plugin = manager.register_plugin(plugin_info)

    logger.info(f"插件发布成功: {plugin['plugin_id']} by {current_user.get('username')}")

    return {
        "plugin_id": plugin["plugin_id"],
        "name": plugin["name"],
        "message": "插件发布成功",
    }


@router.put("/{plugin_id}")
def update_plugin(
    plugin_id: str,
    data: PluginUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    更新插件（需要认证）

    更新已发布插件的信息。
    """
    manager = PluginManager.get_instance()
    plugin = manager.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    # 更新插件信息
    update_data = data.model_dump(exclude_unset=True)
    plugin.update(update_data)
    plugin["updated_at"] = __import__("datetime").datetime.now().isoformat()

    # 重新注册以更新
    manager.register_plugin(plugin)

    return {"message": "插件更新成功", "plugin_id": plugin_id}


@router.delete("/{plugin_id}")
def delete_plugin(
    plugin_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    删除插件（需要认证）

    从插件市场删除插件。
    """
    manager = PluginManager.get_instance()
    success = manager.unregister_plugin(plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail="插件不存在")

    return {"message": "插件已删除", "plugin_id": plugin_id}


@router.post("/{plugin_id}/install")
def install_plugin(
    plugin_id: str,
    data: PluginInstallRequest,
    current_user: dict = Depends(get_current_user),
    tenant=Depends(get_current_tenant),
):
    """
    安装插件

    将插件安装到当前租户。
    """
    manager = PluginManager.get_instance()

    try:
        result = manager.install_plugin(
            tenant_id=tenant.tenant_id,
            plugin_id=plugin_id,
            config=data.config,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{plugin_id}/install")
def uninstall_plugin(
    plugin_id: str,
    current_user: dict = Depends(get_current_user),
    tenant=Depends(get_current_tenant),
):
    """
    卸载插件

    从当前租户卸载插件。
    """
    manager = PluginManager.get_instance()
    success = manager.uninstall_plugin(
        tenant_id=tenant.tenant_id,
        plugin_id=plugin_id,
    )
    if not success:
        raise HTTPException(status_code=400, detail="插件未安装或卸载失败")

    return {"message": "插件已卸载", "plugin_id": plugin_id}


@router.post("/{plugin_id}/execute")
def execute_plugin(
    plugin_id: str,
    data: PluginExecuteRequest,
    current_user: dict = Depends(get_current_user),
    tenant=Depends(get_current_tenant),
):
    """
    执行插件方法

    调用插件的指定方法。
    """
    manager = PluginManager.get_instance()

    result = manager.execute_plugin(
        plugin_id=plugin_id,
        method=data.method,
        params=data.params,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "执行失败"))

    return result


@router.post("/{plugin_id}/rate")
def rate_plugin(
    plugin_id: str,
    data: PluginRateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    评分插件

    为插件打分（1-5分）。
    """
    manager = PluginManager.get_instance()
    plugin = manager.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    # 更新评分（简单平均）
    old_avg = plugin.get("rating_avg", 0)
    old_count = plugin.get("rating_count", 0)
    new_count = old_count + 1
    new_avg = (old_avg * old_count + data.score) / new_count

    plugin["rating_avg"] = round(new_avg, 2)
    plugin["rating_count"] = new_count

    # 重新注册以更新
    manager.register_plugin(plugin)

    return {
        "message": "评分成功",
        "plugin_id": plugin_id,
        "rating_avg": plugin["rating_avg"],
        "rating_count": plugin["rating_count"],
    }
