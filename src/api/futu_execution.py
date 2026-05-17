"""
富途实盘执行模块
替换 FMZ(发明者量化)，通过富途 OpenD 进行真实/模拟盘交易

支持：
- 实盘 REAL / 模拟盘 SIMULATE 自动切换
- A股(沪/深) / 港股 / 美股
- 市价单 / 限价单
- 止损止盈单
- 持仓查询 / 资金查询 / 订单查询
"""

import uuid
import time
import signal
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd

from src.utils.logging import logger


# ─── 数据结构 ──────────────────────────────────────────────────

class MarketType(Enum):
    CN = "CN"   # A股
    HK = "HK"   # 港股
    US = "US"   # 美股


class ActionType(Enum):
    BUY = "buy"
    SELL = "sell"
    CANCEL = "cancel"


class OrderType(Enum):
    MARKET = "market"   # 市价单
    LIMIT = "limit"      # 限价单


class TrdEnvType(Enum):
    REAL = "REAL"    # 实盘
    SIMULATE = "SIMULATE"  # 模拟盘


@dataclass
class PositionInfo:
    """持仓信息"""
    symbol: str           # 内部格式代码
    quantity: int        # 持有数量
    cost_price: float    # 成本价
    current_price: float # 当前价
    profit_pct: float   # 盈亏%
    market: str          # 市场


@dataclass
class ExecutionResult:
    """执行结果"""
    request_id: str
    status: str           # "success" / "failed" / "partial"
    message: str
    order_id: Optional[str] = None
    filled_quantity: Optional[int] = None
    filled_price: Optional[float] = None
    positions: Optional[List[PositionInfo]] = None
    capital: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "message": self.message,
            "order_id": self.order_id,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "positions": [p.__dict__ for p in (self.positions or [])],
            "capital": self.capital,
        }


# ─── 富途执行器 ───────────────────────────────────────────────

