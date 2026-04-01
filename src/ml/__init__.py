"""
机器学习模块

注意：ML 功能已迁移到 src/ml_strategy/ 模块。
此文件保留向后兼容的导入。
"""
from src.ml_strategy.ml_strategy import MLStockPicker, Backtester
from src.ml_strategy.factor_extractor import FactorExtractor
from src.ml_strategy.label_constructor import LabelConstructor
from src.ml_strategy.trainer import RollingTrainer, OptunaOptimizer
from src.ml_strategy.shap_analyzer import SHAPAnalyzer

__all__ = [
    'MLStockPicker',
    'Backtester',
    'FactorExtractor',
    'LabelConstructor',
    'RollingTrainer',
    'OptunaOptimizer',
    'SHAPAnalyzer',
]
