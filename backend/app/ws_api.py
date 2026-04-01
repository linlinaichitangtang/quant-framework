"""
WebSocket API 路由

提供 WebSocket 连接端点和通知历史查询。
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from .database import get_db
from .websocket import ws_manager, Channels
from .auth import get_current_user
from . import crud

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 主端点

    连接后可发送以下命令：
    - {"action": "subscribe", "channel": "channel_name"}
    - {"action": "unsubscribe", "channel": "channel_name"}
    - {"action": "ping"}

    服务端会推送：
    - {"channel": "...", "event": "...", "data": {...}, "timestamp": "..."}
    """
    client_id = await ws_manager.connect(websocket)

    try:
        # 默认订阅通知频道
        await ws_manager.subscribe(client_id, Channels.NOTIFICATION)
        await ws_manager.subscribe(client_id, Channels.SYSTEM_ALERT)

        # 发送欢迎消息
        await ws_manager.send_to_client(client_id, "connected", {
            "client_id": client_id,
            "message": "连接成功",
            "available_channels": [
                Channels.MARKET_TICKER,
                Channels.SIGNAL_CREATED,
                Channels.SIGNAL_UPDATED,
                Channels.TRADE_EXECUTED,
                Channels.POSITION_CHANGED,
                Channels.SYSTEM_ALERT,
                Channels.NOTIFICATION,
            ]
        })

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                action = msg.get("action")

                if action == "subscribe":
                    channel = msg.get("channel")
                    if channel:
                        await ws_manager.subscribe(client_id, channel)
                        await ws_manager.send_to_client(client_id, "subscribed", {
                            "channel": channel
                        })

                elif action == "unsubscribe":
                    channel = msg.get("channel")
                    if channel:
                        await ws_manager.unsubscribe(client_id, channel)
                        await ws_manager.send_to_client(client_id, "unsubscribed", {
                            "channel": channel
                        })

                elif action == "ping":
                    await ws_manager.send_to_client(client_id, "pong", {
                        "timestamp": datetime.now().isoformat()
                    })

            except json.JSONDecodeError:
                await ws_manager.send_to_client(client_id, "error", {
                    "message": "无效的 JSON 格式"
                })

    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
        logger.info(f"客户端 {client_id} 断开连接")


@router.get("/ws/status")
async def websocket_status():
    """获取 WebSocket 连接状态"""
    return {
        "total_connections": ws_manager.get_connection_count(),
        "channels": {
            Channels.MARKET_TICKER: ws_manager.get_channel_subscribers(Channels.MARKET_TICKER),
            Channels.SIGNAL_CREATED: ws_manager.get_channel_subscribers(Channels.SIGNAL_CREATED),
            Channels.SIGNAL_UPDATED: ws_manager.get_channel_subscribers(Channels.SIGNAL_UPDATED),
            Channels.TRADE_EXECUTED: ws_manager.get_channel_subscribers(Channels.TRADE_EXECUTED),
            Channels.POSITION_CHANGED: ws_manager.get_channel_subscribers(Channels.POSITION_CHANGED),
            Channels.NOTIFICATION: ws_manager.get_channel_subscribers(Channels.NOTIFICATION),
        }
    }
