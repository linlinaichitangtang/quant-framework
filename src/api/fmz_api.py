"""
OpenClaw ↔ FMZ (发明者量化) API接口定义
JSON格式数据交互规范
"""

from enum import Enum
from typing import Dict, List, Optional, Union, Any
import json
from dataclasses import dataclass, asdict


class ActionType(Enum):
    """交易动作类型"""
    BUY = "buy"
    SELL = "sell"
    CANCEL = "cancel"
    QUERY_POSITION = "query_position"
    QUERY_CAPITAL = "query_capital"
    CLOSE_ALL = "close_all"


class MarketType(Enum):
    """市场类型"""
    CN = "CN"    # A股
    HK = "HK"    # 港股
    US = "US"    # 美股


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"    # 市价单
    LIMIT = "limit"      # 限价单


class ResponseStatus(Enum):
    """响应状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class TradingSignal:
    """OpenClaw → FMZ 交易信号"""
    strategy: str          # 策略名称：a股隔夜/美股事件驱动等
    action: ActionType     # 交易动作
    symbol: str            # 标的代码
    market: MarketType     # 市场
    price: Optional[float] = None       # 下单价格，市价单可为空
    quantity: Optional[int] = None      # 下单数量
    order_type: OrderType = OrderType.MARKET  # 订单类型
    stop_loss: Optional[float] = None    # 止损价
    take_profit: Optional[float] = None  # 止盈价
    expire_time: Optional[str] = None    # 订单失效时间 (ISO格式)
    remark: Optional[str] = None         # 备注信息
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        data = asdict(self)
        # 转换枚举为字符串
        data['action'] = self.action.value
        data['market'] = self.market.value
        data['order_type'] = self.order_type.value
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TradingSignal':
        """从JSON解析"""
        data = json.loads(json_str)
        return cls(
            strategy=data['strategy'],
            action=ActionType(data['action']),
            symbol=data['symbol'],
            market=MarketType(data['market']),
            price=data.get('price'),
            quantity=data.get('quantity'),
            order_type=OrderType(data.get('order_type', 'market')),
            stop_loss=data.get('stop_loss'),
            take_profit=data.get('take_profit'),
            expire_time=data.get('expire_time'),
            remark=data.get('remark')
        )


@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str
    market: MarketType
    quantity: int
    cost_price: float       # 成本价
    current_price: float
    profit_pct: float       # 盈亏百分比
    profit_amount: float    # 盈亏金额
    is_today_open: bool     # 是否今日开仓
    sector: Optional[str] = None
    option_info: Optional[Dict] = None  # 期权额外信息
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['market'] = self.market.value
        return data


@dataclass
class FMZExecutionResult:
    """FMZ → OpenClaw 执行结果"""
    request_id: str         # 请求ID
    status: ResponseStatus  # 执行状态
    message: str            # 执行信息
    order_id: Optional[str] = None       # FMZ订单ID
    filled_quantity: Optional[int] = None  # 成交数量
    filled_price: Optional[float] = None    # 成交均价
    positions: Optional[List[PositionInfo]] = None  # 当前持仓列表
    capital: Optional[Dict] = None  # 资金信息 {total: available: ...}
    
    def to_json(self) -> str:
        data = asdict(self)
        data['status'] = self.status.value
        if self.positions:
            data['positions'] = [p.to_dict() for p in self.positions]
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'FMZExecutionResult':
        data = json.loads(json_str)
        positions = None
        if data.get('positions'):
            positions = [
                PositionInfo(
                    symbol=p['symbol'],
                    market=MarketType(p['market']),
                    quantity=p['quantity'],
                    cost_price=p['cost_price'],
                    current_price=p['current_price'],
                    profit_pct=p['profit_pct'],
                    profit_amount=p['profit_amount'],
                    is_today_open=p['is_today_open'],
                    sector=p.get('sector'),
                    option_info=p.get('option_info')
                ) for p in data['positions']
            ]
        return cls(
            request_id=data['request_id'],
            status=ResponseStatus(data['status']),
            message=data['message'],
            order_id=data.get('order_id'),
            filled_quantity=data.get('filled_quantity'),
            filled_price=data.get('filled_price'),
            positions=positions,
            capital=data.get('capital')
        )


@dataclass
class MarketDataRequest:
    """OpenClaw → FMZ 行情数据请求"""
    symbols: List[str]
    market: MarketType
    timeframe: str = "1d"  # 1d, 1h, 5m
    include_latest: bool = True
    
    def to_json(self) -> str:
        data = asdict(self)
        data['market'] = self.market.value
        return json.dumps(data, indent=2, ensure_ascii=False)


@dataclass
class MarketDataResponse:
    """FMZ → OpenClaw 行情数据响应"""
    status: ResponseStatus
    data: Dict[str, List[Dict]]  # symbol -> k线数据
    message: Optional[str] = None
    
    def to_json(self) -> str:
        data = asdict(self)
        data['status'] = self.status.value
        return json.dumps(data, indent=2, ensure_ascii=False)


class FMZClient:
    """FMZ API客户端，用于发送请求和接收响应"""
    
    def __init__(self, endpoint: Optional[str] = None):
        """
        初始化客户端
        :param endpoint: FMZ API端点地址
        """
        self.endpoint = endpoint
    
    def create_trading_signal(self, 
                             strategy: str,
                             action: str,
                             symbol: str,
                             market: str,
                             price: Optional[float] = None,
                             quantity: Optional[int] = None,
                             order_type: str = "market",
                             stop_loss: Optional[float] = None,
                             take_profit: Optional[float] = None,
                             expire_time: Optional[str] = None,
                             remark: Optional[str] = None) -> TradingSignal:
        """
        创建交易信号
        """
        return TradingSignal(
            strategy=strategy,
            action=ActionType(action),
            symbol=symbol,
            market=MarketType(market),
            price=price,
            quantity=quantity,
            order_type=OrderType(order_type),
            stop_loss=stop_loss,
            take_profit=take_profit,
            expire_time=expire_time,
            remark=remark
        )
    
    def create_success_response(self, request_id: str, message: str = "执行成功", 
                               order_id: str = None, filled_quantity: int = None, 
                               filled_price: float = None) -> FMZExecutionResult:
        """创建成功响应"""
        return FMZExecutionResult(
            request_id=request_id,
            status=ResponseStatus.SUCCESS,
            message=message,
            order_id=order_id,
            filled_quantity=filled_quantity,
            filled_price=filled_price
        )
    
    def create_error_response(self, request_id: str, message: str) -> FMZExecutionResult:
        """创建错误响应"""
        return FMZExecutionResult(
            request_id=request_id,
            status=ResponseStatus.FAILED,
            message=message
        )
