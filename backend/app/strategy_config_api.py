"""
策略参数配置 API 端点

提供策略参数的热更新接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from .strategy_config import strategy_config_manager, StrategyConfig
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/strategy/config", tags=["strategy_config"])


class StrategyConfigCreate(BaseModel):
    """创建策略配置"""
    strategy_id: str = Field(..., description="策略ID")
    strategy_name: str = Field(..., description="策略名称")
    strategy_type: str = Field(..., description="策略类型: a_stock_short_term, us_hk_options_event")
    params: Dict[str, Any] = Field(..., description="策略参数")


class StrategyConfigUpdate(BaseModel):
    """更新策略参数"""
    strategy_id: str = Field(..., description="策略ID")
    params: Dict[str, Any] = Field(..., description="要更新的参数")


class StrategyConfigResponse(BaseModel):
    """策略配置响应"""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    params: Dict[str, Any]
    version: int
    updated_at: str
    updated_by: str


@router.post("/", response_model=StrategyConfigResponse)
def create_or_update_config(
    config: StrategyConfigCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    创建或更新策略配置（热更新）

    适用于：
    - 创建新的策略配置
    - 更新现有策略参数（无需重启）
    """
    strategy_config = StrategyConfig(
        strategy_id=config.strategy_id,
        strategy_name=config.strategy_name,
        strategy_type=config.strategy_type,
        params=config.params
    )

    success = strategy_config_manager.set_config(
        strategy_config,
        updated_by=current_user.get("username", "unknown")
    )

    if not success:
        raise HTTPException(status_code=400, detail="参数校验失败，请检查参数范围")

    saved = strategy_config_manager.get_config(config.strategy_id)
    return StrategyConfigResponse(
        strategy_id=saved.strategy_id,
        strategy_name=saved.strategy_name,
        strategy_type=saved.strategy_type,
        params=saved.params,
        version=saved.version,
        updated_at=saved.updated_at,
        updated_by=saved.updated_by
    )


@router.get("/{strategy_id}", response_model=StrategyConfigResponse)
def get_config(strategy_id: str):
    """获取策略配置"""
    config = strategy_config_manager.get_config(strategy_id)
    if not config:
        raise HTTPException(status_code=404, detail="策略配置不存在")
    return StrategyConfigResponse(
        strategy_id=config.strategy_id,
        strategy_name=config.strategy_name,
        strategy_type=config.strategy_type,
        params=config.params,
        version=config.version,
        updated_at=config.updated_at,
        updated_by=config.updated_by
    )


@router.get("/", response_model=List[StrategyConfigResponse])
def list_configs(
    strategy_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """
    获取策略配置列表

    - strategy_type: 可按策略类型过滤
    """
    if strategy_type:
        configs = strategy_config_manager.get_configs_by_type(strategy_type)
    else:
        configs = strategy_config_manager.get_all_configs()

    configs = configs[skip:skip+limit]
    return [
        StrategyConfigResponse(
            strategy_id=c.strategy_id,
            strategy_name=c.strategy_name,
            strategy_type=c.strategy_type,
            params=c.params,
            version=c.version,
            updated_at=c.updated_at,
            updated_by=c.updated_by
        )
        for c in configs
    ]


@router.patch("/{strategy_id}", response_model=StrategyConfigResponse)
def update_params(
    strategy_id: str,
    update: StrategyConfigUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    部分更新策略参数（热更新）

    只更新传入的参数，保留其他参数不变。
    """
    config = strategy_config_manager.get_config(strategy_id)
    if not config:
        raise HTTPException(status_code=404, detail="策略配置不存在")

    # 合并参数
    new_params = {**config.params, **update.params}
    config.params = new_params

    success = strategy_config_manager.set_config(
        config,
        updated_by=current_user.get("username", "unknown")
    )

    if not success:
        raise HTTPException(status_code=400, detail="参数校验失败")

    updated = strategy_config_manager.get_config(strategy_id)
    return StrategyConfigResponse(
        strategy_id=updated.strategy_id,
        strategy_name=updated.strategy_name,
        strategy_type=updated.strategy_type,
        params=updated.params,
        version=updated.version,
        updated_at=updated.updated_at,
        updated_by=updated.updated_by
    )


@router.get("/{strategy_id}/history")
def get_change_history(
    strategy_id: str,
    limit: int = 50
):
    """
    获取策略参数变更历史
    """
    return {
        "strategy_id": strategy_id,
        "changes": strategy_config_manager.get_change_history(strategy_id, limit)
    }


@router.post("/{strategy_id}/rollback")
def rollback_config(
    strategy_id: str,
    version: int,
    current_user: dict = Depends(get_current_user)
):
    """
    回滚策略配置到指定版本

    Note: 当前实现需要完整的版本存储支持
    """
    success = strategy_config_manager.rollback(strategy_id, version)
    if not success:
        raise HTTPException(status_code=404, detail="策略配置不存在或回滚失败")
    return {"message": f"已请求回滚到版本 {version}"}