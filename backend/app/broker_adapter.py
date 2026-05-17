"""
券商执行层适配器

提供统一的接口，支持多种券商（FMZ、富途、IB等）。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BrokerType(Enum):
    """券商类型"""
    FMZ = "fmz"           # 发明者量化
    FUTU = "futu"         # 富途证券
    IB = "ib"             # Interactive Brokers
    ALPACA = "alpaca"     # Alpaca
    UNKNOWN = "unknown"


@dataclass
class OrderRequest:
    """下单请求"""
    symbol: str           # 股票代码
    market: str           # 市场 (CN/HK/US)
    side: str             # buy/sell
    order_type: str       # market/limit
    quantity: int         # 数量
    price: Optional[float] = None  # 限价（market单不需要）
    stop_price: Optional[float] = None  # 止损价
    strategy_id: Optional[str] = None  # 策略ID
    remark: Optional[str] = None  # 备注


@dataclass
class OrderResponse:
    """下单响应"""
    success: bool
    order_id: Optional[str]
    message: str
    filled_quantity: int = 0
    filled_price: float = 0.0
    remaining_quantity: int = 0


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    market: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    profit_amount: float
    profit_pct: float


@dataclass
class AccountInfo:
    """账户信息"""
    broker: str
    account_id: str
    total_assets: float
    cash: float
    market_value: float
    buying_power: float
    positions: List[Position]


class BrokerAdapter(ABC):
    """
    券商适配器基类

    所有券商实现必须继承此类并实现抽象方法。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化适配器

        Args:
            config: 券商配置，包含 API Key、Secret 等
        """
        self.config = config
        self._connected = False

    @property
    @abstractmethod
    def broker_type(self) -> BrokerType:
        """返回券商类型"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """连接券商"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResponse:
        """下单"""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """查询订单状态"""
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """获取持仓"""
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """获取账户信息"""
        pass

    @abstractmethod
    def get_quote(self, symbol: str, market: str) -> Optional[Dict]:
        """获取实时行情"""
        pass


class BrokerAdapterManager:
    """
    券商适配器管理器

    统一管理所有券商适配器，支持动态切换。
    """

    _adapters: Dict[BrokerType, BrokerAdapter] = {}
    _active_broker: Optional[BrokerType] = None

    @classmethod
    def register(cls, broker_type: BrokerType, adapter: BrokerAdapter):
        """注册适配器"""
        cls._adapters[broker_type] = adapter
        logger.info(f"已注册券商适配器: {broker_type.value}")

    @classmethod
    def get_adapter(cls, broker_type: BrokerType) -> Optional[BrokerAdapter]:
        """获取适配器"""
        return cls._adapters.get(broker_type)

    @classmethod
    def set_active(cls, broker_type: BrokerType) -> bool:
        """设置活跃券商"""
        if broker_type not in cls._adapters:
            logger.error(f"券商 {broker_type.value} 未注册")
            return False

        adapter = cls._adapters[broker_type]
        if not adapter.is_connected():
            if not adapter.connect():
                logger.error(f"连接券商 {broker_type.value} 失败")
                return False

        cls._active_broker = broker_type
        logger.info(f"已切换到券商: {broker_type.value}")
        return True

    @classmethod
    def get_active_adapter(cls) -> Optional[BrokerAdapter]:
        """获取当前活跃的适配器"""
        if cls._active_broker:
            return cls._adapters.get(cls._active_broker)
        return None

    @classmethod
    def list_registered(cls) -> List[str]:
        """列出已注册的券商"""
        return [bt.value for bt in cls._adapters.keys()]

    @classmethod
    def get_active_broker(cls) -> Optional[str]:
        """获取当前活跃的券商类型"""
        return cls._active_broker.value if cls._active_broker else None


# ========== 交互券商(IB) 适配器示例 ==========

class IBAdapter(BrokerAdapter):
    """
    Interactive Brokers 适配器

    Note: 需要安装 ib_insync 库
    """

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.IB

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None
        # IB 配置
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 7497)  # 7497=模拟盘, 7496=实盘
        self.client_id = config.get("client_id", 1)

    def connect(self) -> bool:
        try:
            # 注意: 实际需要 ib_insync 库
            # from ib_insync import IB
            # self._client = IB()
            # self._client.connect(self.host, self.port, self.client_id)
            logger.warning("IB 适配器需要 ib_insync 库: pip install ib_insync")
            self._connected = True  # 模拟
            return True
        except Exception as e:
            logger.error(f"IB 连接失败: {e}")
            return False

    def disconnect(self):
        if self._client:
            self._client.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def place_order(self, order: OrderRequest) -> OrderResponse:
        if not self._connected:
            return OrderResponse(
                success=False,
                order_id=None,
                message="未连接券商"
            )

        # TODO: 实现 IB 下单
        # contract = Stock(order.symbol, order.market, "SMART")
        # trade = self._client.placeOrder(contract, order)
        return OrderResponse(
            success=True,
            order_id=f"IB-{order.symbol}-{id(order)}",
            message="模拟下单成功"
        )

    def cancel_order(self, order_id: str) -> bool:
        if self._client:
            for order in self._client.openOrders():
                if order.orderId == int(order_id):
                    self._client.cancelOrder(order)
                    return True
        return False

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        # TODO: 实现订单状态查询
        return {"status": "filled", "order_id": order_id}

    def get_positions(self) -> List[Position]:
        # TODO: 实现持仓查询
        return []

    def get_account_info(self) -> AccountInfo:
        # TODO: 实现账户信息查询
        return AccountInfo(
            broker="IB",
            account_id="模拟账户",
            total_assets=1000000.0,
            cash=500000.0,
            market_value=500000.0,
            buying_power=1000000.0,
            positions=[]
        )

    def get_quote(self, symbol: str, market: str) -> Optional[Dict]:
        # TODO: 实现行情查询
        return {"symbol": symbol, "last": 100.0}


# 注册 IB 适配器
BrokerAdapterManager.register(BrokerType.IB, IBAdapter({}))