"""
异常交易检测引擎 — 基于统计方法的异常交易检测

纯算法模块，不依赖 LLM。提供以下检测能力：
- 价格异常检测（Z-score + IQR 双重验证）
- 成交量异常检测
- 相关性断裂检测
- 拉高出货（Pump & Dump）检测
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    异常交易检测引擎

    基于统计学方法（Z-score、IQR、相关性分析等）检测市场异常行为。
    所有方法均为纯计算，无外部依赖。
    """

    def __init__(
        self,
        z_score_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
        volume_z_threshold: float = 3.0,
        correlation_window: int = 20,
        correlation_breakdown_threshold: float = 0.5,
    ):
        """
        初始化异常检测器

        Args:
            z_score_threshold: Z-score 异常阈值（默认 3.0，即 3 倍标准差）
            iqr_multiplier: IQR 倍数阈值（默认 1.5）
            volume_z_threshold: 成交量 Z-score 阈值
            correlation_window: 相关性计算窗口（天数）
            correlation_breakdown_threshold: 相关性断裂阈值（相关系数下降幅度）
        """
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier
        self.volume_z_threshold = volume_z_threshold
        self.correlation_window = correlation_window
        self.correlation_breakdown_threshold = correlation_breakdown_threshold

    # ==================== 统计工具方法 ====================

    @staticmethod
    def _mean(values: List[float]) -> float:
        """计算均值"""
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _std(values: List[float]) -> float:
        """计算标准差（总体标准差）"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)

    @staticmethod
    def _percentile(values: List[float], p: float) -> float:
        """计算百分位数（线性插值法）"""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

    @staticmethod
    def _pearson_correlation(x: List[float], y: List[float]) -> float:
        """计算皮尔逊相关系数"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        if denom_x == 0 or denom_y == 0:
            return 0.0
        return numerator / (denom_x * denom_y)

    @staticmethod
    def _calculate_returns(prices: List[float]) -> List[float]:
        """计算价格收益率序列"""
        if len(prices) < 2:
            return []
        return [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

    # ==================== 价格异常检测 ====================

    def detect_price_anomaly(self, prices: List[float]) -> List[Dict[str, Any]]:
        """
        价格异常检测 — Z-score + IQR 双重验证

        当 Z-score 和 IQR 同时判定为异常时，才标记为高置信度异常。

        Args:
            prices: 价格序列（按时间顺序）

        Returns:
            异常列表，每项包含：
            - index: 异常位置索引
            - price: 异常价格
            - z_score: Z-score 值
            - iqr_status: IQR 判定结果
            - severity: 严重程度（low / medium / high）
            - type: 异常类型（spike_up / spike_down）
        """
        if len(prices) < 10:
            logger.warning("价格序列长度不足 10，无法进行异常检测")
            return []

        # 计算收益率
        returns = self._calculate_returns(prices)
        if not returns:
            return []

        anomalies: List[Dict[str, Any]] = []
        mean_ret = self._mean(returns)
        std_ret = self._std(returns)

        # IQR 计算
        q1 = self._percentile(returns, 0.25)
        q3 = self._percentile(returns, 0.75)
        iqr = q3 - q1
        iqr_lower = q1 - self.iqr_multiplier * iqr
        iqr_upper = q3 + self.iqr_multiplier * iqr

        for i, ret in enumerate(returns):
            price_idx = i + 1  # 收益率索引对应的价格索引偏移 1
            z_score = (ret - mean_ret) / std_ret if std_ret > 0 else 0

            # Z-score 判定
            z_anomaly = abs(z_score) >= self.z_score_threshold
            # IQR 判定
            iqr_anomaly = ret < iqr_lower or ret > iqr_upper

            if z_anomaly or iqr_anomaly:
                # 判断方向
                anomaly_type = "spike_up" if ret > 0 else "spike_down"

                # 严重程度判定
                if z_anomaly and iqr_anomaly:
                    severity = "high"
                elif abs(z_score) >= self.z_score_threshold * 1.5:
                    severity = "high"
                elif z_anomaly or iqr_anomaly:
                    severity = "medium"
                else:
                    severity = "low"

                anomalies.append({
                    "index": price_idx,
                    "price": prices[price_idx],
                    "return": round(ret, 6),
                    "z_score": round(z_score, 4),
                    "iqr_lower": round(iqr_lower, 6),
                    "iqr_upper": round(iqr_upper, 6),
                    "iqr_status": "outlier" if iqr_anomaly else "normal",
                    "severity": severity,
                    "type": anomaly_type,
                })

        logger.info(f"价格异常检测完成: 共 {len(anomalies)} 个异常点")
        return anomalies

    # ==================== 成交量异常检测 ====================

    def detect_volume_anomaly(self, volumes: List[float]) -> List[Dict[str, Any]]:
        """
        成交量异常检测 — 基于 Z-score 和移动平均

        Args:
            volumes: 成交量序列（按时间顺序）

        Returns:
            异常列表，每项包含：
            - index: 异常位置索引
            - volume: 异常成交量
            - z_score: Z-score 值
            - ratio_vs_avg: 相对均值的倍数
            - severity: 严重程度
            - type: 异常类型（volume_spike / volume_drop）
        """
        if len(volumes) < 10:
            logger.warning("成交量序列长度不足 10，无法进行异常检测")
            return []

        anomalies: List[Dict[str, Any]] = []
        mean_vol = self._mean(volumes)
        std_vol = self._std(volumes)

        for i, vol in enumerate(volumes):
            z_score = (vol - mean_vol) / std_vol if std_vol > 0 else 0
            ratio = vol / mean_vol if mean_vol > 0 else 0

            if abs(z_score) >= self.volume_z_threshold:
                anomaly_type = "volume_spike" if z_score > 0 else "volume_drop"

                # 严重程度
                if abs(z_score) >= self.volume_z_threshold * 2:
                    severity = "high"
                elif abs(z_score) >= self.volume_z_threshold * 1.5:
                    severity = "medium"
                else:
                    severity = "low"

                anomalies.append({
                    "index": i,
                    "volume": vol,
                    "z_score": round(z_score, 4),
                    "ratio_vs_avg": round(ratio, 2),
                    "mean_volume": round(mean_vol, 2),
                    "severity": severity,
                    "type": anomaly_type,
                })

        logger.info(f"成交量异常检测完成: 共 {len(anomalies)} 个异常点")
        return anomalies

    # ==================== 相关性断裂检测 ====================

    def detect_correlation_breakdown(
        self,
        symbols_data: Dict[str, List[float]],
    ) -> List[Dict[str, Any]]:
        """
        相关性断裂检测 — 检测多个标的之间的相关性异常变化

        通过滑动窗口计算相关系数，当相关系数出现显著下降时标记为断裂。

        Args:
            symbols_data: 标的价格数据字典，格式为 {"symbol": [price1, price2, ...]}

        Returns:
            异常列表，每项包含：
            - symbol_pair: 标的对
            - window_start: 窗口起始位置
            - correlation_before: 断裂前相关系数
            - correlation_after: 断裂后相关系数
            - correlation_drop: 相关系数下降幅度
            - severity: 严重程度
        """
        if len(symbols_data) < 2:
            logger.warning("标的数量不足 2，无法进行相关性检测")
            return []

        symbols = list(symbols_data.keys())
        anomalies: List[Dict[str, Any]] = []

        # 两两配对检测
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym_a = symbols[i]
                sym_b = symbols[j]
                prices_a = symbols_data[sym_a]
                prices_b = symbols_data[sym_b]

                min_len = min(len(prices_a), len(prices_b))
                if min_len < self.correlation_window * 2:
                    continue

                prices_a = prices_a[:min_len]
                prices_b = prices_b[:min_len]

                # 转换为收益率
                returns_a = self._calculate_returns(prices_a)
                returns_b = self._calculate_returns(prices_b)
                min_ret_len = min(len(returns_a), len(returns_b))
                returns_a = returns_a[:min_ret_len]
                returns_b = returns_b[:min_ret_len]

                if min_ret_len < self.correlation_window * 2:
                    continue

                # 滑动窗口计算相关系数
                window = self.correlation_window
                correlations: List[float] = []
                for k in range(min_ret_len - window + 1):
                    corr = self._pearson_correlation(
                        returns_a[k:k + window],
                        returns_b[k:k + window],
                    )
                    correlations.append(corr)

                # 检测相关系数突变
                for k in range(1, len(correlations)):
                    drop = correlations[k - 1] - correlations[k]
                    if drop >= self.correlation_breakdown_threshold:
                        severity = "high" if drop >= 0.8 else (
                            "medium" if drop >= 0.6 else "low"
                        )
                        anomalies.append({
                            "symbol_pair": f"{sym_a} vs {sym_b}",
                            "window_start": k + window,
                            "correlation_before": round(correlations[k - 1], 4),
                            "correlation_after": round(correlations[k], 4),
                            "correlation_drop": round(drop, 4),
                            "severity": severity,
                        })

        logger.info(f"相关性断裂检测完成: 共 {len(anomalies)} 个断裂点")
        return anomalies

    # ==================== 拉高出货检测 ====================

    def detect_pump_dump(
        self,
        prices: List[float],
        volumes: List[float],
        lookback: int = 5,
        dump_threshold: float = 0.10,
        volume_spike_threshold: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """
        拉高出货（Pump & Dump）检测

        检测模式：
        1. 短期内价格快速上涨（lookback 天内涨幅超过阈值）
        2. 上涨期间伴随成交量激增
        3. 随后价格快速回落

        Args:
            prices: 价格序列
            volumes: 成交量序列
            lookback: 回看窗口（天数）
            dump_threshold: 拉高涨幅阈值（默认 10%）
            volume_spike_threshold: 成交量激增阈值（相对均值的倍数）

        Returns:
            异常列表，每项包含：
            - pump_start: 拉高起始位置
            - pump_peak: 拉高峰值位置
            - peak_price: 峰值价格
            - pump_gain: 拉高涨幅
            - subsequent_drop: 随后跌幅
            - volume_ratio: 成交量相对均值的倍数
            - severity: 严重程度
        """
        if len(prices) < lookback + 3 or len(prices) != len(volumes):
            logger.warning("数据长度不足或价格/成交量长度不匹配")
            return []

        anomalies: List[Dict[str, Any]] = []
        mean_vol = self._mean(volumes)

        for i in range(lookback, len(prices) - 2):
            # 检查 lookback 窗口内的涨幅
            start_price = prices[i - lookback]
            current_price = prices[i]
            gain = (current_price - start_price) / start_price if start_price > 0 else 0

            if gain < dump_threshold:
                continue

            # 检查窗口内成交量是否激增
            window_volumes = volumes[i - lookback:i + 1]
            window_mean_vol = self._mean(window_volumes)
            vol_ratio = window_mean_vol / mean_vol if mean_vol > 0 else 0

            if vol_ratio < volume_spike_threshold:
                continue

            # 检查随后是否回落
            next_price = prices[i + 1] if i + 1 < len(prices) else current_price
            drop = (current_price - next_price) / current_price if current_price > 0 else 0

            # 判断严重程度
            if gain >= 0.20 and drop >= 0.05:
                severity = "high"
            elif gain >= 0.15 and drop >= 0.03:
                severity = "medium"
            else:
                severity = "low"

            anomalies.append({
                "pump_start": i - lookback,
                "pump_peak": i,
                "peak_price": current_price,
                "pump_gain": round(gain, 4),
                "subsequent_drop": round(drop, 4),
                "volume_ratio": round(vol_ratio, 2),
                "severity": severity,
                "type": "pump_dump",
            })

        logger.info(f"拉高出货检测完成: 共 {len(anomalies)} 个疑似事件")
        return anomalies

    # ==================== 异常报告生成 ====================

    def generate_anomaly_report(
        self,
        symbol: str,
        anomalies: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成异常检测综合报告

        Args:
            symbol: 标的代码
            anomalies: 所有异常列表（可混合不同类型的异常）

        Returns:
            综合报告字典，包含：
            - symbol: 标的代码
            - total_anomalies: 异常总数
            - by_severity: 按严重程度分类统计
            - by_type: 按类型分类统计
            - anomalies: 异常详情列表
            - risk_level: 综合风险等级
            - summary: 文字摘要
        """
        # 按严重程度分类
        by_severity = {"high": 0, "medium": 0, "low": 0}
        by_type: Dict[str, int] = {}

        for anomaly in anomalies:
            severity = anomaly.get("severity", "low")
            by_severity[severity] = by_severity.get(severity, 0) + 1

            anomaly_type = anomaly.get("type", "unknown")
            by_type[anomaly_type] = by_type.get(anomaly_type, 0) + 1

        # 综合风险等级
        if by_severity["high"] >= 3:
            risk_level = "critical"
        elif by_severity["high"] >= 1:
            risk_level = "high"
        elif by_severity["medium"] >= 3:
            risk_level = "medium"
        elif by_severity["medium"] >= 1 or by_severity["low"] >= 5:
            risk_level = "low"
        else:
            risk_level = "minimal"

        # 生成摘要
        summary_parts = [f"标的 {symbol} 共检测到 {len(anomalies)} 个异常。"]
        if by_severity["high"] > 0:
            summary_parts.append(f"其中高风险异常 {by_severity['high']} 个。")
        if by_type:
            type_desc = "、".join(
                f"{t}({c}次)" for t, c in sorted(by_type.items(), key=lambda x: -x[1])
            )
            summary_parts.append(f"异常类型分布：{type_desc}。")
        summary_parts.append(f"综合风险等级：{risk_level}。")

        report = {
            "symbol": symbol,
            "total_anomalies": len(anomalies),
            "by_severity": by_severity,
            "by_type": by_type,
            "risk_level": risk_level,
            "summary": "".join(summary_parts),
            "anomalies": anomalies,
        }

        logger.info(
            f"异常报告生成: symbol={symbol}, total={len(anomalies)}, "
            f"risk_level={risk_level}"
        )
        return report
