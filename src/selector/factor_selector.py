"""
多因子选股实现
"""

from typing import List, Optional

from src.data_types import StockScore
from .base import BaseSelector, BaseFactor


class FactorSelector(BaseSelector):
    """多因子选股器

    根据多个因子的加权综合评分选股
    """

    def __init__(
        self,
        factors: List[BaseFactor],
        weights: List[float],
        top_n: Optional[int] = None,
        threshold: Optional[float] = None,
    ):
        """初始化

        Args:
            factors: 因子列表
            weights: 权重列表，和因子一一对应
            top_n: 返回排名前n的股票，None表示不限制
            threshold: 最低评分阈值，None表示不限制
        """
        if len(factors) != len(weights):
            raise ValueError("因子数量和权重数量不匹配")

        self.factors = factors
        self.weights = weights
        self.top_n = top_n
        self.threshold = threshold

    def filter(self, universe: List[str]) -> List[StockScore]:
        results: List[StockScore] = []

        for symbol in universe:
            factor_scores: dict[str, float] = {}
            total_score = 0.0

            for factor, weight in zip(self.factors, self.weights):
                score = factor.calculate(symbol)
                factor_scores[factor.__class__.__name__] = score
                total_score += score * weight

            results.append(
                StockScore(
                    symbol=symbol,
                    score=total_score,
                    factor_scores=factor_scores,
                )
            )

        # 按评分降序排序
        results.sort(key=lambda x: x.score, reverse=True)

        # 应用阈值过滤
        if self.threshold is not None:
            results = [r for r in results if r.score >= self.threshold]

        # 应用top_n限制
        if self.top_n is not None:
            results = results[: self.top_n]

        return results