class FutuExecutionProvider:
    """
    富途交易执行器

    通过富途 OpenD 执行交易：
    - 交易信号接收 → 富途下单
    - 持仓同步 / 资金同步
    - 实盘/模拟盘自动切换
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 11111,
        acc_id: Optional[int] = None,
        trd_env: str = "SIMULATE",
    ):
        self.host = host
        self.port = port
        self._acc_id = acc_id
        self._trd_env = TrdEnvType(trd_env)
        self._quote_ctx = None
        self._trade_ctx = None
        self._connected = False

    # ─── 连接管理 ──────────────────────────────────────────────

    def connect(self):
        """建立行情+交易双重连接"""
        from futu import OpenQuoteContext, OpenSecTradeContext

        if self._connected:
            return

        self._quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
        self._trade_ctx = OpenSecTradeContext(
            host=self.host,
            port=self.port,
            is_encrypt=False,
        )
        self._connected = True
        logger.info(f"[FutuExecution] 连接成功 {self.host}:{self.port} | 环境={self._trd_env.value}")

    def close(self):
        """关闭所有连接"""
        if self._quote_ctx:
            self._quote_ctx.close()
            self._quote_ctx = None
        if self._trade_ctx:
            self._trade_ctx.close()
            self._trade_ctx = None
        self._connected = False
        logger.info("[FutuExecution] 连接已关闭")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    # ─── 代码转换 ──────────────────────────────────────────────

    @staticmethod
    def _to_futu_code(code: str) -> str:
        """
        内部格式 → 富途格式
        CN.600000 → SH.600000
        HK.00700 → HK.00700
        US.QQQ → US.QQQ
        """
        if "." in code:
            market, symbol = code.split(".", 1)
            if market == "CN":
                if symbol.startswith(("0", "3")):
                    return f"SZ.{symbol}"
                return f"SH.{symbol}"
            return f"{market}.{symbol}"
        return code

    @staticmethod
    def _from_futu_code(code: str) -> str:
        """富途格式 → 内部格式"""
        if "." in code:
            market, symbol = code.split(".", 1)
            m = {"SH": "CN", "SZ": "CN", "HK": "HK", "US": "US"}.get(market, market)
            return f"{m}.{symbol}"
        return code

    @staticmethod
    def _to_futu_market(market: str) -> 'futu.TrdMarket':
        """内部市场 → 富途市场枚举"""
        import futu as ft
        return {
            "A": ft.TrdMarket.CN,
            "CN": ft.TrdMarket.CN,
            "HK": ft.TrdMarket.HK,
            "US": ft.TrdMarket.US,
        }.get(market, ft.TrdMarket.HK)

    @staticmethod
    def _to_futu_trd_side(action: str) -> 'futu.TrdSide':
        """动作 → 富途买卖方向"""
        import futu as ft
        return {
            "buy": ft.TrdSide.BUY,
            "sell": ft.TrdSide.SELL,
        }.get(action, ft.TrdSide.BUY)

    # ─── 核心交易接口 ──────────────────────────────────────────

    def set_account(self, acc_id: int, trd_env: str = "SIMULATE"):
        """切换交易账户"""
        self._acc_id = acc_id
        self._trd_env = TrdEnvType(trd_env)
        logger.info(f"[FutuExecution] 账户切换: acc_id={acc_id}, trd_env={trd_env}")

    def buy(
        self,
        symbol: str,
        price: float,
        quantity: int,
        order_type: str = "market",
        market: str = "HK",
    ) -> ExecutionResult:
        """买入开仓"""
        return self._place_order(
            action="buy",
            symbol=symbol,
            price=price,
            quantity=quantity,
            order_type=order_type,
            market=market,
        )

    def sell(
        self,
        symbol: str,
        price: float,
        quantity: int,
        order_type: str = "market",
        market: str = "HK",
    ) -> ExecutionResult:
        """卖出平仓"""
        return self._place_order(
            action="sell",
            symbol=symbol,
            price=price,
            quantity=quantity,
            order_type=order_type,
            market=market,
        )

    def _place_order(
        self,
        action: str,
        symbol: str,
        price: float,
        quantity: int,
        order_type: str = "market",
        market: str = "HK",
    ) -> ExecutionResult:
        """通用下单接口"""
        self.connect()

        import futu as ft

        request_id = str(uuid.uuid4())[:8]
        futu_code = self._to_futu_code(symbol)
        futu_market = self._to_futu_market(market)
        trd_side = self._to_futu_trd_side(action)

        # 确定下单价格
        if order_type == "market":
            # 市价单：价格传0
            price_for_order = 0.0
        else:
            price_for_order = price

        # 获取账户ID
        acc_id = self._acc_id
        if acc_id is None:
            # 自动获取第一个匹配账户
            ret, acc_list = self._trade_ctx.get_acc_list()
            if ret == 0 and not acc_list.empty:
                for _, acc in acc_list.iterrows():
                    if acc['trd_env'] == self._trd_env.value:
                        acc_id = acc['acc_id']
                        break
                if acc_id is None:
                    acc_id = acc_list.iloc[0]['acc_id']

        try:
            if order_type == "market":
                ret, data = self._trade_ctx.place_order(
                    code=futu_code,
                    price=price_for_order,
                    qty=quantity,
                    trd_side=trd_side,
                    market=futu_market,
                    order_type=ft.OrderType.MARKET,
                    acc_id=acc_id,
                    trd_env=self._get_trd_env(),
                )
            else:
                ret, data = self._trade_ctx.place_order(
                    code=futu_code,
                    price=price_for_order,
                    qty=quantity,
                    trd_side=trd_side,
                    market=futu_market,
                    order_type=ft.OrderType.NORMAL,
                    acc_id=acc_id,
                    trd_env=self._get_trd_env(),
                )

            if ret == 0:
                order_id = str(data.get("order_id", ""))
                logger.info(f"[FutuExecution] {'买入' if action=='buy' else '卖出'}成功 {symbol} x{quantity} @ {price} | order_id={order_id}")
                return ExecutionResult(
                    request_id=request_id,
                    status="success",
                    message=f"{'买入' if action=='buy' else '卖出'}成功",
                    order_id=order_id,
                    filled_quantity=quantity,
                    filled_price=price,
                )
            else:
                logger.error(f"[FutuExecution] 下单失败 {data}")
                return ExecutionResult(
                    request_id=request_id,
                    status="failed",
                    message=f"下单失败: {data}",
                )
        except Exception as e:
            logger.error(f"[FutuExecution] 下单异常 {e}")
            return ExecutionResult(
                request_id=request_id,
                status="failed",
                message=f"下单异常: {e}",
            )

    def _get_trd_env(self):
        """获取富途 TrdEnv 枚举"""
        import futu as ft
        return ft.TrdEnv.SIMULATE if self._trd_env == TrdEnvType.SIMULATE else ft.TrdEnv.REAL

    # ─── 持仓 & 资金查询 ──────────────────────────────────────

    def get_positions(self, market: Optional[str] = None) -> List[PositionInfo]:
        """
        获取当前持仓

        Args:
            market: 可选筛选市场 "CN" / "HK" / "US"
        """
        self.connect()

        acc_id = self._acc_id
        if acc_id is None:
            ret, acc_list = self._trade_ctx.get_acc_list()
            if ret == 0 and not acc_list.empty:
                acc_id = acc_list.iloc[0]['acc_id']

        try:
            ret, data = self._trade_ctx.position_list_query(
                acc_id=acc_id,
                trd_env=self._get_trd_env(),
            )

            if ret != 0 or data.empty:
                return []

            positions = []
            for _, row in data.iterrows():
                sym = self._from_futu_code(row.get("code", ""))
                if market and not sym.startswith(market):
                    continue

                positions.append(PositionInfo(
                    symbol=sym,
                    quantity=int(row.get("qty", 0)),
                    cost_price=float(row.get("cost_price", 0)),
                    current_price=float(row.get("last_price", 0)),
                    profit_pct=float(row.get("pl_ratio", 0)),
                    market=row.get("market", ""),
                ))

            return positions

        except Exception as e:
            logger.error(f"[FutuExecution] 持仓查询失败: {e}")
            return []

    def get_capital(self) -> Dict:
        """获取账户资金"""
        self.connect()

        acc_id = self._acc_id
        if acc_id is None:
            ret, acc_list = self._trade_ctx.get_acc_list()
            if ret == 0 and not acc_list.empty:
                acc_id = acc_list.iloc[0]['acc_id']

        try:
            ret, data = self._trade_ctx.accinfo_query(
                acc_id=acc_id,
                trd_env=self._get_trd_env(),
            )

            if ret != 0 or data.empty:
                return {}

            row = data.iloc[0]
            return {
                "total": float(row.get("total_assets", 0)),
                "available": float(row.get("cash", 0)),
                "market_value": float(row.get("market_val", 0)),
            }
        except Exception as e:
            logger.error(f"[FutuExecution] 资金查询失败: {e}")
            return {}

    def get_positions_and_capital(self) -> Tuple[List[PositionInfo], Dict]:
        """同时获取持仓和资金（一次连接，更高效）"""
        return self.get_positions(), self.get_capital()

    # ─── 订单管理 ──────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> ExecutionResult:
        """撤单"""
        self.connect()
        request_id = str(uuid.uuid4())[:8]

        try:
            ret, data = self._trade_ctx.cancel_order(order_id=order_id)
            if ret == 0:
                return ExecutionResult(
                    request_id=request_id,
                    status="success",
                    message="撤单成功",
                    order_id=order_id,
                )
            else:
                return ExecutionResult(
                    request_id=request_id,
                    status="failed",
                    message=f"撤单失败: {data}",
                )
        except Exception as e:
            return ExecutionResult(
                request_id=request_id,
                status="failed",
                message=f"撤单异常: {e}",
            )

    def get_order_list(self, status: str = "all") -> List[Dict]:
        """查询订单列表"""
        self.connect()

        acc_id = self._acc_id
        if acc_id is None:
            ret, acc_list = self._trade_ctx.get_acc_list()
            if ret == 0 and not acc_list.empty:
                acc_id = acc_list.iloc[0]['acc_id']

        try:
            ret, data = self._trade_ctx.history_order_list_query(
                acc_id=acc_id,
                trd_env=self._get_trd_env(),
            )
            if ret == 0:
                return data.to_dict("records")
            return []
        except Exception as e:
            logger.error(f"[FutuExecution] 订单查询失败: {e}")
            return []

    # ─── 统一信号入口（兼容原 FMZClient 调度方式）─────────────

    def execute_signal(self, signal_dict: Dict) -> ExecutionResult:
        """
        执行来自 OpenClaw 的交易信号

        signal_dict 格式（与原 TradingSignal.to_dict() 兼容）:
        {
            "action": "buy" | "sell",
            "symbol": "CN.600000",
            "price": 10.5,        # 市价单填0
            "quantity": 100,
            "market": "CN",
            "order_type": "market" | "limit",
        }
        """
        action = signal_dict.get("action", "buy")
        symbol = signal_dict.get("symbol")
        price = float(signal_dict.get("price", 0))
        quantity = int(signal_dict.get("quantity", 0))
        market = signal_dict.get("market", "HK")
        order_type = signal_dict.get("order_type", "market")

        if action == "cancel":
            return self.cancel_order(signal_dict.get("order_id", ""))

        return self._place_order(
            action=action,
            symbol=symbol,
            price=price,
            quantity=quantity,
            order_type=order_type,
            market=market,
        )


if __name__ == "__main__":
    # 测试
    with FutuExecutionProvider() as executor:
        # 先查持仓
        positions = executor.get_positions()
        print(f"当前持仓: {len(positions)} 只")
        for p in positions:
            print(f"  {p.symbol} x {p.quantity} @ {p.cost_price} (浮盈 {p.profit_pct:.2f}%)")

        # 查资金
        capital = executor.get_capital()
        print(f"\n资金: {capital}")

        # 获取账户列表
        print("\n--- 账户列表 ---")
        executor.connect()
        ret, acc_list = executor._trade_ctx.get_acc_list()
        if ret == 0:
            print(acc_list[['acc_id', 'trd_env', 'acc_type']].to_string())
