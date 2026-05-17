"""
策略 DSL API 端点

提供自定义策略的创建、验证、执行接口。
"""

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .strategy_dsl import dsl_evaluator, StrategyDSL, A_STOCK_SHORT_TERM_TEMPLATE, OPTIONS_EVENT_TEMPLATE
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/strategy/dsl", tags=["strategy_dsl"])


class DSLStrategyCreate(BaseModel):
    """创建 DSL 策略"""
    strategy_id: str = Field(..., description="策略ID（唯一标识）")
    name: str = Field(..., description="策略名称")
    config: Dict[str, Any] = Field(..., description="策略配置（YAML格式解析后的字典）")


class DSLValidateRequest(BaseModel):
    """验证 DSL 策略"""
    config: Dict[str, Any] = Field(..., description="策略配置")


class DSLEvaluateRequest(BaseModel):
    """评估单只股票"""
    strategy_id: str = Field(..., description="策略ID")
    data: Dict[str, Any] = Field(..., description="股票数据")


class DSLSignalResponse(BaseModel):
    """信号响应"""
    action: str
    symbol: str
    market: str
    reason: str
    matched_conditions: List[str]
    strategy_name: str


@router.post("/validate")
def validate_dsl_config(
    request: DSLValidateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    验证 DSL 策略配置

    检查配置格式是否正确，条件是否合法。
    """
    try:
        strategy = dsl_evaluator.load_from_dict(request.config)
        return {
            "valid": True,
            "strategy_name": strategy.name,
            "market": strategy.market,
            "conditions_count": len(strategy.selection.conditions)
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


@router.post("/", response_model=Dict)
def create_dsl_strategy(
    request: DSLStrategyCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    创建 DSL 策略

    将策略配置解析并缓存。
    """
    try:
        strategy = dsl_evaluator.load_from_dict(request.config)
        dsl_evaluator.cache_strategy(request.strategy_id, strategy)
        return {
            "strategy_id": request.strategy_id,
            "name": strategy.name,
            "market": strategy.market,
            "message": "策略创建成功"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"策略创建失败: {str(e)}")


@router.get("/{strategy_id}", response_model=Dict)
def get_dsl_strategy(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """获取 DSL 策略详情"""
    strategy = dsl_evaluator.get_cached_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    return {
        "strategy_id": strategy_id,
        "name": strategy.name,
        "version": strategy.version,
        "description": strategy.description,
        "market": strategy.market,
        "conditions": [
            {
                "field": c.field,
                "operator": c.operator,
                "value": c.value,
                "description": c.description
            }
            for c in strategy.selection.conditions
        ],
        "risk": strategy.risk
    }


@router.post("/evaluate")
def evaluate_stock(
    request: DSLEvaluateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    评估单只股票是否满足策略条件

    用于在选股前验证股票。
    """
    strategy = dsl_evaluator.get_cached_strategy(request.strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    result = dsl_evaluator.generate_signal(strategy, request.data)

    if result:
        return {
            "matched": True,
            "signal": DSLSignalResponse(**result)
        }
    else:
        return {
            "matched": False,
            "signal": None
        }


@router.post("/evaluate-batch")
def evaluate_stocks_batch(
    strategy_id: str,
    stocks: List[Dict[str, Any]],
    current_user: dict = Depends(get_current_user)
):
    """
    批量评估多只股票

    返回满足条件的股票列表。
    """
    strategy = dsl_evaluator.get_cached_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    matched = []
    for data in stocks:
        result = dsl_evaluator.generate_signal(strategy, data)
        if result:
            matched.append(DSLSignalResponse(**result))

    return {
        "total": len(stocks),
        "matched_count": len(matched),
        "matched": matched
    }


@router.get("/templates/list")
def list_dsl_templates():
    """
    获取预定义的策略模板

    可用于快速创建策略。
    """
    return {
        "templates": [
            {
                "id": "a_stock_short_term",
                "name": "A股超短策略模板",
                "description": "基于技术指标的A股超短选股策略",
                "config": dsl_evaluator.load_from_yaml(A_STOCK_SHORT_TERM_TEMPLATE).__dict__
            },
            {
                "id": "us_options_event",
                "name": "期权事件驱动模板",
                "description": "基于财报事件的期权策略",
                "config": dsl_evaluator.load_from_yaml(OPTIONS_EVENT_TEMPLATE).__dict__
            }
        ]
    }


@router.get("/templates/{template_id}/config")
def get_template_config(template_id: str):
    """
    获取模板的原始配置（YAML格式）

    可直接用于创建策略。
    """
    if template_id == "a_stock_short_term":
        return {"yaml": A_STOCK_SHORT_TERM_TEMPLATE}
    elif template_id == "us_options_event":
        return {"yaml": OPTIONS_EVENT_TEMPLATE}
    else:
        raise HTTPException(status_code=404, detail="模板不存在")


@router.delete("/{strategy_id}")
def delete_dsl_strategy(
    strategy_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除 DSL 策略"""
    dsl_evaluator.remove_cached_strategy(strategy_id)
    return {"message": f"策略 {strategy_id} 已删除"}