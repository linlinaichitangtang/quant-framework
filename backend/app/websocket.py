"""
WebSocket 实时推送管理器

支持多客户端连接、频道订阅、事件广播。
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 活跃连接：{client_id: WebSocket}
        self._connections: Dict[str, WebSocket] = {}
        # 频道订阅：{channel: set(client_ids)}
        self._channels: Dict[str, Set[str]] = {}
        # 客户端订阅的频道：{client_id: set(channels)}
        self._client_channels: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """
        接受新连接

        Args:
            websocket: WebSocket 实例
            client_id: 客户端 ID（可选，自动生成）

        Returns:
            客户端 ID
        """
        await websocket.accept()
        if not client_id:
            client_id = f"client_{id(websocket)}_{datetime.now().timestamp()}"
        async with self._lock:
            self._connections[client_id] = websocket
            self._client_channels[client_id] = set()
        logger.info(f"WebSocket 客户端连接: {client_id}, 当前连接数: {len(self._connections)}")
        return client_id

    async def disconnect(self, client_id: str):
        """断开连接并清理订阅"""
        async with self._lock:
            # 从所有频道中移除
            channels = self._client_channels.pop(client_id, set())
            for channel in channels:
                if channel in self._channels:
                    self._channels[channel].discard(client_id)
                    if not self._channels[channel]:
                        del self._channels[channel]
            self._connections.pop(client_id, None)
        logger.info(f"WebSocket 客户端断开: {client_id}, 当前连接数: {len(self._connections)}")

    async def subscribe(self, client_id: str, channel: str):
        """订阅频道"""
        async with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)
            self._client_channels[client_id].add(channel)
        logger.debug(f"客户端 {client_id} 订阅频道: {channel}")

    async def unsubscribe(self, client_id: str, channel: str):
        """取消订阅频道"""
        async with self._lock:
            if channel in self._channels:
                self._channels[channel].discard(client_id)
            if client_id in self._client_channels:
                self._client_channels[client_id].discard(channel)
        logger.debug(f"客户端 {client_id} 取消订阅: {channel}")

    async def broadcast(self, channel: str, event: str, data: Any):
        """
        向频道广播消息

        Args:
            channel: 频道名称
            event: 事件类型
            data: 事件数据
        """
        message = json.dumps({
            "channel": channel,
            "event": event,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False, default=str)

        async with self._lock:
            client_ids = list(self._channels.get(channel, set()))

        disconnected = []
        for cid in client_ids:
            ws = self._connections.get(cid)
            if ws:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(cid)

        # 清理断开的连接
        for cid in disconnected:
            await self.disconnect(cid)

    async def send_to_client(self, client_id: str, event: str, data: Any):
        """向指定客户端发送消息"""
        ws = self._connections.get(client_id)
        if ws:
            message = json.dumps({
                "event": event,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False, default=str)
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(client_id)

    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self._connections)

    def get_channel_subscribers(self, channel: str) -> int:
        """获取频道订阅数"""
        return len(self._channels.get(channel, set()))


# 全局连接管理器实例
ws_manager = ConnectionManager()


# ========== 预定义频道 ==========
class Channels:
    """WebSocket 频道常量"""
    # 行情频道
    MARKET_TICKER = "market:ticker"           # 实时行情
    MARKET_DEPTH = "market:depth"             # 盘口深度

    # 交易频道
    SIGNAL_CREATED = "signal:created"         # 新信号创建
    SIGNAL_UPDATED = "signal:updated"         # 信号状态变更
    TRADE_EXECUTED = "trade:executed"         # 交易执行
    ORDER_UPDATED = "order:updated"           # 订单状态更新

    # 持仓频道
    POSITION_CHANGED = "position:changed"     # 持仓变动
    POSITION_PNL = "position:pnl"             # 持仓盈亏更新

    # 系统频道
    SYSTEM_ALERT = "system:alert"             # 系统告警
    SYSTEM_LOG = "system:log"                 # 系统日志
    NOTIFICATION = "notification"              # 通知推送


# ========== 便捷广播函数 ==========

async def broadcast_signal_created(signal_data: dict):
    """广播新信号创建"""
    await ws_manager.broadcast(Channels.SIGNAL_CREATED, "signal_created", signal_data)


async def broadcast_signal_updated(signal_id: int, status: str):
    """广播信号状态变更"""
    await ws_manager.broadcast(Channels.SIGNAL_UPDATED, "signal_updated", {
        "signal_id": signal_id,
        "status": status
    })


async def broadcast_trade_executed(trade_data: dict):
    """广播交易执行"""
    await ws_manager.broadcast(Channels.TRADE_EXECUTED, "trade_executed", trade_data)


async def broadcast_position_changed(position_data: dict):
    """广播持仓变动"""
    await ws_manager.broadcast(Channels.POSITION_CHANGED, "position_changed", position_data)


async def broadcast_notification(notification_data: dict):
    """广播通知"""
    await ws_manager.broadcast(Channels.NOTIFICATION, "notification", notification_data)


async def broadcast_system_alert(alert_data: dict):
    """广播系统告警"""
    await ws_manager.broadcast(Channels.SYSTEM_ALERT, "system_alert", alert_data)
