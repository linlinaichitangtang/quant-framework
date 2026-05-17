"""
阿尔法因子库 API 端点

提供因子查询、计算和分析接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

from .alpha_factors import alpha_factor_library, FactorCategory, FactorDefinition
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/factors", tags=["alpha_factors"])


class FactorListResponse(BaseModel):
    """因子列表响应"""
    total: int
    categories: Dict[str, List[str]]


class FactorDetailResponse(BaseModel):
    """因子详情响应"""
    name: str
    category: str
    description: str
    required_columns: List[str]
    lower_is_better: bool


class FactorComputeRequest(BaseModel):
    """计算因子请求"""
    factor_names: List[str] = Field(..., description="因子名称列表")
    data: Dict[str, List[Any]] = Field(..., description="股票数据 {column: values}")


class FactorAnalyzeRequest(BaseModel):
    """因子分析请求"""
    factor_name: str = Field(..., description="因子名称")
    factor_values: List[float] = Field(..., description="因子值")
    forward_returns: List[float] = Field(..., description="未来收益率")
    n_quantiles: int = Field(5, ge=2, le=10, description="分位数数量")


@router.get("/", response_model=FactorListResponse)
def list_factors(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    获取因子列表

    - category: 可按类别过滤（price/volume/momentum/volatility/quality/value/growth/custom）
    """
    if category:
        try:
            cat = FactorCategory(category)
            factor_names = alpha_factor_library.list_factors(cat)
            return FactorListResponse(
                total=len(factor_names),
                categories={cat.value: factor_names}
            )
        except ValueError:
            raise HTTPException(status_code=400, detail=f"未知类别: {category}")

    # 按类别返回
    by_category = alpha_factor_library.list_by_category()
    return FactorListResponse(
        total=len(alpha_factor_library.list_factors()),
        categories={cat.value: factors for cat, factors in by_category.items()}
    )


@router.get("/{factor_name}", response_model=FactorDetailResponse)
def get_factor_detail(
    factor_name: str,
    current_user: dict = Depends(get_current_user)
):
    """获取因子详情"""
    factor = alpha_factor_library.get_factor(factor_name)
    if not factor:
        raise HTTPException(status_code=404, detail=f"因子不存在: {factor_name}")

    return FactorDetailResponse(
        name=factor.name,
        category=factor.category.value,
        description=factor.description,
        required_columns=factor.required_columns,
        lower_is_better=factor.lower_is_better
    )


@router.post("/compute")
def compute_factors(
    request: FactorComputeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    批量计算因子

    示例请求:
    ```json
    {
        "factor_names": ["ma5", "ma20", "volume_ratio"],
        "data": {
            "close": [10.0, 10.5, 11.0],
            "volume": [1000, 1500, 2000]
        }
    }
    ```
    """
    try:
        # 构建 DataFrame
        df = pd.DataFrame(request.data)

        # 计算因子
        result = alpha_factor_library.compute_factors(request.factor_names, df)

        return {
            "factor_names": request.factor_names,
            "values": result.to_dict(orient='list'),
            "computed_count": len(result)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze")
def analyze_factor(
    request: FactorAnalyzeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    分析因子有效性

    计算 IC、IR、Rank IC 和分位数收益。
    """
    try:
        # 构建 Series
        factor_values = pd.Series(request.factor_values, name=request.factor_name)
        forward_returns = pd.Series(request.forward_returns, name="returns")

        # 分析
        result = alpha_factor_library.analyze_factor(
            factor_values,
            forward_returns,
            request.n_quantiles
        )

        return {
            "factor_name": result.factor_name,
            "ic": result.ic,
            "ir": result.ir,
            "rank_ic": result.rank_ic,
            "returns_by_quantile": result.returns_by_quantile,
            "interpretation": _interpret_ic(result.ic, result.ir)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
def register_custom_factor(
    factor_name: str,
    category: str,
    description: str,
    required_columns: List[str],
    current_user: dict = Depends(get_current_user)
):
    """
    注册自定义因子

    Note: 自定义因子需要通过配置文件或代码实现。
    此接口仅记录元数据。
    """
    # 检查是否已存在
    if alpha_factor_library.get_factor(factor_name):
        return {"message": f"因子 {factor_name} 已存在，使用现有实现"}

    # 注意：这里无法直接注册计算函数，需要通过代码
    return {
        "message": f"请实现因子 {factor_name} 的计算逻辑并注册",
        "factor_name": factor_name,
        "category": category,
        "required_columns": required_columns
    }


@router.get("/categories/list")
def list_categories():
    """获取因子类别列表"""
    return {
        "categories": [
            {"value": cat.value, "description": _category_description(cat)}
            for cat in FactorCategory
        ]
    }


def _interpret_ic(ic: float, ir: float) -> str:
    """解释 IC/IR 指标"""
    abs_ic = abs(ic)
    abs_ir = abs(ir)

    if abs_ic < 0.02:
        ic_text = "IC接近零，因子无效"
    elif abs_ic < 0.05:
        ic_text = "IC较低，因子效果一般"
    elif abs_ic < 0.1:
        ic_text = "IC中等，因子有一定预测能力"
    else:
        ic_text = "IC较高，因子预测能力强"

    if abs_ir < 0.3:
        ir_text = "，IR不稳定"
    elif abs_ir < 0.5:
        ir_text = "，IR一般"
    else:
        ir_text = "，IR稳定"

    return ic_text + ir_text + f"（IC={ic:.4f}, IR={ir:.4f}）"


def _category_description(category: FactorCategory) -> str:
    """类别描述"""
    descriptions = {
        FactorCategory.PRICE: "价格相关因子",
        FactorCategory.VOLUME: "成交量/额相关因子",
        FactorCategory.MOMENTUM: "动量/趋势因子",
        FactorCategory.VOLATILITY: "波动率因子",
        FactorCategory.QUALITY: "基本面质量因子",
        FactorCategory.VALUE: "价值因子",
        FactorCategory.GROWTH: "成长因子",
        FactorCategory.CUSTOM: "用户自定义因子",
    }
    return descriptions.get(category, "")