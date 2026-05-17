"""
仓位风控规则
"""

from .base import BaseRiskControl, RiskContext, RiskResult


class PositionRiskControl(BaseRiskControl):
    """单票仓位限制风控

    限制单个标的占总仓位的最大比例
"""

    def __init__(self, max_weight: float = 0.1):
        """初始化

        Args:
            max_weight: 最大仓位比例，默认10%
        """
        self.max_weight = max_weight

    def check(self, context: RiskContext) -> RiskResult:
        if context.side == "sell":
            # 卖出不受限制
            return RiskResult(passed=True, message="卖出操作，直接通过")

        total_value = context.price * context.target_volume
        total_balance = context.account.total_balance

        # 当前目标占总资金的比例
        if total_balance <= 0:
            return RiskResult(passed=False, message="账户资金为0")

        weight = total_value / total_balance

        if weight > self.max_weight:
            # 需要调整到max_weight
            adjusted = total_balance * self.max_weight / context.price
            adjusted_volume = int(adjusted)
            return RiskResult(
                passed=False,
                message=f"目标仓位 {weight*100:.2f}% 超过限制 {self.max_weight*100:.2f}%",
                adjusted_volume=adjusted,
            )

        return RiskResult(passed=True, message=f"仓位在限制范围内")
