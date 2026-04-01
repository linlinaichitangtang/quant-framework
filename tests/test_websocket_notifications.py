"""
WebSocket 和通知模块单元测试
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.websocket import (
    ConnectionManager,
    Channels,
    ws_manager,
    broadcast_signal_created,
    broadcast_notification,
)
from app.notifications import (
    Notification,
    NotificationService,
    WechatNotifier,
    DingtalkNotifier,
    render_template,
    TEMPLATES,
)


class TestConnectionManager:
    """WebSocket 连接管理器测试"""

    @pytest.mark.asyncio
    async def test_connect(self):
        """测试连接"""
        ws = AsyncMock()
        ws_manager._connections.clear()
        ws_manager._channels.clear()
        ws_manager._client_channels.clear()

        client_id = await ws_manager.connect(ws, "test_client")
        assert client_id == "test_client"
        assert ws_manager.get_connection_count() == 1

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """测试断开连接"""
        ws = AsyncMock()
        ws_manager._connections.clear()
        ws_manager._channels.clear()
        ws_manager._client_channels.clear()

        await ws_manager.connect(ws, "test_client")
        await ws_manager.subscribe("test_client", "test_channel")
        await ws_manager.disconnect("test_client")
        assert ws_manager.get_connection_count() == 0
        assert ws_manager.get_channel_subscribers("test_channel") == 0

    @pytest.mark.asyncio
    async def test_subscribe(self):
        """测试订阅"""
        ws = AsyncMock()
        ws_manager._connections.clear()
        ws_manager._channels.clear()
        ws_manager._client_channels.clear()

        await ws_manager.connect(ws, "c1")
        await ws_manager.connect(ws, "c2")
        await ws_manager.subscribe("c1", "ch1")
        await ws_manager.subscribe("c2", "ch1")
        assert ws_manager.get_channel_subscribers("ch1") == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """测试取消订阅"""
        ws = AsyncMock()
        ws_manager._connections.clear()
        ws_manager._channels.clear()
        ws_manager._client_channels.clear()

        await ws_manager.connect(ws, "c1")
        await ws_manager.subscribe("c1", "ch1")
        await ws_manager.unsubscribe("c1", "ch1")
        assert ws_manager.get_channel_subscribers("ch1") == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """测试广播"""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws_manager._connections.clear()
        ws_manager._channels.clear()
        ws_manager._client_channels.clear()

        await ws_manager.connect(ws1, "c1")
        await ws_manager.connect(ws2, "c2")
        await ws_manager.subscribe("c1", "ch1")
        await ws_manager.subscribe("c2", "ch1")

        await ws_manager.broadcast("ch1", "test_event", {"key": "value"})

        # 两个客户端都应收到消息
        assert ws1.send_text.call_count == 1
        assert ws2.send_text.call_count == 1

        # 验证消息格式
        msg = json.loads(ws1.send_text.call_args[0][0])
        assert msg["channel"] == "ch1"
        assert msg["event"] == "test_event"
        assert msg["data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_broadcast_no_subscribers(self):
        """无订阅者时广播不报错"""
        ws_manager._channels.clear()
        await ws_manager.broadcast("nonexistent", "test", {})

    @pytest.mark.asyncio
    async def test_send_to_client(self):
        """测试点对点发送"""
        ws = AsyncMock()
        ws_manager._connections.clear()
        ws_manager._channels.clear()
        ws_manager._client_channels.clear()

        await ws_manager.connect(ws, "c1")
        await ws_manager.send_to_client("c1", "direct_msg", {"hello": "world"})

        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["event"] == "direct_msg"
        assert msg["data"] == {"hello": "world"}

    @pytest.mark.asyncio
    async def test_broadcast_disconnects_failed(self):
        """广播时自动清理断开的连接"""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.send_text.side_effect = Exception("Connection lost")

        ws_manager._connections.clear()
        ws_manager._channels.clear()
        ws_manager._client_channels.clear()

        await ws_manager.connect(ws1, "c1")
        await ws_manager.connect(ws2, "c2")
        await ws_manager.subscribe("c1", "ch")
        await ws_manager.subscribe("c2", "ch")

        await ws_manager.broadcast("ch", "test", {})
        # c2 应该被清理
        assert ws_manager.get_connection_count() == 1


class TestChannels:
    """频道常量测试"""

    def test_channels_defined(self):
        """所有预定义频道存在"""
        assert Channels.MARKET_TICKER == "market:ticker"
        assert Channels.SIGNAL_CREATED == "signal:created"
        assert Channels.TRADE_EXECUTED == "trade:executed"
        assert Channels.POSITION_CHANGED == "position:changed"
        assert Channels.NOTIFICATION == "notification"
        assert Channels.SYSTEM_ALERT == "system:alert"


class TestNotificationTemplate:
    """通知模板测试"""

    def test_render_signal_created(self):
        """渲染信号创建模板"""
        result = render_template("signal_created",
            symbol="000001", side="买入", strategy="尾盘策略",
            market="A", price="15.5", stop_loss="15.0",
            take_profit="16.5", reason="放量突破"
        )
        assert "000001" in result["title"]
        assert "买入" in result["title"]
        assert "尾盘策略" in result["content"]

    def test_render_stop_loss(self):
        """渲染止损模板"""
        result = render_template("stop_loss_triggered",
            symbol="000001", stop_loss="15.0",
            current_price="14.5", loss_pct="3.33"
        )
        assert "止损" in result["title"]

    def test_render_unknown_template(self):
        """未知模板返回原始数据"""
        result = render_template("unknown_template", key="value")
        assert result["title"] == "unknown_template"

    def test_all_templates_render(self):
        """所有模板都能正确渲染"""
        params = {
            "symbol": "000001", "side": "BUY", "market": "A",
            "strategy": "test", "price": "10.0", "stop_loss": "9.5",
            "take_profit": "11.0", "quantity": "100", "reason": "test",
            "signal_id": "1", "alert_type": "test", "message": "test msg",
            "time": "2026-01-01", "level": "warning",
            "amount": "1000", "avg_cost": "10.0", "current_price": "10.5",
            "profit_pct": "5.0", "loss_pct": "2.0",
        }
        for name in TEMPLATES:
            result = render_template(name, **params)
            assert "title" in result
            assert "content" in result


class TestNotification:
    """通知对象测试"""

    def test_to_dict(self):
        """通知转字典"""
        notif = Notification(
            title="测试",
            content="内容",
            channel="signal",
            level="info",
            data={"key": "value"},
            recipients=["user1"]
        )
        d = notif.to_dict()
        assert d["title"] == "测试"
        assert d["channel"] == "signal"
        assert d["data"] == {"key": "value"}
        assert "timestamp" in d


class TestNotificationService:
    """通知服务测试"""

    def test_init_empty(self):
        """无配置时初始化"""
        service = NotificationService()
        assert len(service._notifiers) == 0

    def test_add_notifier(self):
        """添加自定义通知渠道"""
        service = NotificationService()
        mock_notifier = AsyncMock()
        service.add_notifier("custom", mock_notifier)
        assert "custom" in service._notifiers

    @pytest.mark.asyncio
    async def test_send_no_channels(self):
        """无渠道时只走 WebSocket"""
        service = NotificationService()
        notif = Notification(title="test", content="test", channel="test")
        with patch('app.notifications.broadcast_notification', new_callable=AsyncMock):
            results = await service.send(notif)
        assert results["websocket"] is True

    @pytest.mark.asyncio
    async def test_send_specific_channels(self):
        """指定渠道发送"""
        service = NotificationService()
        mock_notifier = MagicMock()
        mock_notifier.send = AsyncMock(return_value=True)
        service.add_notifier("test_ch", mock_notifier)

        notif = Notification(title="test", content="test", channel="test")
        with patch('app.notifications.broadcast_notification', new_callable=AsyncMock):
            results = await service.send(notif, channels=["test_ch"])
        assert results["test_ch"] is True
        mock_notifier.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_from_template(self):
        """从模板发送"""
        service = NotificationService()
        with patch('app.notifications.broadcast_notification', new_callable=AsyncMock):
            results = await service.send_from_template(
                "signal_created",
                channel="signal",
                symbol="000001",
                side="买入",
                strategy="test",
                market="A",
                price="10",
                stop_loss="9",
                take_profit="11",
                reason="test"
            )
        assert results["websocket"] is True


class TestWechatNotifier:
    """企业微信通知测试"""

    @pytest.mark.asyncio
    async def test_send_no_webhook(self):
        """无 Webhook 配置"""
        notifier = WechatNotifier(webhook_url=None)
        result = await notifier.send(Notification(title="test", content="test", channel="test"))
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        """发送成功"""
        notifier = WechatNotifier(webhook_url="https://example.com/webhook")

        # aiohttp: session.post() 返回 async context manager, resp.json() 是协程
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"errcode": 0})

        # session.post() 返回的 async context manager
        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_instance = AsyncMock()
        # post() 必须是普通 MagicMock，因为 async with session.post(...) as resp:
        # 中 post() 同步返回 async context manager，不是协程
        mock_session_instance.post = MagicMock(return_value=mock_post_cm)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=False)

        with patch('aiohttp.ClientSession', return_value=mock_session_instance):
            result = await notifier.send(Notification(title="test", content="test", channel="test"))
        assert result is True
