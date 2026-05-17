"""
时序交叉验证 API 端点

提供回测中的时序交叉验证功能。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import numpy as np

from .cross_validation import TimeSeriesCrossValidator, WalkForwardAnalyzer, DataLeakageDetector
from .auth import get_current_user

router = APIRouter(prefix="/api/v1/backtest/cv", tags=["cross_validation"])


class CrossValidationConfig(BaseModel):
    """交叉验证配置"""
    n_splits: int = Field(5, ge=2, le=20, description="分割数量")
    test_size: Optional[int] = Field(None, description="验证集大小（天数）")
    train_size: Optional[int] = Field(None, description="训练集最小大小")
    gap: int = Field(0, ge=0, description="训练集和验证集的间隔")
    variable_size: bool = Field(True, description="True=滚动增长，False=固定滑动窗口")


class CrossValidationRunRequest(BaseModel):
    """运行交叉验证请求"""
    dates: List[str] = Field(..., description="日期列表 ISO格式")
    X: List[List[float]] = Field(..., description="特征矩阵")
    y: List[float] = Field(..., description="目标变量")


class LeakageCheckRequest(BaseModel):
    """泄露检测请求"""
    X: List[List[float]] = Field(..., description="特征矩阵")
    y: List[float] = Field(..., description="目标变量")
    feature_names: List[str] = Field(default=[], description="特征名称")
    max_lag: int = Field(5, ge=1, le=20, description="最大滞后阶数")


@router.post("/validate")
def create_cv_config(
    config: CrossValidationConfig,
    current_user: dict = Depends(get_current_user)
):
    """
    创建时序交叉验证配置

    返回分割的详细信息。
    """
    validator = TimeSeriesCrossValidator(
        n_splits=config.n_splits,
        test_size=config.test_size,
        train_size=config.train_size,
        gap=config.gap,
        variable_size=config.variable_size
    )

    return {
        "config": {
            "n_splits": config.n_splits,
            "test_size": config.test_size,
            "train_size": config.train_size,
            "gap": config.gap,
            "variable_size": config.variable_size
        },
        "message": "配置已创建，可用于后续验证"
    }


@router.post("/run")
def run_cross_validation(
    request: CrossValidationRunRequest,
    config: CrossValidationConfig = CrossValidationConfig(),
    current_user: dict = Depends(get_current_user)
):
    """
    运行时序交叉验证（Walk-Forward 分析）

    在每个时间序列分割上训练和验证模型。
    """
    try:
        # 解析日期
        dates = [datetime.fromisoformat(d) for d in request.dates]
        dates = sorted(dates)

        # 转换为 numpy 数组
        X = np.array(request.X)
        y = np.array(request.y)

        if len(dates) != len(y):
            raise HTTPException(status_code=400, detail="日期长度与y长度不匹配")
        if len(X) != len(y):
            raise HTTPException(status_code=400, detail="X长度与y长度不匹配")

        # 创建验证器
        validator = TimeSeriesCrossValidator(
            n_splits=config.n_splits,
            test_size=config.test_size,
            train_size=config.train_size,
            gap=config.gap,
            variable_size=config.variable_size
        )

        # 创建分析器
        analyzer = WalkForwardAnalyzer(validator)

        # 定义训练和预测函数（线性回归作为示例）
        def train_func(X_train, y_train):
            result = np.linalg.lstsq(X_train, y_train, rcond=None)
            return result[0]

        def predict_func(model, X_test):
            return X_test @ model

        def metrics_func(y_true, y_pred):
            mse = float(np.mean((y_true - y_pred) ** 2))
            mae = float(np.mean(np.abs(y_true - y_pred)))
            return {"mse": mse, "mae": mae}

        # 运行分析
        result = analyzer.run(dates, X, y, train_func, predict_func, metrics_func)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"交叉验证执行失败: {str(e)}")


@router.post("/leakage-check")
def check_data_leakage(
    request: LeakageCheckRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    检测未来数据泄露

    检查特征是否与未来目标存在异常相关性。
    """
    try:
        X = np.array(request.X)
        y = np.array(request.y)

        if request.feature_names:
            feature_names = request.feature_names
        else:
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]

        # 检查滞后相关性
        lag_correlations = DataLeakageDetector.check_future_correlation(
            X, y, request.max_lag
        )

        # 检查特征泄露
        high_correlations = DataLeakageDetector.check_feature_leakage(
            X, y, feature_names
        )

        return {
            "lag_correlations": lag_correlations,
            "potential_leakage": high_correlations,
            "message": "检测完成"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"泄露检测失败: {str(e)}")


@router.get("/splits-preview")
def preview_splits(
    n_samples: int = Field(100, ge=10, le=10000),
    n_splits: int = Field(5, ge=2, le=20),
    test_size: int = Field(5, ge=1),
    gap: int = Field(0),
    current_user: dict = Depends(get_current_user)
):
    """
    预览交叉验证分割

    生成示例日期序列，展示分割结果。
    """
    # 生成示例日期
    base_date = datetime(2024, 1, 1)
    dates = [base_date.replace(day=i % 30 + 1, month=(i // 30) % 12 + 1)
             for i in range(n_samples)]
    dates = sorted(set(dates))[:n_samples]

    validator = TimeSeriesCrossValidator(
        n_splits=n_splits,
        test_size=test_size,
        gap=gap,
        variable_size=True
    )

    try:
        splits = validator.split(dates)
        return {
            "n_samples": n_samples,
            "config": {
                "n_splits": n_splits,
                "test_size": test_size,
                "gap": gap,
                "variable_size": True
            },
            "splits": [
                {
                    "fold": s.fold,
                    "train_period": f"{s.train_start.date()} ~ {s.train_end.date()}",
                    "val_period": f"{s.val_start.date()} ~ {s.val_end.date()}",
                    "train_size": (s.train_end - s.train_start).days,
                    "val_size": (s.val_end - s.val_start).days
                }
                for s in splits
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))