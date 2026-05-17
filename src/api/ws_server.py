"""
OpenClaw API服务端

接收富途OpenD推送的tick和成交信息，处理后分发到各个模块
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from loguru import logger

from src.data_types import TickData, Trade, MarketEvent
from src.monitor.base import BaseMonitor

from .schemas import WebsocketMessage, TickPush, TradePush

app = FastAPI(title="OpenClaw-Futu API", version="0.1.0")


class WebsocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.monitors: List[BaseMonitor] = []

    def register_monitor(self, monitor: BaseMonitor):
        """注册监控器"""
        self.monitors.append(monitor)

    async def connect(self, websocket: WebSocket):
        """新连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"新WebSocket连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开连接"""
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket断开，当前连接数: {len(self.active_connections)}")

    def _convert_tick(self, data: TickPush) -> TickData:
        """转换为TickData"""
        return TickData(
            symbol=data.symbol,
            price=data.price,
            volume=data.volume,
            timestamp=data.timestamp,
            open=data.open,
            high=data.high,
            low=data.low,
        )

    def _convert_trade(self, data: TradePush) -> Trade:
        """转换为Trade"""
        return Trade(
            symbol=data.symbol,
            side=data.side,
            volume=data.volume,
            price=data.price,
            timestamp=data.timestamp,
            trade_id=data.trade_id,
            order_id=data.order_id,
        )

    async def broadcast_message(self, message: WebsocketMessage):
        """广播消息给所有连接"""
        for connection in self.active_connections:
            await connection.send_json(message.model_dump())

    async def process_message(self, raw_data: dict):
        """处理接收到的消息"""
        try:
            msg = WebsocketMessage(**raw_data)

            if msg.msg_type == "tick":
                tick_data = TickPush(**msg.data)
                tick = self._convert_tick(tick_data)
                # 分发到所有监控器
                for monitor in self.monitors:
                    monitor.on_tick(tick)

            elif msg.msg_type == "trade":
                # 成交推送，可以记录到本地
                trade_data = TradePush(**msg.data)
                trade = self._convert_trade(trade_data)
                logger.info(f"收到成交推送: {trade.side} {trade.symbol} {trade.volume} @ {trade.price}")
                # TODO: 存储成交记录
                event = MarketEvent(
                    event_type="trade_executed",
                    symbol=trade.symbol,
                    timestamp=trade.timestamp,
                    data=trade.__dict__,
                    message=f"成交: {trade.side} {trade.symbol} {trade.volume} @ {trade.price}",
                )
                for monitor in self.monitors:
                    monitor.on_event(event)

        except Exception as e:
            logger.error(f"处理WebSocket消息失败: {e}", exc_info=True)


manager = WebsocketManager()


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点，接收富途OpenD推送"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.process_message(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket错误: {e}", exc_info=True)
        manager.disconnect(websocket)
