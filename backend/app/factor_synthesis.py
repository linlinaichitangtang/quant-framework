"""
深度因子合成

使用深度学习自动合成新因子。
基于因子间的非线性组合发现隐藏模式。
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FactorSynthConfig:
    """因子合成配置"""
    input_factors: List[str]
    hidden_dims: List[int] = None  # [64, 32, 16]
    output_dim: int = 1
    activation: str = "relu"
    dropout: float = 0.1
    learning_rate: float = 0.001
    n_epochs: int = 100
    batch_size: int = 32
    validation_split: float = 0.2


class FactorSynthesizer:
    """
    深度因子合成器

    使用神经网络学习因子间的非线性组合。
    """

    def __init__(self, config: FactorSynthConfig):
        self.config = config
        self._model = None
        self._scaler = None
        self._feature_importance = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        训练因子合成模型

        Args:
            X: 因子矩阵 (n_samples, n_factors)
            y: 目标变量 (n_samples,)
            feature_names: 因子名称列表

        Returns:
            训练结果字典
        """
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            logger.warning("PyTorch 未安装，使用简化实现")
            return self._fit_simple(X, y, feature_names)

        n_samples, n_features = X.shape
        feature_names = feature_names or [f"factor_{i}" for i in range(n_features)]

        # 数据标准化
        X_mean = X.mean(axis=0)
        X_std = X.std(axis=0) + 1e-8
        X_norm = (X - X_mean) / X_std
        y_mean = y.mean()
        y_std = y.std() + 1e-8
        y_norm = (y - y_mean) / y_std

        self._scaler = {"X_mean": X_mean, "X_std": X_std, "y_mean": y_mean, "y_std": y_std}

        # 构建神经网络
        hidden_dims = self.config.hidden_dims or [64, 32, 16]
        layers = []
        in_dim = n_features

        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(in_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(self.config.dropout))
            in_dim = hidden_dim

        layers.append(nn.Linear(in_dim, self.config.output_dim))

        self._model = nn.Sequential(*layers)

        # 训练
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self._model.parameters(), lr=self.config.learning_rate)

        # 数据加载器
        dataset = TensorDataset(
            torch.FloatTensor(X_norm),
            torch.FloatTensor(y_norm.reshape(-1, 1))
        )
        dataloader = DataLoader(dataset, batch_size=self.config.batch_size, shuffle=True)

        losses = []
        for epoch in range(self.config.n_epochs):
            epoch_loss = 0
            for batch_X, batch_y in dataloader:
                optimizer.zero_grad()
                output = self._model(batch_X)
                loss = criterion(output, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(dataloader)
            losses.append(avg_loss)

            if (epoch + 1) % 20 == 0:
                logger.info(f"Epoch {epoch+1}/{self.config.n_epochs}, Loss: {avg_loss:.6f}")

        # 计算特征重要性（基于梯度）
        self._compute_feature_importance(X_norm, y_norm, feature_names)

        # 最终评估
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_norm)
            y_pred = self._model(X_tensor).numpy().flatten()
            y_pred = y_pred * y_std + y_mean

        mse = np.mean((y - y_pred) ** 2)
        ic = np.corrcoef(X_norm.mean(axis=1), y_norm)[0, 1]

        return {
            "n_samples": n_samples,
            "n_features": n_features,
            "feature_names": feature_names,
            "final_loss": losses[-1],
            "mse": float(mse),
            "ic": float(ic) if not np.isnan(ic) else 0,
            "feature_importance": self._feature_importance,
            "training_complete": True
        }

    def _fit_simple(self, X: np.ndarray, y: np.ndarray, feature_names: List[str]) -> Dict:
        """简化实现（无 PyTorch 时）"""
        n_samples, n_features = X.shape
        feature_names = feature_names or [f"factor_{i}" for i in range(n_features)]

        # 使用线性回归作为替代
        from sklearn.linear_model import Ridge
        model = Ridge(alpha=1.0)
        model.fit(X, y)

        y_pred = model.predict(X)
        mse = np.mean((y - y_pred) ** 2)

        # 特征重要性 = 系数绝对值
        importance = np.abs(model.coef_)
        self._feature_importance = {
            name: float(imp) for name, imp in zip(feature_names, importance)
        }

        return {
            "n_samples": n_samples,
            "n_features": n_features,
            "feature_names": feature_names,
            "final_loss": mse,
            "mse": float(mse),
            "ic": 0,
            "feature_importance": self._feature_importance,
            "training_complete": True,
            "note": "使用 Ridge 回归（PyTorch 未安装）"
        }

    def _compute_feature_importance(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str]
    ):
        """计算特征重要性"""
        try:
            import torch
        except ImportError:
            return

        # 使用梯度的绝对值均值
        X_tensor = torch.FloatTensor(X, requires_grad=True)
        X_tensor.retain_grad()

        output = self._model(X_tensor)
        output.sum().backward()

        gradients = X_tensor.grad.abs().mean(dim=0).numpy()
        self._feature_importance = {
            name: float(g) for name, g in zip(feature_names, gradients)
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        使用合成因子进行预测

        Args:
            X: 因子矩阵 (n_samples, n_factors)

        Returns:
            合成因子值 (n_samples,)
        """
        if self._scaler is None:
            raise RuntimeError("模型未训练，请先调用 fit()")

        X_norm = (X - self._scaler["X_mean"]) / self._scaler["X_std"]

        try:
            import torch
            with torch.no_grad():
                X_tensor = torch.FloatTensor(X_norm)
                output = self._model(X_tensor).numpy().flatten()
                return output * self._scaler["y_std"] + self._scaler["y_mean"]
        except ImportError:
            # 简化实现
            return X.mean(axis=1)

    def get_synthetic_factors(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        获取合成因子

        返回多个合成分量，用于因子分析。
        """
        if self._scaler is None:
            raise RuntimeError("模型未训练")

        X_norm = (X - self._scaler["X_mean"]) / self._scaler["X_std"]

        try:
            import torch
            with torch.no_grad():
                X_tensor = torch.FloatTensor(X_norm)

                # 获取中间层输出
                synthetic = {}
                x = X_tensor
                for i, layer in enumerate(self._model[:-1]):
                    x = layer(x)
                    if isinstance(layer, torch.nn.ReLU):
                        synthetic[f"synthetic_layer_{i}"] = x.numpy().mean(axis=1)

                # 最终输出
                synthetic["final"] = self._model(X_tensor).numpy().flatten()

                return synthetic
        except ImportError:
            return {"mean": X.mean(axis=1)}


class FactorCrossingAnalyzer:
    """
    特征交叉分析器

    分析因子间的交互作用，发现非线性组合。
    """

    @staticmethod
    def compute_interaction_matrix(
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str]
    ) -> np.ndarray:
        """
        计算因子交互矩阵

        检测每对因子之间的交互作用强度。
        """
        n_features = X.shape[1]
        interaction_matrix = np.zeros((n_features, n_features))

        for i in range(n_features):
            for j in range(i, n_features):
                if i == j:
                    # 自身相关性
                    interaction_matrix[i, j] = np.corrcoef(X[:, i], y)[0, 1]
                else:
                    # 乘积相关性
                    interaction = X[:, i] * X[:, j]
                    corr = np.corrcoef(interaction, y)[0, 1]
                    if not np.isnan(corr):
                        interaction_matrix[i, j] = corr
                        interaction_matrix[j, i] = corr

        return interaction_matrix

    @staticmethod
    def find_synergy_pairs(
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        找出协同因子对

        协同对是指单独使用效果一般，但组合效果显著的因子对。
        """
        n_features = X.shape[1]
        synergy_pairs = []

        for i in range(n_features):
            for j in range(i + 1, n_features):
                # 单独 IC
                ic_i = np.corrcoef(X[:, i], y)[0, 1]
                ic_j = np.corrcoef(X[:, j], y)[0, 1]

                # 组合 IC
                interaction = X[:, i] * X[:, j]
                ic_combined = np.corrcoef(interaction, y)[0, 1]

                if np.isnan(ic_combined):
                    continue

                # 协同效应 = 组合IC - max(单独IC)
                synergy = ic_combined - max(abs(ic_i), abs(ic_j))

                if synergy > threshold:
                    synergy_pairs.append({
                        "factor1": feature_names[i],
                        "factor2": feature_names[j],
                        "ic1": float(ic_i) if not np.isnan(ic_i) else 0,
                        "ic2": float(ic_j) if not np.isnan(ic_j) else 0,
                        "ic_combined": float(ic_combined),
                        "synergy": float(synergy),
                        "interpretation": "组合效果优于单独使用"
                    })

        # 按协同效应排序
        synergy_pairs.sort(key=lambda x: x["synergy"], reverse=True)
        return synergy_pairs


# ========== 使用示例 ==========

def example():
    """使用示例"""
    # 模拟因子数据
    np.random.seed(42)
    n_samples = 1000
    n_factors = 5

    # 生成相关因子
    factor1 = np.random.randn(n_samples)
    factor2 = np.random.randn(n_samples) * 0.5 + factor1 * 0.5
    factor3 = np.random.randn(n_samples)
    factor4 = np.random.randn(n_samples) * 0.3 + factor2 * 0.4
    factor5 = np.random.randn(n_samples)

    X = np.column_stack([factor1, factor2, factor3, factor4, factor5])
    feature_names = ["factor1", "factor2", "factor3", "factor4", "factor5"]

    # 生成目标（与 factor1, factor2, 及它们的交互相关）
    y = factor1 * 0.3 + factor2 * 0.2 + factor1 * factor2 * 0.5 + np.random.randn(n_samples) * 0.1

    # 因子合成
    config = FactorSynthConfig(
        input_factors=feature_names,
        hidden_dims=[32, 16],
        n_epochs=50,
        learning_rate=0.01
    )

    synthesizer = FactorSynthesizer(config)
    result = synthesizer.fit(X, y, feature_names)

    print("因子合成结果:")
    print(f"  MSE: {result['mse']:.4f}")
    print(f"  IC: {result['ic']:.4f}")
    print("\n特征重要性:")
    for name, imp in result["feature_importance"].items():
        print(f"  {name}: {imp:.4f}")

    # 特征交叉分析
    analyzer = FactorCrossingAnalyzer()
    interaction_matrix = analyzer.compute_interaction_matrix(X, y, feature_names)
    print("\n交互矩阵:")
    print(np.round(interaction_matrix, 3))

    # 协同因子对
    synergy_pairs = analyzer.find_synergy_pairs(X, y, feature_names, threshold=0.05)
    print("\n协同因子对:")
    for pair in synergy_pairs[:3]:
        print(f"  {pair['factor1']} x {pair['factor2']}: synergy={pair['synergy']:.4f}")