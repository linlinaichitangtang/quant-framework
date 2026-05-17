"""
深度因子合成 API 端点

提供因子合成和特征交叉分析接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import numpy as np

from .factor_synthesis import FactorSynthesizer, FactorCrossingAnalyzer, FactorSynthConfig
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/factors/synthesis", tags=["factor_synthesis"])


class SynthesisConfig(BaseModel):
    """合成配置"""
    input_factors: List[str] = Field(..., description="输入因子列表")
    hidden_dims: List[int] = Field([64, 32, 16], description="隐藏层维度")
    output_dim: int = Field(1, ge=1, le=10)
    dropout: float = Field(0.1, ge=0, le=0.5)
    learning_rate: float = Field(0.001, ge=1e-5, le=1)
    n_epochs: int = Field(100, ge=10, le=1000)
    batch_size: int = Field(32, ge=8, le=512)


class SynthesisRequest(BaseModel):
    """合成请求"""
    X: List[List[float]] = Field(..., description="因子矩阵 (n_samples, n_factors)")
    y: List[float] = Field(..., description="目标变量 (n_samples,)")
    factor_names: List[str] = Field(..., description="因子名称")
    config: Optional[SynthesisConfig] = None


class CrossAnalysisRequest(BaseModel):
    """交叉分析请求"""
    X: List[List[float]] = Field(..., description="因子矩阵")
    y: List[float] = Field(..., description="目标变量")
    factor_names: List[str] = Field(..., description="因子名称")
    threshold: float = Field(0.05, ge=0, description="协同阈值")


# 内存中存储的合成器
_synthesizers: Dict[str, FactorSynthesizer] = {}


@router.post("/train")
def train_synthesizer(
    study_name: str,
    request: SynthesisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    训练因子合成模型

    学习因子间的非线性组合。
    """
    try:
        # 转换数据
        X = np.array(request.X)
        y = np.array(request.y)

        if len(X) != len(y):
            raise HTTPException(status_code=400, detail="X 和 y 长度不匹配")

        if X.shape[1] != len(request.factor_names):
            raise HTTPException(status_code=400, detail="因子数量与名称不匹配")

        # 配置
        config = request.config or FactorSynthConfig(input_factors=request.factor_names)
        if not isinstance(config, FactorSynthConfig):
            config = FactorSynthConfig(
                input_factors=request.factor_names,
                hidden_dims=config.hidden_dims or [64, 32, 16],
                n_epochs=config.n_epochs or 100,
                learning_rate=config.learning_rate or 0.001,
                batch_size=config.batch_size or 32,
                dropout=config.dropout or 0.1
            )

        # 训练
        synthesizer = FactorSynthesizer(config)
        result = synthesizer.fit(X, y, request.factor_names)

        # 存储
        key = f"{current_user.get('username', 'anonymous')}_{study_name}"
        _synthesizers[key] = synthesizer

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
def predict_synthetic(
    study_name: str,
    X: List[List[float]],
    current_user: dict = Depends(get_current_user)
):
    """
    使用合成模型预测

    返回合成因子值。
    """
    key = f"{current_user.get('username', 'anonymous')}_{study_name}"
    synthesizer = _synthesizers.get(key)

    if not synthesizer:
        raise HTTPException(status_code=404, detail="合成模型不存在")

    try:
        X_arr = np.array(X)
        synthetic = synthesizer.predict(X_arr)
        return {
            "study_name": study_name,
            "synthetic_factors": synthetic.tolist(),
            "n_samples": len(synthetic)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cross-analysis")
def analyze_factor_interactions(
    request: CrossAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    分析因子交互作用

    找出协同因子对和特征交叉模式。
    """
    try:
        X = np.array(request.X)
        y = np.array(request.y)

        analyzer = FactorCrossingAnalyzer()

        # 交互矩阵
        interaction_matrix = analyzer.compute_interaction_matrix(X, y, request.factor_names)

        # 协同因子对
        synergy_pairs = analyzer.find_synergy_pairs(
            X, y, request.factor_names, request.threshold
        )

        return {
            "interaction_matrix": interaction_matrix.tolist(),
            "factor_names": request.factor_names,
            "synergy_pairs": synergy_pairs[:10],  # 最多返回10对
            "n_synergy_pairs": len(synergy_pairs)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/studies")
def list_synthesis_studies(current_user: dict = Depends(get_current_user)):
    """列出用户的合成模型"""
    prefix = f"{current_user.get('username', 'anonymous')}_"
    studies = [name[len(prefix):] for name in _synthesizers.keys() if name.startswith(prefix)]
    return {"studies": studies}


@router.delete("/studies/{study_name}")
def delete_synthesizer(
    study_name: str,
    current_user: dict = Depends(get_current_user)
):
    """删除合成模型"""
    key = f"{current_user.get('username', 'anonymous')}_{study_name}"
    if key in _synthesizers:
        del _synthesizers[key]
        return {"message": f"合成模型 {study_name} 已删除"}
    return {"message": f"合成模型 {study_name} 不存在"}