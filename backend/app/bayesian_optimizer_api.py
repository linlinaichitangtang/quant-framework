"""
贝叶斯优化 API 端点

提供超参数优化的贝叶斯优化接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from .bayesian_optimizer import BayesianOptimizer
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/ml/bayesian", tags=["bayesian_optimization"])


class ParamSpaceItem(BaseModel):
    """参数空间定义"""
    name: str
    min_value: float
    max_value: float


class BayesianOptimizeRequest(BaseModel):
    """贝叶斯优化请求"""
    study_name: str = Field(..., description="研究名称")
    param_space: List[ParamSpaceItem] = Field(..., description="参数空间")
    n_iterations: int = Field(20, ge=5, le=100, description="迭代次数")
    n_initial_points: int = Field(3, ge=1, le=10, description="初始随机点数")
    minimize: bool = Field(True, description="是否最小化")
    acquisition: str = Field("ei", description="采集函数: ei/ucb/pi")


class BayesianSuggestRequest(BaseModel):
    """建议下一个参数"""
    study_name: str


class BayesianObserveRequest(BaseModel):
    """观察目标值"""
    study_name: str
    params: Dict[str, float]
    value: float


class BayesianSuggestResponse(BaseModel):
    """建议响应"""
    params: Dict[str, float]
    iteration: int


class BayesianResultResponse(BaseModel):
    """优化结果"""
    study_name: str
    best_params: Dict[str, float]
    best_value: float
    n_iterations: int
    observations: List[Dict[str, Any]]


# 内存中存储优化研究
_optimizers: Dict[str, BayesianOptimizer] = {}


@router.post("/studies", response_model=Dict)
def create_study(
    request: BayesianOptimizeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    创建优化研究

    定义参数空间和优化目标。
    """
    study_name = f"{current_user.get('username', 'anonymous')}_{request.study_name}"

    if study_name in _optimizers:
        return {"message": f"研究 {request.study_name} 已存在", "study_name": study_name}

    # 构建参数空间
    param_space = {}
    for p in request.param_space:
        param_space[p.name] = (p.min_value, p.max_value)

    # 注意：这里需要提供一个目标函数，实际使用时应该通过训练服务调用
    # 暂时使用一个占位函数
    def placeholder_objective(params: Dict[str, float]) -> float:
        # 这应该被替换为真实的目标函数
        return 0.0

    optimizer = BayesianOptimizer(
        param_space=param_space,
        objective_func=placeholder_objective,
        minimize=request.minimize,
        acquisition=request.acquisition
    )

    _optimizers[study_name] = optimizer

    return {
        "study_name": study_name,
        "param_space": param_space,
        "message": "研究已创建"
    }


@router.get("/studies/{study_name}/suggest", response_model=BayesianSuggestResponse)
def suggest_params(
    study_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    建议下一个待评估的参数组合

    使用贝叶斯优化算法智能选择下一个参数点。
    """
    full_name = f"{current_user.get('username', 'anonymous')}_{study_name}"
    optimizer = _optimizers.get(full_name)

    if not optimizer:
        raise HTTPException(status_code=404, detail=f"研究 {study_name} 不存在")

    params = optimizer.suggest()
    iteration = len(optimizer._observations)

    return BayesianSuggestResponse(
        params=params,
        iteration=iteration
    )


@router.post("/studies/{study_name}/observe")
def observe_value(
    study_name: str,
    request: BayesianObserveRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    观察目标函数值

    记录参数组合对应的目标函数值，用于更新贝叶斯模型。
    """
    full_name = f"{current_user.get('username', 'anonymous')}_{study_name}"
    optimizer = _optimizers.get(full_name)

    if not optimizer:
        raise HTTPException(status_code=404, detail=f"研究 {study_name} 不存在")

    optimizer.observe(request.params, request.value)

    return {
        "message": "已记录观察结果",
        "total_observations": len(optimizer._observations)
    }


@router.get("/studies/{study_name}/best")
def get_best_params(
    study_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取当前最优参数
    """
    full_name = f"{current_user.get('username', 'anonymous')}_{study_name}"
    optimizer = _optimizers.get(full_name)

    if not optimizer:
        raise HTTPException(status_code=404, detail=f"研究 {study_name} 不存在")

    best_params, best_value = optimizer.get_best()

    if best_params is None:
        return {"message": "暂无观察结果"}

    return {
        "best_params": best_params,
        "best_value": best_value
    }


@router.get("/studies/{study_name}/results", response_model=BayesianResultResponse)
def get_study_results(
    study_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取优化研究结果
    """
    full_name = f"{current_user.get('username', 'anonymous')}_{study_name}"
    optimizer = _optimizers.get(full_name)

    if not optimizer:
        raise HTTPException(status_code=404, detail=f"研究 {study_name} 不存在")

    best_params, best_value = optimizer.get_best()

    return BayesianResultResponse(
        study_name=study_name,
        best_params=best_params or {},
        best_value=best_value or 0.0,
        n_iterations=len(optimizer._observations),
        observations=[
            {"params": obs.params, "value": obs.value, "time": obs.timestamp.isoformat()}
            for obs in optimizer._observations
        ]
    )


@router.get("/studies")
def list_studies(current_user: dict = Depends(get_current_user)):
    """列出用户的所有研究"""
    prefix = f"{current_user.get('username', 'anonymous')}_"
    studies = [name[len(prefix):] for name in _optimizers.keys() if name.startswith(prefix)]
    return {"studies": studies}


@router.delete("/studies/{study_name}")
def delete_study(
    study_name: str,
    current_user: dict = Depends(get_current_user)
):
    """删除优化研究"""
    full_name = f"{current_user.get('username', 'anonymous')}_{study_name}"
    if full_name in _optimizers:
        del _optimizers[full_name]
        return {"message": f"研究 {study_name} 已删除"}
    return {"message": f"研究 {study_name} 不存在"}