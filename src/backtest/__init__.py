"""
回测模块

注意：回测功能已在 src/ml_strategy/ml_strategy.py 的 Backtester 类中实现。
此文件保留向后兼容的导入。
"""
from src.ml_strategy.ml_strategy import Backtester

__all__ = ['Backtester']
