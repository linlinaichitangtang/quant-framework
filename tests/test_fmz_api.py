"""
单元测试：FMZ API接口
测试数据序列化、反序列化是否正确
"""

import pytest
import json
from src.api.fmz_api import (
    TradingSignal,
    FMZExecutionResult,
    PositionInfo,
    MarketDataRequest,
    MarketDataResponse,
    FMZClient,
    ActionType,
    MarketType,
    OrderType,
    ResponseStatus,
)


class TestTradingSignal:
    """测试交易信号序列化/反序列化"""

    def test_create_buy_signal_a_stock(self):
        """创建A股买入信号"""
        signal = TradingSignal(
            strategy="a股隔夜",
            action=ActionType.BUY,
            symbol="000001",
            market=MarketType.CN,
            price=10.5,
            quantity=1000,
            order_type=OrderType.MARKET,
            stop_loss=10.3,
            take_profit=10.71,
            remark="测试买入"
        )
        assert signal.strategy == "a股隔夜"
        assert signal.action == ActionType.BUY
        assert signal.symbol == "000001"
        assert signal.market == MarketType.CN
        assert signal.price == 10.5
        assert signal.quantity == 1000

    def test_to_json(self):
        """测试转换为JSON"""
        signal = TradingSignal(
            strategy="a股隔夜",
            action=ActionType.BUY,
            symbol="000001",
            market=MarketType.CN,
            quantity=1000,
        )
        json_str = signal.to_json()
        data = json.loads(json_str)
        assert data['action'] == "buy"
        assert data['market'] == "CN"
        assert data['order_type'] == "market"
        assert data['symbol'] == "000001"

    def test_from_json(self):
        """测试从JSON解析"""
        json_str = """
        {
            "strategy": "美股事件驱动",
            "action": "buy",
            "symbol": "AAPL",
            "market": "US",
            "price": 175.5,
            "quantity": 10,
            "order_type": "limit",
            "stop_loss": 170,
            "take_profit": 190,
            "remark": "财报买入"
        }
        """
        signal = TradingSignal.from_json(json_str)
        assert signal.strategy == "美股事件驱动"
        assert signal.action == ActionType.BUY
        assert signal.symbol == "AAPL"
        assert signal.market == MarketType.US
        assert signal.price == 175.5
        assert signal.quantity == 10
        assert signal.order_type == OrderType.LIMIT
        assert signal.stop_loss == 170
        assert signal.take_profit == 190
        assert signal.remark == "财报买入"

    def test_json_roundtrip(self):
        """测试JSON序列化反序列化闭环"""
        signal = TradingSignal(
            strategy="港股期权",
            action=ActionType.BUY,
            symbol="TSLA",
            market=MarketType.US,
            price=250.0,
            quantity=5,
            order_type=OrderType.LIMIT,
            stop_loss=240.0,
            take_profit=280.0,
            expire_time="2024-01-01T16:00:00Z"
        )
        json_str = signal.to_json()
        signal2 = TradingSignal.from_json(json_str)
        assert signal.strategy == signal2.strategy
        assert signal.action == signal2.action
        assert signal.symbol == signal2.symbol
        assert signal.market == signal2.market
        assert signal.price == signal2.price
        assert signal.quantity == signal2.quantity


class TestFMZExecutionResult:
    """测试执行结果序列化反序列化"""

    def test_create_success_result(self):
        """创建成功执行结果"""
        result = FMZExecutionResult(
            request_id="req-12345",
            status=ResponseStatus.SUCCESS,
            message="买入成交",
            order_id="order-67890",
            filled_quantity=1000,
            filled_price=10.5
        )
        assert result.request_id == "req-12345"
        assert result.status == ResponseStatus.SUCCESS
        assert result.filled_quantity == 1000

    def test_to_json_with_positions(self):
        """测试带持仓信息的JSON序列化"""
        positions = [
            PositionInfo(
                symbol="000001",
                market=MarketType.CN,
                quantity=1000,
                cost_price=10.0,
                current_price=10.5,
                profit_pct=5.0,
                profit_amount=500,
                is_today_open=True,
                sector="银行"
            )
        ]
        result = FMZExecutionResult(
            request_id="req-123",
            status=ResponseStatus.SUCCESS,
            message="查询成功",
            positions=positions,
            capital={"total": 1000000, "available": 989500}
        )
        json_str = result.to_json()
        data = json.loads(json_str)
        assert data['status'] == "success"
        assert len(data['positions']) == 1
        assert data['positions'][0]['market'] == "CN"
        assert data['capital']['total'] == 1000000

    def test_from_json_with_positions(self):
        """测试带持仓信息的JSON解析"""
        json_str = """
        {
            "request_id": "req-123",
            "status": "success",
            "message": "查询成功",
            "positions": [
                {
                    "symbol": "000001",
                    "market": "CN",
                    "quantity": 1000,
                    "cost_price": 10.0,
                    "current_price": 10.5,
                    "profit_pct": 5.0,
                    "profit_amount": 500,
                    "is_today_open": true,
                    "sector": "银行"
                }
            ],
            "capital": {
                "total": 1000000,
                "available": 989500
            }
        }
        """
        result = FMZExecutionResult.from_json(json_str)
        assert result.request_id == "req-123"
        assert result.status == ResponseStatus.SUCCESS
        assert len(result.positions) == 1
        assert result.positions[0].symbol == "000001"
        assert result.positions[0].market == MarketType.CN
        assert result.positions[0].sector == "银行"
        assert result.capital['total'] == 1000000


class TestMarketData:
    """测试行情数据请求响应"""

    def test_market_data_request_to_json(self):
        """测试行情请求JSON"""
        req = MarketDataRequest(
            symbols=["000001", "000002"],
            market=MarketType.CN,
            timeframe="1d",
            include_latest=True
        )
        json_str = req.to_json()
        data = json.loads(json_str)
        assert data['market'] == "CN"
        assert len(data['symbols']) == 2

    def test_market_data_response_from_json(self):
        """测试行情响应JSON"""
        json_str = """
        {
            "status": "success",
            "message": "获取成功",
            "data": {
                "000001": [
                    {"date": "2024-01-01", "open": 10, "close": 10.5, "high": 10.6, "low": 9.9}
                ]
            }
        }
        """
        resp = json.loads(json_str)
        assert resp['status'] == "success"
        assert "000001" in resp['data']


class TestFMZClient:
    """测试FMZ API客户端"""

    def test_create_trading_signal(self):
        """测试创建交易信号"""
        client = FMZClient()
        signal = client.create_trading_signal(
            strategy="a股隔夜",
            action="buy",
            symbol="000001",
            market="CN",
            quantity=1000,
            price=10.5
        )
        assert signal.strategy == "a股隔夜"
        assert signal.action == ActionType.BUY
        assert signal.market == MarketType.CN

    def test_create_success_response(self):
        """测试创建成功响应"""
        client = FMZClient()
        resp = client.create_success_response("req-123", "买入成交", "order-456", 1000, 10.5)
        assert resp.request_id == "req-123"
        assert resp.status == ResponseStatus.SUCCESS
        assert resp.order_id == "order-456"
        assert resp.filled_quantity == 1000

    def test_create_error_response(self):
        """测试创建错误响应"""
        client = FMZClient()
        resp = client.create_error_response("req-123", "资金不足")
        assert resp.request_id == "req-123"
        assert resp.status == ResponseStatus.FAILED
        assert resp.message == "资金不足"
