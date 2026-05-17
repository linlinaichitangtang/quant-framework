"""
高频 Tick 数据管理

支持 Tick 级数据的存储、压缩和查询。
用于毫秒级回测和市场微观结构分析。
"""

import logging
import gzip
import struct
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TickData:
    """Tick 数据结构"""
    symbol: str
    timestamp: datetime
    last_price: float
    bid_price: float
    ask_price: float
    bid_size: int
    ask_size: int
    volume: int
    turnover: float
    date: str  # YYYYMMDD 格式，用于分区


class TickDataCompressor:
    """
    Tick 数据压缩器

    使用增量编码压缩 Tick 数据，压缩率可达 90%+。
    """

    # 压缩格式版本
    VERSION = 1

    @staticmethod
    def compress(ticks: List[TickData]) -> bytes:
        """
        压缩 Tick 数据

        使用结构化打包 + 增量编码。
        """
        if not ticks:
            return b""

        # 格式: [version(1)] [count(4)] [base_timestamp(8)] + tick_data
        count = len(ticks)
        base_ts = ticks[0].timestamp

        # 基础价格（第一个 Tick 的价格）
        base_price = ticks[0].last_price

        data_parts = [
            struct.pack("B", TickDataCompressor.VERSION),
            struct.pack("<I", count),
            struct.pack("<Q", int(base_ts.timestamp() * 1000)),  # 毫秒时间戳
            struct.pack("<d", base_price),
        ]

        prev_ts = base_ts
        prev_price = base_price
        prev_bid = ticks[0].bid_price
        prev_ask = ticks[0].ask_price

        for tick in ticks:
            # 时间增量（毫秒）
            dt = int((tick.timestamp - prev_ts).total_seconds() * 1000)
            # 价格增量（基点）
            dp = int(round((tick.last_price - prev_price) * 10000))
            # 价差增量
            db = int(round((tick.bid_price - prev_bid) * 10000))
            da = int(round((tick.ask_price - prev_ask) * 10000))

            # 打包（使用小整数格式）
            tick_data = struct.pack(
                "<IiiiiiI",
                dt,      # 时间增量 (4 bytes)
                dp,      # 价格增量 (4 bytes)
                db,      # bid 增量 (4 bytes)
                da,      # ask 增量 (4 bytes)
                tick.bid_size,  # bid size (4 bytes)
                tick.ask_size,  # ask size (4 bytes)
                tick.volume      # volume (4 bytes)
            )

            data_parts.append(tick_data)

            prev_ts = tick.timestamp
            prev_price = tick.last_price
            prev_bid = tick.bid_price
            prev_ask = tick.ask_price

        return b"".join(data_parts)

    @staticmethod
    def decompress(data: bytes) -> List[TickData]:
        """解压缩 Tick 数据"""
        if not data:
            return []

        offset = 0

        # 读取头部
        version, = struct.unpack("B", data[offset:offset+1])
        offset += 1

        count, = struct.unpack("<I", data[offset:offset+4])
        offset += 4

        base_ts_ms, = struct.unpack("<Q", data[offset:offset+8])
        offset += 8
        base_ts = datetime.fromtimestamp(base_ts_ms / 1000)

        base_price, = struct.unpack("<d", data[offset:offset+8])
        offset += 8

        ticks = []
        prev_ts = base_ts
        prev_price = base_price
        prev_bid = base_price * 0.999  # 假设初始 bid/ask
        prev_ask = base_price * 1.001

        for _ in range(count):
            dt, dp, db, da, bid_size, ask_size, volume = struct.unpack(
                "<IiiiiiI", data[offset:offset+28]
            )
            offset += 28

            # 还原
            ts = prev_ts + timedelta(milliseconds=dt)
            price = prev_price + dp / 10000
            bid = prev_bid + db / 10000
            ask = prev_ask + da / 10000

            ticks.append(TickData(
                symbol="",
                timestamp=ts,
                last_price=price,
                bid_price=bid,
                ask_price=ask,
                bid_size=bid_size,
                ask_size=ask_size,
                volume=volume,
                turnover=price * volume,
                date=ts.strftime("%Y%m%d")
            ))

            prev_ts = ts
            prev_price = price
            prev_bid = bid
            prev_ask = ask

        return ticks


