"""
实时行情服务

提供实时行情数据的 WebSocket 推送。
支持模拟数据生成和真实数据接入（如富途 API）。
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TickerData:
    """行情数据"""
    symbol: str
    market: str  # CN/HK/US
    last_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    amount: float
    change_pct: float  # 涨跌幅 %
    change_amount: float  # 涨跌额
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "last_price": self.last_price,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "volume": self.volume,
            "amount": self.amount,
            "change_pct": self.change_pct,
            "change_amount": self.change_amount,
            "timestamp": self.timestamp
        }


class MarketDataProvider:
    """
    实时行情数据提供者

    支持：
    - 模拟数据生成（用于测试和演示）
    - 真实数据接入（通过子类实现）
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._watching_symbols: Dict[str, Dict] = {}  # symbol -> last_data

    def subscribe(self, symbol: str, callback: Callable[[TickerData], None]):
        """订阅行情更新"""
        if symbol not in self._subscribers:
            self._subscribers[symbol] = []
        self._subscribers[symbol].append(callback)
        logger.info(f"订阅行情: {symbol}, 当前订阅者: {len(self._subscribers.get(symbol, []))}")

    def unsubscribe(self, symbol: str, callback: Callable):
        """取消订阅"""
        if symbol in self._subscribers:
            self._subscribers[symbol] = [cb for cb in self._subscribers[symbol] if cb != callback]
            if not self._subscribers[symbol]:
                del self._subscribers[symbol]

    async def start(self):
        """启动行情服务"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("行情服务已启动")

    async def stop(self):
        """停止行情服务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("行情服务已停止")

    async def _run_loop(self):
        """行情更新循环"""
        while self._running:
            try:
                await self._push_updates()
                await asyncio.sleep(1)  # 每秒更新
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"行情更新异常: {e}")
                await asyncio.sleep(5)

    async def _push_updates(self):
        """推送行情更新"""
        for symbol, last_data in list(self._watching_symbols.items()):
            if symbol not in self._subscribers:
                continue

            # 生成模拟更新
            updated = self._generate_update(symbol, last_data)
            self._watching_symbols[symbol] = updated

            # 推送给订阅者
            ticker = TickerData(**updated)
            for callback in self._subscribers.get(symbol, []):
                try:
                    await callback(ticker)
                except Exception as e:
                    logger.error(f"推送行情失败 {symbol}: {e}")

    def _generate_update(self, symbol: str, last_data: Dict) -> Dict:
        """生成模拟行情更新"""
        base_price = last_data.get("last_price", 10.0)

        # 随机价格波动 +-0.5%
        change_pct = random.uniform(-0.5, 0.5)
        new_price = round(base_price * (1 + change_pct / 100), 2)

        # 更新涨跌额和涨跌幅
        open_price = last_data.get("open_price", base_price)
        change_amount = new_price - open_price
        total_change_pct = (change_amount / open_price * 100) if open_price else 0

        return {
            "symbol": symbol,
            "market": last_data.get("market", "CN"),
            "last_price": new_price,
            "open_price": open_price,
            "high_price": max(last_data.get("high_price", new_price), new_price),
            "low_price": min(last_data.get("low_price", new_price), new_price),
            "volume": last_data.get("volume", 0) + random.randint(1000, 10000),
            "amount": last_data.get("amount", 0) + new_price * random.randint(1000, 10000),
            "change_pct": round(total_change_pct, 2),
            "change_amount": round(change_amount, 2),
            "timestamp": datetime.now().isoformat()
        }

    def add_symbol(self, symbol: str, market: str = "CN", initial_price: float = 10.0):
        """添加关注的股票"""
        self._watching_symbols[symbol] = {
            "symbol": symbol,
            "market": market,
            "last_price": initial_price,
            "open_price": initial_price,
            "high_price": initial_price,
            "low_price": initial_price,
            "volume": random.randint(100000, 1000000),
            "amount": initial_price * random.randint(100000, 1000000),
            "change_pct": 0.0,
            "change_amount": 0.0,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"添加关注股票: {symbol} @ {market}, 初始价: {initial_price}")

    def remove_symbol(self, symbol: str):
        """移除关注的股票"""
        if symbol in self._watching_symbols:
            del self._watching_symbols[symbol]
            logger.info(f"移除关注股票: {symbol}")

    def get_current_data(self, symbol: str) -> Optional[Dict]:
        """获取当前行情数据"""
        return self._watching_symbols.get(symbol)


# 全局行情服务实例
market_data_provider = MarketDataProvider()


# ========== WebSocket 广播集成 ==========

async def broadcast_market_ticker(ticker: TickerData):
    """广播行情数据到 WebSocket"""
    from .websocket import ws_manager, Channels

    await ws_manager.broadcast(
        Channels.MARKET_TICKER,
        "market_ticker",
        ticker.to_dict()
    )


def start_market_subscription(symbol: str, market: str = "CN"):
    """开始订阅股票行情（带 WebSocket 广播）"""
    # 添加到关注列表
    if not market_data_provider.get_current_data(symbol):
        # 随机初始价格
        initial_price = random.uniform(5.0, 500.0)
        market_data_provider.add_symbol(symbol, market, initial_price)

    # 订阅更新并广播到 WebSocket
    async def on_update(ticker: TickerData):
        await broadcast_market_ticker(ticker)

    market_data_provider.subscribe(symbol, on_update)

    # 确保服务运行
    if not market_data_provider._running:
        asyncio.create_task(market_data_provider.start())


def stop_market_subscription(symbol: str):
    """停止订阅股票行情"""
    # 需要保存回调引用才能 unsubscribe，这里简化处理
    market_data_provider.remove_symbol(symbol)