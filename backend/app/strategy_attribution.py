"""
策略效果归因分析 — 分解策略收益来源

对回测结果和交易记录进行归因分析，将策略收益分解为：
- 选股 Alpha（个股选择能力贡献）
- 择时收益（买卖时机选择贡献）
- 市场 Beta（市场整体趋势贡献）
- 行业贡献（各行业/板块贡献）
- 风险贡献（风险因子贡献）
"""

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StrategyAttributor:
    """
    策略效果归因分析器

    对回测结果和交易记录进行多维度归因分析，
    帮助理解策略收益的来源和风险特征。
    """

    def __init__(
        self,
        risk_free_rate: float = 0.03,
        benchmark_return: float = 0.10,
    ):
        """
        初始化归因分析器

        Args:
            risk_free_rate: 无风险利率（年化，默认 3%）
            benchmark_return: 基准收益率（年化，默认 10%）
        """
        self.risk_free_rate = risk_free_rate
        self.benchmark_return = benchmark_return

    # ==================== 统计工具方法 ====================

    @staticmethod
    def _mean(values: List[float]) -> float:
        """计算均值"""
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _std(values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)

    @staticmethod
    def _group_by(values: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
        """按指定字段分组"""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in values:
            k = str(item.get(key, "unknown"))
            if k not in groups:
                groups[k] = []
            groups[k].append(item)
        return groups

    # ==================== 归因分析入口 ====================

    def analyze(
        self,
        backtest_result: Dict[str, Any],
        trades: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        归因分析入口 — 对回测结果进行全面归因分析

        Args:
            backtest_result: 回测结果字典，需包含：
                - total_return: 总收益率
                - annual_return: 年化收益率
                - max_drawdown: 最大回撤
                - sharpe_ratio: 夏普比率
                - win_rate: 胜率
                - n_trades: 交易次数
                - initial_capital: 初始资金
                - final_value: 最终资金
            trades: 交易记录列表，每项包含：
                - action: buy/sell
                - code: 股票代码
                - price: 成交价格
                - shares: 成交数量
                - pnl: 盈亏金额（卖出时）
                - pnl_pct: 盈亏比例（卖出时）
                - date: 交易日期

        Returns:
            完整归因分析报告
        """
        logger.info(f"开始归因分析: 共 {len(trades)} 条交易记录")

        # 只分析卖出交易（有盈亏数据）
        sell_trades = [t for t in trades if t.get("action") == "sell" and t.get("pnl") is not None]

        if not sell_trades:
            logger.warning("无卖出交易记录，无法进行归因分析")
            return self._generate_empty_report(backtest_result)

        # 各维度归因
        return_decomposition = self._decompose_returns(sell_trades)
        sector_contribution = self._analyze_sector_contribution(sell_trades)
        timing_analysis = self._analyze_timing(sell_trades)
        risk_contribution = self._analyze_risk_contribution(sell_trades, backtest_result)

        # 组装归因结果
        attribution = {
            "return_decomposition": return_decomposition,
            "sector_contribution": sector_contribution,
            "timing_analysis": timing_analysis,
            "risk_contribution": risk_contribution,
            "backtest_summary": {
                "total_return": backtest_result.get("total_return", 0),
                "annual_return": backtest_result.get("annual_return", 0),
                "max_drawdown": backtest_result.get("max_drawdown", 0),
                "sharpe_ratio": backtest_result.get("sharpe_ratio", 0),
                "win_rate": backtest_result.get("win_rate", 0),
                "n_trades": backtest_result.get("n_trades", len(sell_trades)),
                "total_pnl": sum(t.get("pnl", 0) for t in sell_trades),
            },
        }

        # 生成报告
        report = self._generate_report(attribution)
        return report

    def _generate_empty_report(self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
        """生成空归因报告（无交易数据时）"""
        return {
            "status": "no_data",
            "message": "无有效交易记录，无法进行归因分析",
            "backtest_summary": {
                "total_return": backtest_result.get("total_return", 0),
                "annual_return": backtest_result.get("annual_return", 0),
                "max_drawdown": backtest_result.get("max_drawdown", 0),
                "sharpe_ratio": backtest_result.get("sharpe_ratio", 0),
                "win_rate": backtest_result.get("win_rate", 0),
                "n_trades": backtest_result.get("n_trades", 0),
                "total_pnl": 0,
            },
            "return_decomposition": None,
            "sector_contribution": None,
            "timing_analysis": None,
            "risk_contribution": None,
            "summary": "无有效交易记录，无法进行归因分析。",
        }

    # ==================== 收益分解 ====================

    def _decompose_returns(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        收益分解 — 将策略收益分解为选股 Alpha、择时收益和市场 Beta

        分解方法：
        - 选股 Alpha：个股收益超出市场平均的部分
        - 择时收益：买卖时机带来的额外收益
        - 市场 Beta：跟随市场趋势获得的收益

        Args:
            trades: 卖出交易列表

        Returns:
            收益分解结果
        """
        if not trades:
            return {"alpha": 0, "timing": 0, "beta": 0, "total": 0}

        # 计算每笔交易收益
        pnls = [t.get("pnl", 0) for t in trades]
        pnl_pcts = [t.get("pnl_pct", 0) for t in trades]
        total_pnl = sum(pnls)
        avg_pnl_pct = self._mean(pnl_pcts)

        # 选股 Alpha：收益为正的交易贡献
        winning_pnl = sum(p for p in pnls if p > 0)
        losing_pnl = sum(p for p in pnls if p < 0)
        alpha = winning_pnl + losing_pnl * 0.5  # 亏损交易部分归因于选股

        # 择时收益：基于持仓周期的收益差异
        # 短期交易（假设持仓 < 5 天）更多体现择时能力
        # 这里用收益率的离散度来衡量择时贡献
        std_pnl = self._std(pnl_pcts)
        timing = total_pnl * 0.3 * (std_pnl / (abs(avg_pnl_pct) + 0.01)) if avg_pnl_pct != 0 else 0

        # 市场 Beta：剩余部分归因于市场
        beta = total_pnl - alpha - timing

        # 各部分占比
        total_abs = abs(alpha) + abs(timing) + abs(beta)
        if total_abs > 0:
            alpha_pct = abs(alpha) / total_abs
            timing_pct = abs(timing) / total_abs
            beta_pct = abs(beta) / total_abs
        else:
            alpha_pct = timing_pct = beta_pct = 1 / 3

        result = {
            "alpha": round(alpha, 2),
            "timing": round(timing, 2),
            "beta": round(beta, 2),
            "total": round(total_pnl, 2),
            "alpha_pct": round(alpha_pct, 4),
            "timing_pct": round(timing_pct, 4),
            "beta_pct": round(beta_pct, 4),
            "avg_pnl_pct": round(avg_pnl_pct, 4),
            "pnl_std": round(std_pnl, 4),
            "interpretation": self._interpret_decomposition(alpha, timing, beta, total_pnl),
        }

        logger.info(
            f"收益分解: alpha={alpha:.2f}, timing={timing:.2f}, "
            f"beta={beta:.2f}, total={total_pnl:.2f}"
        )
        return result

    @staticmethod
    def _interpret_decomposition(
        alpha: float,
        timing: float,
        beta: float,
        total: float,
    ) -> str:
        """生成分解结果解读"""
        if total <= 0:
            return "策略整体亏损，需优化选股和择时能力。"

        parts = []
        if alpha > abs(total) * 0.5:
            parts.append("选股能力是主要收益来源")
        elif alpha < 0:
            parts.append("选股能力拖累了整体收益")
        else:
            parts.append("选股能力贡献一般")

        if timing > abs(total) * 0.3:
            parts.append("择时能力提供了额外收益")
        elif timing < 0:
            parts.append("择时判断存在偏差")

        if beta > abs(total) * 0.5:
            parts.append("收益主要来自市场趋势（Beta）")

        return "；".join(parts) + "。"

    # ==================== 行业贡献分析 ====================

    def _analyze_sector_contribution(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        行业贡献分析 — 分析各行业/标的对策略收益的贡献

        由于交易记录中可能没有直接的行业信息，
        这里按股票代码（标的）维度进行分析。

        Args:
            trades: 卖出交易列表

        Returns:
            行业/标的贡献分析结果
        """
        if not trades:
            return {"by_symbol": [], "concentration": 0, "diversification_score": 0}

        # 按股票代码分组
        by_code = self._group_by(trades, "code")

        symbol_contributions: List[Dict[str, Any]] = []
        for code, code_trades in by_code.items():
            total_pnl = sum(t.get("pnl", 0) for t in code_trades)
            avg_pnl_pct = self._mean([t.get("pnl_pct", 0) for t in code_trades])
            n_trades = len(code_trades)
            wins = sum(1 for t in code_trades if t.get("pnl", 0) > 0)
            win_rate = wins / n_trades if n_trades > 0 else 0

            symbol_contributions.append({
                "symbol": code,
                "total_pnl": round(total_pnl, 2),
                "avg_pnl_pct": round(avg_pnl_pct, 4),
                "n_trades": n_trades,
                "win_rate": round(win_rate, 4),
                "wins": wins,
                "losses": n_trades - wins,
            })

        # 按总盈亏排序
        symbol_contributions.sort(key=lambda x: x["total_pnl"], reverse=True)

        # 计算集中度（前 N 标的贡献占比）
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        top_n = min(3, len(symbol_contributions))
        top_pnl = sum(s["total_pnl"] for s in symbol_contributions[:top_n])
        concentration = abs(top_pnl) / abs(total_pnl) if total_pnl != 0 else 0

        # 多样化评分（标的数量和收益均匀度）
        n_symbols = len(symbol_contributions)
        if n_symbols <= 1:
            diversification_score = 0.0
        else:
            # 基于赫芬达尔指数的多样化评分
            pnl_abs = [abs(s["total_pnl"]) for s in symbol_contributions]
            total_abs = sum(pnl_abs)
            if total_abs > 0:
                hhi = sum((p / total_abs) ** 2 for p in pnl_abs)
                diversification_score = round(1 - hhi, 4)
            else:
                diversification_score = 0.5

        result = {
            "by_symbol": symbol_contributions,
            "n_symbols": n_symbols,
            "concentration": round(concentration, 4),
            "diversification_score": round(diversification_score, 4),
            "top_contributors": symbol_contributions[:5],
            "bottom_contributors": symbol_contributions[-3:] if len(symbol_contributions) > 3 else [],
            "interpretation": self._interpret_sector(concentration, diversification_score, n_symbols),
        }

        logger.info(
            f"行业贡献分析: {n_symbols} 个标的, "
            f"集中度={concentration:.2f}, 多样化={diversification_score:.2f}"
        )
        return result

    @staticmethod
    def _interpret_sector(
        concentration: float,
        diversification: float,
        n_symbols: int,
    ) -> str:
        """生成行业贡献解读"""
        parts = [f"策略涉及 {n_symbols} 个标的。"]

        if concentration > 0.7:
            parts.append("收益高度集中于少数标的，集中度风险较高。")
        elif concentration > 0.5:
            parts.append("收益相对集中，建议适当分散。")
        else:
            parts.append("收益分布较为均匀，分散化程度良好。")

        if diversification > 0.7:
            parts.append("组合多样化程度较高。")
        elif diversification < 0.3:
            parts.append("组合多样化程度较低，过度依赖个别标的。")

        return "".join(parts)

    # ==================== 择时能力分析 ====================

    def _analyze_timing(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        择时能力分析 — 评估策略的买卖时机选择能力

        分析维度：
        - 盈利交易与亏损交易的特征差异
        - 连续盈利/亏损序列
        - 平均持仓周期（如果有日期信息）

        Args:
            trades: 卖出交易列表

        Returns:
            择时能力分析结果
        """
        if not trades:
            return {
                "timing_score": 0,
                "win_streak_max": 0,
                "loss_streak_max": 0,
                "avg_win_pnl": 0,
                "avg_loss_pnl": 0,
                "profit_factor": 0,
            }

        pnls = [t.get("pnl", 0) for t in trades]
        pnl_pcts = [t.get("pnl_pct", 0) for t in trades]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        avg_win = self._mean(wins) if wins else 0
        avg_loss = self._mean(losses) if losses else 0

        # 盈亏比
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

        # 最大连胜/连亏
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0

        for pnl in pnls:
            if pnl > 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)

        # 择时评分（综合胜率、盈亏比、连胜等）
        win_rate = len(wins) / len(pnls) if pnls else 0
        timing_score = self._calculate_timing_score(
            win_rate=win_rate,
            profit_factor=min(profit_factor, 5.0),  # 上限 5.0
            max_win_streak=max_win_streak,
            max_loss_streak=max_loss_streak,
        )

        result = {
            "timing_score": round(timing_score, 4),
            "win_streak_max": max_win_streak,
            "loss_streak_max": max_loss_streak,
            "avg_win_pnl": round(avg_win, 2),
            "avg_loss_pnl": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else 999.0,
            "win_rate": round(win_rate, 4),
            "n_wins": len(wins),
            "n_losses": len(losses),
            "pnl_distribution": {
                "max_win": round(max(pnls), 2) if pnls else 0,
                "max_loss": round(min(pnls), 2) if pnls else 0,
                "median_pnl": round(sorted(pnls)[len(pnls) // 2], 2) if pnls else 0,
                "pnl_std": round(self._std(pnls), 2),
            },
            "interpretation": self._interpret_timing(timing_score, win_rate, profit_factor),
        }

        logger.info(
            f"择时分析: score={timing_score:.2f}, "
            f"胜率={win_rate:.2f}, 盈亏比={profit_factor:.2f}"
        )
        return result

    @staticmethod
    def _calculate_timing_score(
        win_rate: float,
        profit_factor: float,
        max_win_streak: int,
        max_loss_streak: int,
    ) -> float:
        """
        计算择时综合评分（0-100）

        综合考虑胜率、盈亏比、连胜连亏等因素。
        """
        # 胜率评分（权重 40%）
        win_rate_score = min(win_rate / 0.6, 1.0) * 40  # 60% 胜率得满分

        # 盈亏比评分（权重 30%）
        pf_score = min(profit_factor / 2.5, 1.0) * 30  # 盈亏比 2.5 得满分

        # 连胜评分（权重 15%）
        streak_score = min(max_win_streak / 5, 1.0) * 15  # 5 连胜得满分

        # 连亏惩罚（权重 15%）
        loss_penalty = min(max_loss_streak / 5, 1.0) * 15

        score = win_rate_score + pf_score + streak_score - loss_penalty
        return max(0, min(100, score))

    @staticmethod
    def _interpret_timing(
        timing_score: float,
        win_rate: float,
        profit_factor: float,
    ) -> str:
        """生成择时能力解读"""
        if timing_score >= 70:
            level = "优秀"
        elif timing_score >= 50:
            level = "良好"
        elif timing_score >= 30:
            level = "一般"
        else:
            level = "较弱"

        parts = [f"择时能力评级：{level}（评分 {timing_score:.1f}/100）。"]
        parts.append(f"胜率 {win_rate:.1%}，盈亏比 {profit_factor:.2f}。")

        if win_rate < 0.4:
            parts.append("胜率偏低，建议优化入场条件。")
        if profit_factor < 1.0:
            parts.append("盈亏比不足 1，需改善止盈止损策略。")

        return "".join(parts)

    # ==================== 风险贡献分析 ====================

    def _analyze_risk_contribution(
        self,
        trades: List[Dict[str, Any]],
        backtest_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        风险贡献分析 — 分析策略的风险特征

        分析维度：
        - 最大回撤分析
        - 收益波动率
        - 下行风险
        - 风险调整后收益

        Args:
            trades: 卖出交易列表
            backtest_result: 回测结果

        Returns:
            风险贡献分析结果
        """
        if not trades:
            return {
                "max_drawdown": 0,
                "volatility": 0,
                "downside_risk": 0,
                "sortino_ratio": 0,
                "calmar_ratio": 0,
                "risk_level": "unknown",
            }

        pnl_pcts = [t.get("pnl_pct", 0) for t in trades]
        pnls = [t.get("pnl", 0) for t in trades]

        # 波动率（收益率标准差）
        volatility = self._std(pnl_pcts)

        # 下行风险（仅计算负收益的标准差）
        negative_returns = [r for r in pnl_pcts if r < 0]
        downside_risk = self._std(negative_returns) if negative_returns else 0

        # 最大回撤（基于累计盈亏）
        cumulative = 0
        cummax = 0
        max_dd = 0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > cummax:
                cummax = cumulative
            dd = (cumulative - cummax) / cummax if cummax > 0 else 0
            if dd < max_dd:
                max_dd = dd

        # 年化收益率
        annual_return = backtest_result.get("annual_return", 0)

        # Sortino 比率（使用下行风险）
        daily_rf = self.risk_free_rate / 252
        excess_return = annual_return - self.risk_free_rate
        sortino = excess_return / downside_risk if downside_risk > 0 else 0

        # Calmar 比率（年化收益 / 最大回撤）
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

        # 风险等级评定
        if volatility > 0.05:
            risk_level = "high"
        elif volatility > 0.03:
            risk_level = "medium"
        else:
            risk_level = "low"

        result = {
            "max_drawdown": round(max_dd, 4),
            "volatility": round(volatility, 4),
            "downside_risk": round(downside_risk, 4),
            "sortino_ratio": round(sortino, 4),
            "calmar_ratio": round(calmar, 4),
            "risk_level": risk_level,
            "annual_return": round(annual_return, 4),
            "risk_free_rate": self.risk_free_rate,
            "interpretation": self._interpret_risk(
                volatility, max_dd, sortino, calmar, risk_level
            ),
        }

        logger.info(
            f"风险分析: volatility={volatility:.4f}, "
            f"max_dd={max_dd:.4f}, sortino={sortino:.4f}, "
            f"risk_level={risk_level}"
        )
        return result

    @staticmethod
    def _interpret_risk(
        volatility: float,
        max_dd: float,
        sortino: float,
        calmar: float,
        risk_level: str,
    ) -> str:
        """生成风险分析解读"""
        risk_names = {"low": "低", "medium": "中", "high": "高"}
        parts = [f"策略风险等级：{risk_names.get(risk_level, risk_level)}。"]
        parts.append(f"收益波动率 {volatility:.2%}，最大回撤 {max_dd:.2%}。")

        if sortino > 2.0:
            parts.append("Sortino 比率优秀，下行风险控制良好。")
        elif sortino < 0.5:
            parts.append("Sortino 比率偏低，下行风险较大。")

        if calmar > 2.0:
            parts.append("Calmar 比率优秀，回撤控制出色。")
        elif calmar < 0.5:
            parts.append("Calmar 比率偏低，回撤幅度偏大。")

        return "".join(parts)

    # ==================== 归因报告生成 ====================

    def _generate_report(self, attribution: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成归因分析综合报告

        Args:
            attribution: 各维度归因结果

        Returns:
            综合归因报告
        """
        summary = backtest = attribution.get("backtest_summary", {})
        decomposition = attribution.get("return_decomposition", {})
        sector = attribution.get("sector_contribution", {})
        timing = attribution.get("timing_analysis", {})
        risk = attribution.get("risk_contribution", {})

        # 综合评价
        total_return = backtest.get("total_return", 0)
        sharpe = backtest.get("sharpe_ratio", 0)
        win_rate = backtest.get("win_rate", 0)

        if total_return > 0.1 and sharpe > 1.5 and win_rate > 0.5:
            overall_rating = "excellent"
        elif total_return > 0 and sharpe > 0.8:
            overall_rating = "good"
        elif total_return > -0.05:
            overall_rating = "average"
        else:
            overall_rating = "poor"

        rating_names = {
            "excellent": "优秀",
            "good": "良好",
            "average": "一般",
            "poor": "较差",
        }

        # 生成摘要
        summary_parts = [
            f"策略综合评级：{rating_names.get(overall_rating, overall_rating)}。"
        ]
        summary_parts.append(
            f"总收益率 {total_return:.2%}，夏普比率 {sharpe:.2f}，胜率 {win_rate:.2%}。"
        )

        if decomposition:
            alpha = decomposition.get("alpha", 0)
            timing_pnl = decomposition.get("timing", 0)
            beta = decomposition.get("beta", 0)
            summary_parts.append(
                f"收益分解：选股 Alpha={alpha:.2f}，"
                f"择时={timing_pnl:.2f}，市场 Beta={beta:.2f}。"
            )

        if risk:
            risk_level = risk.get("risk_level", "unknown")
            summary_parts.append(f"风险等级：{risk_level}。")

        report = {
            "overall_rating": overall_rating,
            "overall_rating_text": rating_names.get(overall_rating, overall_rating),
            "summary": "".join(summary_parts),
            "backtest_summary": backtest,
            "return_decomposition": decomposition,
            "sector_contribution": sector,
            "timing_analysis": timing,
            "risk_contribution": risk,
            "recommendations": self._generate_recommendations(
                decomposition, sector, timing, risk
            ),
        }

        logger.info(f"归因报告生成完成: 评级={overall_rating}")
        return report

    @staticmethod
    def _generate_recommendations(
        decomposition: Optional[Dict[str, Any]],
        sector: Optional[Dict[str, Any]],
        timing: Optional[Dict[str, Any]],
        risk: Optional[Dict[str, Any]],
    ) -> List[str]:
        """生成改进建议"""
        recommendations: List[str] = []

        if decomposition:
            alpha = decomposition.get("alpha", 0)
            if alpha < 0:
                recommendations.append("选股能力不足，建议优化选股因子和筛选条件。")

            timing_pnl = decomposition.get("timing", 0)
            if timing_pnl < 0:
                recommendations.append("择时判断存在偏差，建议优化入场/出场时机。")

        if sector:
            concentration = sector.get("concentration", 0)
            if concentration > 0.7:
                recommendations.append("收益过于集中，建议增加持仓标的数量以分散风险。")

            diversification = sector.get("diversification_score", 0)
            if diversification < 0.3:
                recommendations.append("组合多样化不足，建议覆盖更多行业/板块。")

        if timing:
            timing_score = timing.get("timing_score", 0)
            if timing_score < 30:
                recommendations.append("择时能力较弱，建议增加技术指标辅助判断。")

            profit_factor = timing.get("profit_factor", 0)
            if profit_factor < 1.0:
                recommendations.append("盈亏比不足，建议优化止盈止损比例。")

        if risk:
            risk_level = risk.get("risk_level", "")
            if risk_level == "high":
                recommendations.append("策略风险偏高，建议降低仓位或增加止损机制。")

            sortino = risk.get("sortino_ratio", 0)
            if sortino < 0.5:
                recommendations.append("下行风险控制不足，建议加强回撤管理。")

        if not recommendations:
            recommendations.append("策略整体表现均衡，建议持续监控各项指标。")

        return recommendations
