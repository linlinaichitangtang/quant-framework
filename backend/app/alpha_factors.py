"""
阿尔法因子库

提供量化因子的定义、计算和分析功能。
基于业界标准的因子框架设计。
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class FactorCategory(Enum):
    """因子类别"""
    PRICE = "price"              # 价格因子
    VOLUME = "volume"            # 量能因子
    MOMENTUM = "momentum"        # 动量因子
    VOLATILITY = "volatility"   # 波动率因子
    QUALITY = "quality"          # 质量因子
    VALUE = "value"             # 价值因子
    GROWTH = "growth"           # 成长因子
    CUSTOM = "custom"           # 自定义因子


@dataclass
class FactorDefinition:
    """因子定义"""
    name: str
    category: FactorCategory
    description: str
    required_columns: List[str]
    compute_func: Callable[[pd.DataFrame], pd.Series]
    lower_is_better: bool = False  # 是否是"越小越好"因子


@dataclass
class FactorAnalysisResult:
    """因子分析结果"""
    factor_name: str
    ic: float                   # 信息系数
    ir: float                   # 信息比率
    rank_ic: float              # 排名 IC
    returns_by_quantile: Dict[int, float]  # 分位数收益
    cumulative_returns: List[float]  # 累积收益曲线


class AlphaFactorLibrary:
    """
    阿尔法因子库

    提供预定义因子和自定义因子注册功能。
    """

    def __init__(self):
        self._factors: Dict[str, FactorDefinition] = {}
        self._register_default_factors()

    def _register_default_factors(self):
        """注册默认因子"""

        # ========== 价格因子 ==========

        self.register(FactorDefinition(
            name="close",
            category=FactorCategory.PRICE,
            description="收盘价",
            required_columns=["close"],
            compute_func=lambda df: df["close"]
        ))

        self.register(FactorDefinition(
            name="returns_1d",
            category=FactorCategory.MOMENTUM,
            description="1日收益率",
            required_columns=["close"],
            compute_func=lambda df: df["close"].pct_change(1)
        ))

        self.register(FactorDefinition(
            name="returns_5d",
            category=FactorCategory.MOMENTUM,
            description="5日收益率",
            required_columns=["close"],
            compute_func=lambda df: df["close"].pct_change(5)
        ))

        self.register(FactorDefinition(
            name="returns_20d",
            category=FactorCategory.MOMENTUM,
            description="20日收益率",
            required_columns=["close"],
            compute_func=lambda df: df["close"].pct_change(20)
        ))

        # ========== 均线因子 ==========

        self.register(FactorDefinition(
            name="ma5",
            category=FactorCategory.PRICE,
            description="5日均线",
            required_columns=["close"],
            compute_func=lambda df: df["close"].rolling(5).mean()
        ))

        self.register(FactorDefinition(
            name="ma20",
            category=FactorCategory.PRICE,
            description="20日均线",
            required_columns=["close"],
            compute_func=lambda df: df["close"].rolling(20).mean()
        ))

        self.register(FactorDefinition(
            name="ma60",
            category=FactorCategory.PRICE,
            description="60日均线",
            required_columns=["close"],
            compute_func=lambda df: df["close"].rolling(60).mean()
        ))

        self.register(FactorDefinition(
            name="price_to_ma20",
            category=FactorCategory.PRICE,
            description="收盘价/20日均线",
            required_columns=["close"],
            compute_func=lambda df: df["close"] / df["close"].rolling(20).mean()
        ))

        # ========== 量能因子 ==========

        self.register(FactorDefinition(
            name="volume",
            category=FactorCategory.VOLUME,
            description="成交量",
            required_columns=["volume"],
            compute_func=lambda df: df["volume"]
        ))

        self.register(FactorDefinition(
            name="volume_ratio",
            category=FactorCategory.VOLUME,
            description="量比（当日成交量/5日均量）",
            required_columns=["volume"],
            compute_func=lambda df: df["volume"] / df["volume"].rolling(5).mean()
        ))

        self.register(FactorDefinition(
            name="amount",
            category=FactorCategory.VOLUME,
            description="成交额",
            required_columns=["amount"],
            compute_func=lambda df: df["amount"]
        ))

        self.register(FactorDefinition(
            name="turnover_rate",
            category=FactorCategory.VOLUME,
            description="换手率",
            required_columns=["turnover"],
            compute_func=lambda df: df.get("turnover", pd.Series(0, index=df.index))
        ))

        # ========== 波动率因子 ==========

        self.register(FactorDefinition(
            name="volatility_20d",
            category=FactorCategory.VOLATILITY,
            description="20日波动率",
            required_columns=["close"],
            compute_func=lambda df: df["close"].pct_change().rolling(20).std()
        ))

        self.register(FactorDefinition(
            name="volatility_60d",
            category=FactorCategory.VOLATILITY,
            description="60日波动率",
            required_columns=["close"],
            compute_func=lambda df: df["close"].pct_change().rolling(60).std()
        ))

        self.register(FactorDefinition(
            name="high_low_ratio",
            category=FactorCategory.VOLATILITY,
            description="最高价/最低价",
            required_columns=["high", "low"],
            compute_func=lambda df: df["high"] / df["low"]
        ))

        # ========== 动量因子 ==========

        self.register(FactorDefinition(
            name="momentum_20d",
            category=FactorCategory.MOMENTUM,
            description="20日动量",
            required_columns=["close"],
            compute_func=lambda df: df["close"] / df["close"].shift(20) - 1
        ))

        self.register(FactorDefinition(
            name="momentum_60d",
            category=FactorCategory.MOMENTUM,
            description="60日动量",
            required_columns=["close"],
            compute_func=lambda df: df["close"] / df["close"].shift(60) - 1
        ))

        self.register(FactorDefinition(
            name="rsi_14",
            category=FactorCategory.MOMENTUM,
            description="RSI（14日）",
            required_columns=["close"],
            compute_func=lambda df: self._compute_rsi(df["close"], 14)
        ))

        # ========== 质量因子 ==========

        self.register(FactorDefinition(
            name="roe",
            category=FactorCategory.QUALITY,
            description="净资产收益率",
            required_columns=["roe"],
            compute_func=lambda df: df.get("roe", pd.Series(np.nan, index=df.index))
        ))

        self.register(FactorDefinition(
            name="roa",
            category=FactorCategory.QUALITY,
            description="资产收益率",
            required_columns=["roa"],
            compute_func=lambda df: df.get("roa", pd.Series(np.nan, index=df.index))
        ))

        self.register(FactorDefinition(
            name="debt_to_equity",
            category=FactorCategory.QUALITY,
            description="资产负债率",
            required_columns=["debt", "equity"],
            compute_func=lambda df: df.get("debt", pd.Series(0, index=df.index)) / df.get("equity", pd.Series(1, index=df.index))
        ))

        # ========== 价值因子 ==========

        self.register(FactorDefinition(
            name="pe_ratio",
            category=FactorCategory.VALUE,
            description="市盈率",
            required_columns=["pe"],
            compute_func=lambda df: df.get("pe", pd.Series(np.nan, index=df.index))
        ))

        self.register(FactorDefinition(
            name="pb_ratio",
            category=FactorCategory.VALUE,
            description="市净率",
            required_columns=["pb"],
            compute_func=lambda df: df.get("pb", pd.Series(np.nan, index=df.index))
        ))

        self.register(FactorDefinition(
            name="ps_ratio",
            category=FactorCategory.VALUE,
            description="市销率",
            required_columns=["ps"],
            compute_func=lambda df: df.get("ps", pd.Series(np.nan, index=df.index))
        ))

        logger.info(f"已注册 {len(self._factors)} 个默认因子")

    @staticmethod
    def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
        """计算 RSI"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def register(self, factor: FactorDefinition):
        """注册因子"""
        self._factors[factor.name] = factor
        logger.debug(f"已注册因子: {factor.name}")

    def unregister(self, factor_name: str):
        """注销因子"""
        if factor_name in self._factors:
            del self._factors[factor_name]

    def get_factor(self, factor_name: str) -> Optional[FactorDefinition]:
        """获取因子定义"""
        return self._factors.get(factor_name)

    def list_factors(self, category: Optional[FactorCategory] = None) -> List[str]:
        """列出因子名称"""
        if category:
            return [f.name for f in self._factors.values() if f.category == category]
        return list(self._factors.keys())

    def list_by_category(self) -> Dict[FactorCategory, List[str]]:
        """按类别列出因子"""
        result = {cat: [] for cat in FactorCategory}
        for factor in self._factors.values():
            result[factor.category].append(factor.name)
        return result

    def compute_factor(self, factor_name: str, data: pd.DataFrame) -> pd.Series:
        """
        计算单个因子

        Args:
            factor_name: 因子名称
            data: 包含所需列的 DataFrame

        Returns:
            因子值序列
        """
        factor = self._factors.get(factor_name)
        if not factor:
            raise ValueError(f"因子不存在: {factor_name}")

        # 检查必需列
        missing = set(factor.required_columns) - set(data.columns)
        if missing:
            raise ValueError(f"数据缺少必要列: {missing}")

        return factor.compute_func(data)

    def compute_factors(
        self,
        factor_names: List[str],
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        批量计算因子

        Returns:
            因子值 DataFrame
        """
        result = pd.DataFrame(index=data.index)

        for name in factor_names:
            try:
                result[name] = self.compute_factor(name, data)
            except Exception as e:
                logger.error(f"计算因子 {name} 失败: {e}")
                result[name] = np.nan

        return result

    def analyze_factor(
        self,
        factor_values: pd.Series,
        forward_returns: pd.Series,
        n_quantiles: int = 5
    ) -> FactorAnalysisResult:
        """
        分析因子有效性

        Args:
            factor_values: 因子值
            forward_returns: 未来收益率
            n_quantiles: 分位数数量

        Returns:
            因子分析结果
        """
        # 对齐数据
        valid_idx = factor_values.notna() & forward_returns.notna()
        fv = factor_values[valid_idx]
        fr = forward_returns[valid_idx]

        if len(fv) < 30:
            return FactorAnalysisResult(
                factor_name=factor_values.name or "unknown",
                ic=0, ir=0, rank_ic=0,
                returns_by_quantile={},
                cumulative_returns=[]
            )

        # 计算 IC（信息系数）
        ic = fv.corr(fr)

        # 计算 Rank IC（排名相关系数）
        rank_ic = fv.rank().corr(fr.rank())

        # 计算 IR（信息比率）- 需要时间序列
        # 简化处理：使用 IC 的均值/标准差
        if len(fv) > 60:
            # 月度 IC
            monthly_ic = []
            for month in range(0, len(fv), 20):
                month_end = min(month + 20, len(fv))
                month_ic = fv.iloc[month:month_end].corr(fr.iloc[month:month_end])
                if not np.isnan(month_ic):
                    monthly_ic.append(month_ic)

            ir = np.mean(monthly_ic) / np.std(monthly_ic) if len(monthly_ic) > 1 else 0
        else:
            ir = 0

        # 计算分位数收益
        quantile_returns = {}
        try:
            quantile_labels = pd.qcut(fv, n_quantiles, labels=False, duplicates='drop')
            for q in range(n_quantiles):
                mask = quantile_labels == q
                if mask.sum() > 0:
                    quantile_returns[q + 1] = fr[mask].mean()
        except Exception as e:
            logger.warning(f"分位数计算失败: {e}")

        return FactorAnalysisResult(
            factor_name=factor_values.name or "unknown",
            ic=float(ic) if not np.isnan(ic) else 0,
            ir=float(ir) if not np.isnan(ir) else 0,
            rank_ic=float(rank_ic) if not np.isnan(rank_ic) else 0,
            returns_by_quantile=quantile_returns,
            cumulative_returns=[]
        )


# 全局因子库实例
alpha_factor_library = AlphaFactorLibrary()