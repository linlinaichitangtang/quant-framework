"""
回撤风控规则
"""

from .base import BaseRiskControl, RiskContext, RiskResult


class DrawDownRiskControl(BaseRiskControl):
    """最大回撤风控

    当日亏损达到一定比例后，停止当日交易
    """

    def __init__(self, max_daily_drawdown: float = 0.03):
        """初始化

        Args:
            max_daily_drawdown: 最大允许单日回撤，默认3%
        """
        self.max_daily_drawdown = max_daily_drawdown

    def check(self, context: RiskContext) -> RiskResult:
        # 计算当前总盈亏
        if context.account.total_balance <= 0:
            return RiskResult(passed=False, message="账户资金为0")

        # 总盈亏 = 总市值 + 可用资金 - 初始资金
        # 这里需要从上下文获取初始资金，简化版本只检查当前市值变动
        current_profit_pct = 0  # 需要外部计算传入

        # TODO: 需要在context补充初始资金和当日盈亏
        # 暂时总是通过，后续完善

        if current_profit_pct <= -self.max_daily_drawdown:
            return RiskResult(
                passed=False,
                message=f"当日回撤 {current_profit_pct*100:.2f}%，超过限制 {self.max_daily_drawdown*100:.2f}%，停止交易",
            )

        return RiskResult(passed=True, message="回撤在允许范围内")
