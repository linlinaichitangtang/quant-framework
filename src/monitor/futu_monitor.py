"""
富途实时行情监控服务
将富途 OpenD 实时行情接入 PriceChangeMonitor / VolumeSpikeMonitor

支持：
- 多标的实时价格/成交量监控
- 阈值触发事件回调
- 定期轮询 + 事件驱动
"""

import threading
import time
from datetime import datetime
from typing import List, Optional, Dict, Callable

from src.data import FutuProvider
from src.data_types import TickData, MarketEvent
from src.monitor.price import PriceChangeMonitor
from src.monitor.volume import VolumeSpikeMonitor
from src.monitor.base import BaseMonitor
from src.utils.logging import logger


class FutuMonitorService:
    """
    富途实时行情监控服务

    用法：
        service = FutuMonitorService(['CN.600000', 'HK.00700'])
        service.add_monitor(PriceChangeMonitor(up_threshold=0.03, down_threshold=-0.03))
        service.add_monitor(VolumeSpikeMonitor(window_size=20, multiple_threshold=3.0))
        service.register_event_callback(lambda e: print(f"[ALERT] {e.message}"))
        service.start()
        # ...
        service.stop()
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        poll_interval: float = 5.0,
        host: str = "127.0.0.1",
        port: int = 11111,
    ):
        """
        Args:
            symbols: 初始监控标的列表（内部格式）
            poll_interval: 轮询间隔（秒），默认5秒
            host: Futu OpenD 地址
            port: Futu OpenD 端口
        """
        self._symbols: List[str] = symbols or []
        self._poll_interval = poll_interval
        self._host = host
        self._port = port

        self._provider = FutuProvider(host=host, port=port)
        self._monitors: List[BaseMonitor] = []
        self._event_callbacks: List[Callable[[MarketEvent], None]] = []

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_quotes: Dict[str, Dict] = {}  # symbol → quote row

    # ─── 配置 ──────────────────────────────────────────────────

    def add_symbol(self, symbol: str):
        """添加监控标的"""
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            logger.info(f"[FutuMonitor] 添加标的 {symbol}")

    def remove_symbol(self, symbol: str):
        """移除监控标的"""
        if symbol in self._symbols:
            self._symbols.remove(symbol)
            logger.info(f"[FutuMonitor] 移除标的 {symbol}")

    def add_monitor(self, monitor: BaseMonitor):
        """注册监控器"""
        self._monitors.append(monitor)
        logger.info(f"[FutuMonitor] 注册监控器 {monitor.__class__.__name__}")

    def register_event_callback(self, callback: Callable[[MarketEvent], None]):
        """注册事件回调（当监控器触发事件时调用）"""
        self._event_callbacks.append(callback)

    # ─── 生命周期 ──────────────────────────────────────────────

    def start(self):
        """启动监控线程"""
        if self._running:
            logger.warning("[FutuMonitor] 服务已在运行")
            return

        self._running = True
        self._provider.connect()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"[FutuMonitor] 启动成功，监控标的: {self._symbols}，轮询间隔: {self._poll_interval}s")

    def stop(self):
        """停止监控线程"""
        if not self._running:
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        self._provider.close()
        logger.info("[FutuMonitor] 已停止")

    # ─── 内部 ─────────────────────────────────────────────────

    def _run_loop(self):
        """主轮询循环"""
        while self._running:
            try:
                self._poll_and_dispatch()
            except Exception as e:
                logger.error(f"[FutuMonitor] 轮询异常: {e}")
            time.sleep(self._poll_interval)

    def _poll_and_dispatch(self):
        """拉取行情并分发给所有监控器"""
        if not self._symbols:
            return

        # 获取实时行情
        quotes = self._provider.get_stock_quote(self._symbols)
        if quotes.empty:
            logger.warning(f"[FutuMonitor] 行情拉取为空 ({self._symbols})")
            return

        for _, row in quotes.iterrows():
            tick = self._quote_row_to_tick(row)
            if tick is None:
                continue

            # 记录上一条行情（用于计算成交量变化）
            self._last_quotes[tick.symbol] = row.to_dict()

            # 分发给所有监控器
            for monitor in self._monitors:
                try:
                    monitor.on_tick(tick)
                except Exception as e:
                    logger.error(f"[FutuMonitor] {monitor.__class__.__name__} on_tick 异常: {e}")

    def _quote_row_to_tick(self, row) -> Optional[TickData]:
        """将富途行情行转换为 TickData"""
        try:
            code = str(row.get("code", ""))
            last_price = float(row.get("last_price", 0))
            volume = float(row.get("volume", 0))
            open_price = float(row.get("open_price") or 0)
            high_price = float(row.get("high_price") or 0)
            low_price = float(row.get("low_price") or 0)
            data_time = str(row.get("data_time", ""))

            # 解析时间戳
            try:
                ts = datetime.fromisoformat(data_time.replace(" ", "T"))
            except Exception:
                ts = datetime.now()

            return TickData(
                symbol=code,
                price=last_price,
                volume=volume,
                timestamp=ts,
                open=open_price if open_price > 0 else None,
                high=high_price if high_price > 0 else None,
                low=low_price if low_price > 0 else None,
            )
        except Exception as e:
            logger.error(f"[FutuMonitor] 行情行转换 TickData 失败: {e}")
            return None

    def _emit_event(self, event: MarketEvent):
        """内部事件发射（监控器通过此方法触发回调）"""
        logger.info(f"[FutuMonitor EVENT] {event.message}")
        for cb in self._event_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"[FutuMonitor] 事件回调异常: {e}")

    # ─── 便捷构造器 ────────────────────────────────────────────

    @classmethod
    def for_evening_pick(
        cls,
        symbols: List[str],
        up_threshold: float = 0.03,
        down_threshold: float = -0.03,
        volume_multiple: float = 3.0,
        poll_interval: float = 10.0,
    ) -> "FutuMonitorService":
        """
        便捷构造器：创建适合尾盘选股的监控服务

        Args:
            symbols: 监控标的
            up_threshold: 上涨阈值（3%），超过则预警
            down_threshold: 下跌阈值（-3%），超过则预警
            volume_multiple: 成交量放量倍数（3倍）
            poll_interval: 轮询间隔（秒）
        """
        service = cls(symbols=symbols, poll_interval=poll_interval)

        price_monitor = PriceChangeMonitor(
            up_threshold=up_threshold,
            down_threshold=down_threshold,
        )
        price_monitor.register_callback(service._emit_event)
        service.add_monitor(price_monitor)

        vol_monitor = VolumeSpikeMonitor(
            window_size=20,
            multiple_threshold=volume_multiple,
        )
        vol_monitor.register_callback(service._emit_event)
        service.add_monitor(vol_monitor)

        return service


if __name__ == "__main__":
    # 示例：监控A股 + 港股 + 美股
    def on_alert(event: MarketEvent):
        print(f"\n🚨 【警报】{event.symbol} {event.event_type}")
        print(f"   {event.message}")
        print(f"   数据: {event.data}\n")

    service = FutuMonitorService.for_evening_pick(
        symbols=["CN.600000", "CN.601318", "HK.00700", "US.QQQ"],
        up_threshold=0.03,
        down_threshold=-0.03,
        volume_multiple=3.0,
        poll_interval=10.0,
    )
    service.register_event_callback(on_alert)
    service.start()

    print("FutMonitorService 已启动，按 Ctrl+C 停止")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()
        print("已停止")