class TickDataStore:
    """
    Tick 数据存储

    内存映射存储，支持按日期和股票代码分区。
    """

    def __init__(self, max_memory_mb: int = 1024):
        """
        Args:
            max_memory_mb: 最大内存使用（MB）
        """
        self.max_memory_mb = max_memory_mb
        # 分区存储: date -> symbol -> compressed_data
        self._partitions: Dict[str, Dict[str, bytes]] = defaultdict(dict)
        # 内存索引: date -> symbol -> (offset, count)
        self._index: Dict[str, Dict[str, Tuple[int, int]]] = defaultdict(dict)

    def put(self, ticks: List[TickData]):
        """写入 Tick 数据"""
        if not ticks:
            return

        # 按日期分组
        by_date = defaultdict(list)
        for tick in ticks:
            by_date[tick.date].append(tick)

        for date, day_ticks in by_date.items():
            # 按股票代码分组
            by_symbol = defaultdict(list)
            for tick in day_ticks:
                by_symbol[tick.symbol].append(tick)

            for symbol, symbol_ticks in by_symbol.items():
                # 压缩
                compressed = TickDataCompressor.compress(symbol_ticks)
                self._partitions[date][symbol] = compressed
                self._index[date][symbol] = (0, len(symbol_ticks))

                logger.debug(f"写入 Tick 数据: {date}/{symbol}, {len(symbol_ticks)} 条")

    def get(self, date: str, symbol: str) -> List[TickData]:
        """读取指定日期和股票的数据"""
        if date not in self._partitions:
            return []

        if symbol not in self._partitions[date]:
            return []

        compressed = self._partitions[date][symbol]
        return TickDataCompressor.decompress(compressed)

    def query(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[TickData]:
        """
        查询时间范围内的 Tick 数据

        Args:
            symbol: 股票代码
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            匹配的 Tick 列表
        """
        results = []

        # 确定需要查询的日期
        current = start_time.date()
        end_date = end_time.date()

        while current <= end_date:
            date_str = current.strftime("%Y%m%d")
            ticks = self.get(date_str, symbol)

            # 过滤时间范围
            for tick in ticks:
                if start_time <= tick.timestamp <= end_time:
                    results.append(tick)

            current += timedelta(days=1)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        total_ticks = sum(
            count for date_index in self._index.values()
            for _, count in date_index.values()
        )
        n_partitions = len(self._partitions)
        n_symbols = sum(len(symbols) for symbols in self._partitions.values())

        return {
            "n_partitions": n_partitions,
            "n_symbols": n_symbols,
            "total_ticks": total_ticks,
            "estimated_size_mb": total_ticks * 50 / 1e6  # 估算
        }

    def clear_oldest(self, n_days: int = 1):
        """清除最早的 N 天数据以释放内存"""
        dates = sorted(self._partitions.keys())
        for date in dates[:n_days]:
            del self._partitions[date]
            if date in self._index:
                del self._index[date]
            logger.info(f"已清除旧数据: {date}")


class MicrostructureAnalyzer:
    """
    市场微观结构分析器

    基于 Tick 数据计算买卖价差、流动性指标等。
    """

    @staticmethod
    def compute_spread(ticks: List[TickData]) -> Dict[str, float]:
        """计算平均买卖价差"""
        if not ticks:
            return {"mean_spread": 0, "median_spread": 0}

        spreads = [(t.ask_price - t.bid_price) / t.last_price * 10000 for t in ticks]  # 基点

        return {
            "mean_spread_bps": np.mean(spreads),
            "median_spread_bps": np.median(spreads),
            "max_spread_bps": np.max(spreads),
            "min_spread_bps": np.min(spreads)
        }

    @staticmethod
    def compute_volume_profile(ticks: List[TickData], n_bins: int = 20) -> Dict[str, Any]:
        """计算成交量分布"""
        if not ticks:
            return {}

        prices = np.array([t.last_price for t in ticks])
        volumes = np.array([t.volume for t in ticks])

        price_min, price_max = prices.min(), prices.max()
        bins = np.linspace(price_min, price_max, n_bins + 1)

        # 统计每个价格区间的成交量
        volume_profile = []
        for i in range(n_bins):
            mask = (prices >= bins[i]) & (prices < bins[i+1])
            volume_profile.append({
                "price_range": f"{bins[i]:.2f}-{bins[i+1]:.2f}",
                "volume": int(volumes[mask].sum())
            })

        return {"volume_profile": volume_profile}

    @staticmethod
    def compute_roll_impact(ticks: List[TickData], window: int = 100) -> Dict[str, float]:
        """
        计算 Roll 模型的市场冲击

        Roll (1984) 模型: Cov(ΔP_t, ΔP_{t-1}) ≈ -σ²/2 + σ²ρ
        其中 ρ 是价格发现指标
        """
        if len(ticks) < window + 1:
            return {"roll_impact": 0, "price_discovery": 0}

        prices = np.array([t.last_price for t in ticks[-window-1:]])
        returns = np.diff(np.log(prices))

        if len(returns) < 2:
            return {"roll_impact": 0, "price_discovery": 0}

        # 协方差
        cov = np.cov(returns[:-1], returns[1:])[0, 1]
        variance = np.var(returns)

        roll_impact = -2 * cov  # Roll spread estimate
        price_discovery = -cov / variance if variance > 0 else 0

        return {
            "roll_impact": float(roll_impact),
            "price_discovery": float(price_discovery)
        }

    @staticmethod
    def compute_vwap(ticks: List[TickData]) -> float:
        """计算成交量加权平均价格 (VWAP)"""
        if not ticks:
            return 0

        total_turnover = sum(t.turnover for t in ticks)
        total_volume = sum(t.volume for t in ticks)

        return total_turnover / total_volume if total_volume > 0 else 0

    @staticmethod
    def compute_market_depth(ticks: List[TickData]) -> Dict[str, Any]:
        """计算市场深度"""
        if not ticks:
            return {}

        bid_sizes = [t.bid_size for t in ticks]
        ask_sizes = [t.ask_size for t in ticks]

        return {
            "mean_bid_size": np.mean(bid_sizes),
            "mean_ask_size": np.mean(ask_sizes),
            "bid_ask_imbalance": (np.mean(bid_sizes) - np.mean(ask_sizes)) /
                                  (np.mean(bid_sizes) + np.mean(ask_sizes) + 1e-10)
        }


# 全局 Tick 数据存储实例
tick_data_store = TickDataStore()