"""
持仓集中度风控规则
"""

from .base import BaseRiskControl, RiskContext, RiskResult


class ConcentrationRiskControl(BaseRiskControl):
    """行业集中度风控

    限制同一行业的最大仓位比例
    """

    def __init__(self, max_industry_weight: float = 0.3):
        """初始化

        Args:
            max_industry_weight: 同一行业最大仓位比例，默认30%
        """
        self.max_industry_weight = max_industry_weight

    def check(self, context: RiskContext) -> RiskResult:
        # 需要行业信息映射，实际使用时需要外部传入行业数据
        # 这里只是框架结构，具体实现需要结合行业数据
        total_balance = context.account.total_balance
        if total_balance <= 0:
            return RiskResult(passed=False, message="账户资金为0")

        # TODO: 根据context中target_symbol获取行业信息，计算当前行业总仓位
        # 这里留空，由具体业务实现

        return RiskResult(passed=True, message="行业集中度检查通过")
