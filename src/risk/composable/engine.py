"""
风控引擎 - 组合多个风控规则执行检查
"""

from typing import List

from .base import BaseRiskControl, RiskContext, RiskResult


class RiskEngine:
    """风控引擎

    按顺序执行所有风控规则，任意规则不通过则整体不通过
    """

    def __init__(self, rules: List[BaseRiskControl]):
        """初始化

        Args:
            rules: 风控规则列表，按顺序执行
        """
        self.rules = rules

    def run_checks(self, context: RiskContext) -> RiskResult:
        """执行所有风控检查

        Args:
            context: 风控上下文

        Returns:
            最终风控结果
        """
        adjusted_volume = None

        for rule in self.rules:
            result = rule.check(context)

            if result.adjusted_volume > 0:
                # 记录调整后的成交量
                adjusted_volume = result.adjusted_volume
                context.target_volume = adjusted_volume

            if not result.passed:
                # 返回第一个不通过的结果
                return RiskResult(
                    passed=False,
                    message=result.message,
                    adjusted_volume=adjusted_volume or 0,
                )

        # 所有规则都通过
        return RiskResult(
            passed=True,
            message="所有风控检查通过",
            adjusted_volume=adjusted_volume if adjusted_volume is not None else 0,
        )
