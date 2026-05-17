"""
时序交叉验证框架

提供时间序列数据的交叉验证，防止未来数据泄露。
支持 Walk-Forward 分析。
"""

import logging
import numpy as np
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesSplit:
    """时间序列分割"""
    train_start: datetime
    train_end: datetime
    val_start: datetime
    val_end: datetime
    fold: int

    def __repr__(self):
        return (f"Fold {self.fold}: "
                f"Train [{self.train_start.date()} ~ {self.train_end.date()}] "
                f"Val [{self.val_start.date()} ~ {self.val_end.date()}]")


class TimeSeriesCrossValidator:
    """
    时序交叉验证器

    特点：
    - 训练集总是在验证集之前
    - 避免未来数据泄露
    - 支持滑动窗口（Walk-Forward）
    """

    def __init__(
        self,
        n_splits: int = 5,
        test_size: Optional[int] = None,  # 验证集大小（天数或样本数）
        train_size: Optional[int] = None,  # 训练集最小大小
        gap: int = 0,  # 训练集和验证集之间的间隔
        variable_size: bool = True  # 训练集是否随fold增长
    ):
        """
        Args:
            n_splits: 分割数量
            test_size: 验证集大小（天数），如果为None则自动计算
            train_size: 训练集最小大小
            gap: 训练集和验证集之间的间隔（防止数据泄露）
            variable_size: True=滚动增长训练集，False=固定大小滑动窗口
        """
        self.n_splits = n_splits
        self.test_size = test_size
        self.train_size = train_size
        self.gap = gap
        self.variable_size = variable_size

    def split(
        self,
        dates: List[datetime],
        y: Optional[np.ndarray] = None
    ) -> List[TimeSeriesSplit]:
        """
        生成分割索引

        Args:
            dates: 日期列表（必须有序）
            y: 目标变量（可选）

        Returns:
            TimeSeriesSplit 列表
        """
        n = len(dates)
        if n < 2:
            raise ValueError(f"数据长度不足: {n}")

        splits = []

        if self.variable_size:
            # Walk-Forward Analysis（滚动增长）
            # 初始训练集大小
            min_train = self.train_size or max(1, n // (self.n_splits + 1))
            test_sz = self.test_size or (n - min_train) // self.n_splits

            train_end_idx = min_train - 1
            fold = 1

            while train_end_idx < n - 1 and fold <= self.n_splits:
                val_start_idx = train_end_idx + 1 + self.gap
                val_end_idx = min(val_start_idx + test_sz - 1, n - 1)

                if val_start_idx >= n:
                    break

                splits.append(TimeSeriesSplit(
                    train_start=dates[0],
                    train_end=dates[train_end_idx],
                    val_start=dates[val_start_idx],
                    val_end=dates[val_end_idx],
                    fold=fold
                ))

                train_end_idx = val_end_idx
                fold += 1
        else:
            # 固定大小滑动窗口
            test_sz = self.test_size or (n // (self.n_splits + 1))
            min_train = self.train_size or test_sz

            for fold in range(1, self.n_splits + 1):
                train_end_idx = min_train * fold - 1 + self.gap * (fold - 1)
                val_start_idx = train_end_idx + 1 + self.gap
                val_end_idx = val_start_idx + test_sz - 1

                if val_end_idx >= n:
                    val_end_idx = n - 1
                    val_start_idx = max(0, val_end_idx - test_sz + 1)

                if train_end_idx >= val_start_idx or val_end_idx >= n:
                    break

                splits.append(TimeSeriesSplit(
                    train_start=dates[0],
                    train_end=dates[train_end_idx],
                    val_start=dates[val_start_idx],
                    val_end=dates[val_end_idx],
                    fold=fold
                ))

        return splits

    def get_n_splits(self) -> int:
        return self.n_splits


class WalkForwardAnalyzer:
    """
    Walk-Forward 分析器

    在每个时间序列分割上训练、验证模型。
    """

    def __init__(self, validator: TimeSeriesCrossValidator):
        self.validator = validator
        self.results: List[Dict] = []

    def run(
        self,
        dates: List[datetime],
        X: np.ndarray,
        y: np.ndarray,
        train_func: Callable,
        predict_func: Callable,
        metrics_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        运行 Walk-Forward 分析

        Args:
            dates: 日期列表
            X: 特征矩阵 (n_samples, n_features)
            y: 目标变量 (n_samples,)
            train_func: 训练函数，接收 (X_train, y_train)，返回模型
            predict_func: 预测函数，接收 (model, X_test)，返回预测
            metrics_func: 评估函数，接收 (y_true, y_pred)，返回指标字典

        Returns:
            包含所有 fold 结果的字典
        """
        splits = self.validator.split(dates, y)
        self.results = []

        all_metrics = []

        for split in splits:
            # 找到对应的索引
            train_mask = (dates >= split.train_start) & (dates <= split.train_end)
            val_mask = (dates >= split.val_start) & (dates <= split.val_end)

            X_train = X[train_mask]
            y_train = y[train_mask]
            X_val = X[val_mask]
            y_val = y[val_mask]

            if len(X_train) == 0 or len(X_val) == 0:
                logger.warning(f"Fold {split.fold}: 数据为空，跳过")
                continue

            try:
                # 训练模型
                model = train_func(X_train, y_train)

                # 预测
                y_pred = predict_func(model, X_val)

                # 评估
                if metrics_func:
                    metrics = metrics_func(y_val, y_pred)
                else:
                    # 默认评估指标
                    mse = np.mean((y_val - y_pred) ** 2)
                    mae = np.mean(np.abs(y_val - y_pred))
                    metrics = {"mse": mse, "mae": mae}

                self.results.append({
                    "fold": split.fold,
                    "train_start": split.train_start,
                    "train_end": split.train_end,
                    "val_start": split.val_start,
                    "val_end": split.val_end,
                    "train_size": len(X_train),
                    "val_size": len(X_val),
                    "metrics": metrics
                })

                all_metrics.append(metrics)

            except Exception as e:
                logger.error(f"Fold {split.fold} 执行异常: {e}")
                continue

        # 汇总结果
        if not all_metrics:
            return {"error": "所有 fold 都失败了"}

        # 计算平均指标
        avg_metrics = {}
        for key in all_metrics[0].keys():
            values = [m[key] for m in all_metrics if key in m]
            avg_metrics[f"avg_{key}"] = np.mean(values)
            avg_metrics[f"std_{key}"] = np.std(values)

        return {
            "n_folds": len(self.results),
            "folds": self.results,
            "summary": {
                "avg_metrics": avg_metrics,
                "best_fold": max(self.results, key=lambda x: x["metrics"].get("sharpe_ratio", 0))["fold"] if self.results else None
            }
        }


class DataLeakageDetector:
    """
    未来数据泄露检测器

    检测特征和目标变量之间是否存在不合理的时间相关性。
    """

    @staticmethod
    def check_future_correlation(
        X: np.ndarray,
        y: np.ndarray,
        max_lag: int = 5
    ) -> Dict[str, float]:
        """
        检测未来相关性

        正常的特征应该与当前或过去的目标相关，不应该与未来的目标强相关。

        Args:
            X: 特征矩阵
            y: 目标变量
            max_lag: 最大检查的滞后阶数

        Returns:
            各滞后阶数的相关系数
        """
        correlations = {}
        n = len(y)

        for lag in range(1, max_lag + 1):
            if lag >= n:
                break

            # y[t] 与 X[t-lag] 的相关性
            y_current = y[lag:]
            X_lagged = X[:n-lag]

            if len(y_current) < 10:
                continue

            corr = np.corrcoef(y_current.flatten()[:len(X_lagged)], X_lagged[:, 0].flatten()[:len(y_current)])[0, 1]
            correlations[f"lag_{lag}"] = corr

        return correlations

    @staticmethod
    def check_feature_leakage(
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        threshold: float = 0.9
    ) -> List[Dict[str, Any]]:
        """
        检查特征泄露

        如果特征与目标的相关系数异常高，可能是泄露。
        """
        n = len(y)
        results = []

        for i, name in enumerate(feature_names):
            if i >= X.shape[1]:
                break

            corr = np.corrcoef(X[:, i].flatten()[:n], y.flatten()[:n])[0, 1]

            if abs(corr) > threshold:
                results.append({
                    "feature": name,
                    "correlation": corr,
                    "warning": f"特征与目标相关系数异常高 ({corr:.3f})，可能存在数据泄露"
                })

        return results


# ========== 使用示例 ==========

def example_usage():
    """使用示例"""
    import pandas as pd

    # 生成示例数据
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    n = len(dates)

    # 模拟价格数据
    np.random.seed(42)
    y = np.cumsum(np.random.randn(n)) + 100
    X = np.column_stack([
        y[:-1],  # 滞后1天的价格
        np.roll(y, 1)[:-1],  # 滞后2天的价格
        np.random.randn(n) * 0.1,  # 噪声
    ])
    y = y[1:]  # 目标变量
    dates = dates[1:]

    # 时序交叉验证
    validator = TimeSeriesCrossValidator(
        n_splits=5,
        gap=0,
        variable_size=True
    )

    splits = validator.split(list(dates), y)
    print("时序分割:")
    for split in splits:
        print(f"  {split}")

    # Walk-Forward 分析
    analyzer = WalkForwardAnalyzer(validator)

    def train_fn(X_train, y_train):
        # 简化：返回系数
        return np.linalg.lstsq(X_train, y_train, rcond=None)[0]

    def predict_fn(model, X_test):
        return X_test @ model

    def metrics_fn(y_true, y_pred):
        mse = np.mean((y_true - y_pred) ** 2)
        mae = np.mean(np.abs(y_true - y_pred))
        return {"mse": float(mse), "mae": float(mae)}

    result = analyzer.run(list(dates), X, y, train_fn, predict_fn, metrics_fn)

    print("\nWalk-Forward 结果:")
    print(f"  平均 MSE: {result['summary']['avg_metrics']['avg_mse']:.4f}")
    print(f"  平均 MAE: {result['summary']['avg_metrics']['avg_mae']:.4f}")

    # 泄露检测
    leakage_check = DataLeakageDetector.check_future_correlation(X, y, max_lag=3)
    print(f"\n滞后相关性: {leakage_check}")