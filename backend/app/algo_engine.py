"""
V1.9 算法交易引擎 — TWAP/VWAP/冰山/智能拆单
提供多种算法交易策略，支持大单拆分、智能执行
"""
import json
import uuid
import math
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AlgoOrder:
    """算法订单内部数据类"""

    def __init__(self, order_id: str, symbol: str, side: str, total_quantity: float,
                 algo_type: str, params: dict = None):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.total_quantity = total_quantity
        self.filled_quantity = 0.0
        self.avg_fill_price = 0.0
        self.status = "pending"  # pending/running/paused/completed/cancelled/failed
        self.algo_type = algo_type
        self.params = params or {}
        self.child_orders: List[Dict] = []
        self.created_at = datetime.now()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.market = self.params.get("market", "A")
        self.target_price = self.params.get("target_price")

    def to_dict(self) -> dict:
        """转换为字典"""
        progress = (self.filled_quantity / self.total_quantity * 100) if self.total_quantity > 0 else 0
        return {
            "order_id": self.order_id,
            "algo_type": self.algo_type,
            "status": self.status,
            "symbol": self.symbol,
            "market": self.market,
            "side": self.side,
            "total_quantity": self.total_quantity,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "target_price": self.target_price,
            "progress": round(progress, 2),
            "child_order_count": len(self.child_orders),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "created_at": self.created_at.isoformat(),
        }


class AlgoEngine:
    """算法交易引擎"""

    def __init__(self, db: Session):
        self.db = db
        self._active_orders: Dict[str, AlgoOrder] = {}

    def _generate_order_id(self, algo_type: str) -> str:
        """生成算法订单ID"""
        prefix_map = {
            "twap": "TW",
            "vwap": "VW",
            "iceberg": "IB",
            "smart": "SM",
        }
        prefix = prefix_map.get(algo_type, "AL")
        return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

    def _generate_child_order_id(self, parent_id: str, index: int) -> str:
        """生成子订单ID"""
        return f"{parent_id}_C{index:03d}"

    def _simulate_fill_price(self, symbol: str, side: str, quantity: float) -> float:
        """模拟成交价格（基于随机波动）"""
        # 模拟基础价格
        base_prices = {
            "600519": 1800.0,  # 贵州茅台
            "000001": 12.5,    # 平安银行
            "601318": 45.0,    # 中国平安
            "000858": 150.0,   # 五粮液
        }
        base = base_prices.get(symbol, 100.0)
        # 随机波动 ±0.5%
        change = random.uniform(-0.005, 0.005)
        # 买入略高，卖出略低（模拟滑点）
        slippage = 0.001 if side == "BUY" else -0.001
        return round(base * (1 + change + slippage), 2)

    def _save_order_to_db(self, order: AlgoOrder) -> bool:
        """保存订单到数据库"""
        try:
            from .models import AlgoOrder as AlgoOrderModel, AlgoOrderStatus, AlgoOrderType
            algo_type_map = {
                "twap": AlgoOrderType.TWAP,
                "vwap": AlgoOrderType.VWAP,
                "iceberg": AlgoOrderType.ICEBERG,
                "smart": AlgoOrderType.SMART,
            }
            status_map = {
                "pending": AlgoOrderStatus.PENDING,
                "running": AlgoOrderStatus.RUNNING,
                "paused": AlgoOrderStatus.PAUSED,
                "completed": AlgoOrderStatus.COMPLETED,
                "cancelled": AlgoOrderStatus.CANCELLED,
                "failed": AlgoOrderStatus.FAILED,
            }

            db_order = AlgoOrderModel(
                order_id=order.order_id,
                algo_type=algo_type_map.get(order.algo_type, AlgoOrderType.TWAP),
                status=status_map.get(order.status, AlgoOrderStatus.PENDING),
                symbol=order.symbol,
                market=order.market,
                side=order.side,
                total_quantity=order.total_quantity,
                filled_quantity=order.filled_quantity,
                avg_fill_price=order.avg_fill_price,
                target_price=order.target_price,
                params=json.dumps(order.params),
                child_orders=json.dumps(order.child_orders),
                start_time=order.start_time,
                end_time=order.end_time,
            )
            self.db.add(db_order)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"保存算法订单到数据库失败: {e}")
            self.db.rollback()
            return False

    def _update_order_in_db(self, order: AlgoOrder) -> bool:
        """更新数据库中的订单"""
        try:
            from .models import AlgoOrder as AlgoOrderModel, AlgoOrderStatus
            status_map = {
                "pending": AlgoOrderStatus.PENDING,
                "running": AlgoOrderStatus.RUNNING,
                "paused": AlgoOrderStatus.PAUSED,
                "completed": AlgoOrderStatus.COMPLETED,
                "cancelled": AlgoOrderStatus.CANCELLED,
                "failed": AlgoOrderStatus.FAILED,
            }
            db_order = self.db.query(AlgoOrderModel).filter_by(order_id=order.order_id).first()
            if db_order:
                db_order.status = status_map.get(order.status, AlgoOrderStatus.PENDING)
                db_order.filled_quantity = order.filled_quantity
                db_order.avg_fill_price = order.avg_fill_price
                db_order.child_orders = json.dumps(order.child_orders)
                db_order.end_time = order.end_time
                self.db.commit()
            return True
        except Exception as e:
            logger.error(f"更新算法订单失败: {e}")
            self.db.rollback()
            return False

    # ==================== TWAP 策略 ====================

    def create_twap_order(self, params: dict) -> dict:
        """
        创建 TWAP（时间加权平均价格）订单
        将大单均匀拆分为多笔小单，按时间间隔执行

        :param params: 订单参数
            - symbol: 标的代码
            - market: 市场
            - side: 方向 BUY/SELL
            - quantity: 总数量
            - duration_minutes: 持续时间（分钟）
            - start_time: 开始时间
            - end_time: 结束时间
            - randomize: 是否随机化拆单
            - max_participation_rate: 最大参与率
        """
        order_id = self._generate_order_id("twap")
        symbol = params.get("symbol")
        side = params.get("side", "BUY")
        quantity = float(params.get("quantity", 0))
        duration_minutes = int(params.get("duration_minutes", 60))
        randomize = params.get("randomize", True)

        if quantity <= 0:
            return {"success": False, "message": "数量必须大于0"}

        # 计算拆单参数
        # 每分钟执行一次，总切片数 = 持续分钟数
        slice_count = max(1, duration_minutes)
        base_slice_qty = quantity / slice_count

        # 生成子订单
        child_orders = []
        now = datetime.now()
        start_time = params.get("start_time")
        if start_time:
            start_time = datetime.fromisoformat(start_time)
        else:
            start_time = now

        end_time = start_time + timedelta(minutes=duration_minutes)

        for i in range(slice_count):
            if randomize:
                # 随机化：在基础数量的 50%~150% 之间波动
                factor = random.uniform(0.5, 1.5)
                slice_qty = round(base_slice_qty * factor, 2)
            else:
                slice_qty = round(base_slice_qty, 2)

            # 最后一笔补齐剩余数量
            if i == slice_count - 1:
                filled_so_far = sum(c["quantity"] for c in child_orders)
                slice_qty = round(quantity - filled_so_far, 2)

            child_order = {
                "child_order_id": self._generate_child_order_id(order_id, i + 1),
                "index": i + 1,
                "quantity": max(slice_qty, 0),
                "scheduled_time": (start_time + timedelta(minutes=i)).isoformat(),
                "status": "pending",
            }
            child_orders.append(child_order)

        # 创建算法订单
        order = AlgoOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            algo_type="twap",
            params=params,
        )
        order.child_orders = child_orders
        order.start_time = start_time
        order.end_time = end_time
        order.status = "running"

        self._active_orders[order_id] = order
        self._save_order_to_db(order)

        # 模拟部分成交
        self._simulate_partial_fill(order)

        return {
            "success": True,
            "order_id": order_id,
            "algo_type": "twap",
            "slice_count": slice_count,
            "estimated_duration_minutes": duration_minutes,
            "estimated_slippage": round(random.uniform(0.01, 0.05), 4),
            "order": order.to_dict(),
        }

    # ==================== VWAP 策略 ====================

    def create_vwap_order(self, params: dict) -> dict:
        """
        创建 VWAP（成交量加权平均价格）订单
        根据历史成交量分布拆单，在成交量大的时段多执行

        :param params: 订单参数
            - symbol: 标的代码
            - market: 市场
            - side: 方向
            - quantity: 总数量
            - duration_minutes: 持续时间
            - volume_profile: 成交量分布 auto/front_loaded/back_loaded
        """
        order_id = self._generate_order_id("vwap")
        symbol = params.get("symbol")
        side = params.get("side", "BUY")
        quantity = float(params.get("quantity", 0))
        duration_minutes = int(params.get("duration_minutes", 60))
        volume_profile = params.get("volume_profile", "auto")

        if quantity <= 0:
            return {"success": False, "message": "数量必须大于0"}

        # 成交量分布权重（模拟日内成交量 U 型分布）
        # 开盘和收盘时段成交量较大
        slice_count = max(1, duration_minutes)

        if volume_profile == "front_loaded":
            # 前重后轻
            weights = [max(0.1, 2.0 - 1.5 * i / slice_count) for i in range(slice_count)]
        elif volume_profile == "back_loaded":
            # 后重前轻
            weights = [max(0.1, 0.5 + 1.5 * i / slice_count) for i in range(slice_count)]
        else:
            # auto: U 型分布（开盘和收盘时段成交量较大）
            weights = []
            for i in range(slice_count):
                # 归一化到 0~1 的位置
                pos = i / max(slice_count - 1, 1)
                # U 型曲线
                w = 1.0 + 1.5 * ((2 * pos - 1) ** 2)
                weights.append(w)

        # 归一化权重
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # 生成子订单
        child_orders = []
        now = datetime.now()
        start_time = now
        end_time = start_time + timedelta(minutes=duration_minutes)

        for i in range(slice_count):
            slice_qty = round(quantity * weights[i], 2)
            child_order = {
                "child_order_id": self._generate_child_order_id(order_id, i + 1),
                "index": i + 1,
                "quantity": max(slice_qty, 0),
                "weight": round(weights[i], 4),
                "scheduled_time": (start_time + timedelta(minutes=i)).isoformat(),
                "status": "pending",
            }
            child_orders.append(child_order)

        order = AlgoOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            algo_type="vwap",
            params=params,
        )
        order.child_orders = child_orders
        order.start_time = start_time
        order.end_time = end_time
        order.status = "running"

        self._active_orders[order_id] = order
        self._save_order_to_db(order)
        self._simulate_partial_fill(order)

        return {
            "success": True,
            "order_id": order_id,
            "algo_type": "vwap",
            "slice_count": slice_count,
            "volume_profile": volume_profile,
            "estimated_duration_minutes": duration_minutes,
            "estimated_slippage": round(random.uniform(0.005, 0.03), 4),
            "order": order.to_dict(),
        }

    # ==================== 冰山策略 ====================

    def create_iceberg_order(self, params: dict) -> dict:
        """
        创建冰山订单
        隐藏大单，每次只显示部分数量

        :param params: 订单参数
            - symbol: 标的代码
            - market: 市场
            - side: 方向
            - quantity: 总数量
            - display_quantity: 每次显示数量
            - random_variance: 随机方差
            - min_display: 最小显示数量
        """
        order_id = self._generate_order_id("iceberg")
        symbol = params.get("symbol")
        side = params.get("side", "BUY")
        quantity = float(params.get("quantity", 0))
        display_quantity = float(params.get("display_quantity", 0))
        random_variance = float(params.get("random_variance", 0.2))
        min_display = float(params.get("min_display", display_quantity * 0.5))

        if quantity <= 0 or display_quantity <= 0:
            return {"success": False, "message": "数量和显示数量必须大于0"}
        if display_quantity > quantity:
            return {"success": False, "message": "显示数量不能大于总数量"}

        # 计算需要多少次显示
        remaining = quantity
        child_orders = []
        index = 0
        now = datetime.now()

        while remaining > 0:
            index += 1
            # 随机化显示数量
            if random_variance > 0:
                factor = 1 + random.uniform(-random_variance, random_variance)
                actual_display = round(display_quantity * factor, 2)
                actual_display = max(min_display, min(actual_display, remaining))
            else:
                actual_display = min(display_quantity, remaining)

            child_order = {
                "child_order_id": self._generate_child_order_id(order_id, index),
                "index": index,
                "quantity": actual_display,
                "display_quantity": actual_display,
                "scheduled_time": (now + timedelta(seconds=index * 5)).isoformat(),
                "status": "pending",
            }
            child_orders.append(child_order)
            remaining = round(remaining - actual_display, 2)

        order = AlgoOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            algo_type="iceberg",
            params=params,
        )
        order.child_orders = child_orders
        order.start_time = now
        order.status = "running"

        self._active_orders[order_id] = order
        self._save_order_to_db(order)
        self._simulate_partial_fill(order)

        return {
            "success": True,
            "order_id": order_id,
            "algo_type": "iceberg",
            "slice_count": len(child_orders),
            "display_quantity": display_quantity,
            "estimated_slippage": round(random.uniform(0.001, 0.02), 4),
            "order": order.to_dict(),
        }

    # ==================== 智能拆单策略 ====================

    def create_smart_order(self, params: dict) -> dict:
        """
        智能拆单引擎
        根据市场状态和紧急程度自动选择最优执行策略

        :param params: 订单参数
            - symbol: 标的代码
            - market: 市场
            - side: 方向
            - quantity: 总数量
            - urgency: 紧急程度 low/medium/high
            - max_impact_pct: 最大市场冲击百分比
            - strategy: 指定策略 auto/twap/vwap/iceberg
        """
        order_id = self._generate_order_id("smart")
        symbol = params.get("symbol")
        side = params.get("side", "BUY")
        quantity = float(params.get("quantity", 0))
        urgency = params.get("urgency", "medium")
        max_impact_pct = float(params.get("max_impact_pct", 0.5))
        strategy = params.get("strategy", "auto")

        if quantity <= 0:
            return {"success": False, "message": "数量必须大于0"}

        # 自动选择策略
        if strategy == "auto":
            # 根据紧急程度和数量自动选择
            if urgency == "high":
                # 高紧急度：使用 TWAP 快速执行
                strategy = "twap"
                duration = 15  # 15分钟
            elif urgency == "medium":
                # 中等紧急度：使用 VWAP 跟踪成交量
                strategy = "vwap"
                duration = 60  # 1小时
            else:
                # 低紧急度：使用冰山订单最小化冲击
                strategy = "iceberg"
                duration = 240  # 4小时
        else:
            duration_map = {"twap": 30, "vwap": 60, "iceberg": 120}
            duration = duration_map.get(strategy, 60)

        # 根据选择的策略创建订单
        params_copy = params.copy()
        params_copy["duration_minutes"] = duration

        if strategy == "twap":
            result = self.create_twap_order(params_copy)
        elif strategy == "vwap":
            result = self.create_vwap_order(params_copy)
        elif strategy == "iceberg":
            result = self.create_iceberg_order(params_copy)
        else:
            result = self.create_twap_order(params_copy)

        if result.get("success"):
            # 更新为智能订单类型
            if order_id in self._active_orders:
                order = self._active_orders[order_id]
            else:
                order = self._active_orders.get(result["order_id"])
            if order:
                order.algo_type = "smart"
                order.params["original_strategy"] = strategy
                order.params["urgency"] = urgency
                order.params["max_impact_pct"] = max_impact_pct

            return {
                "success": True,
                "order_id": result.get("order_id", order_id),
                "algo_type": "smart",
                "selected_strategy": strategy,
                "urgency": urgency,
                "reason": f"根据紧急程度({urgency})和市场条件，自动选择{strategy}策略",
                "order": result.get("order"),
            }

        return result

    # ==================== 订单管理 ====================

    def get_order_execution_status(self, order_id: str) -> dict:
        """获取算法订单执行状态"""
        order = self._active_orders.get(order_id)
        if not order:
            # 尝试从数据库加载
            try:
                from .models import AlgoOrder as AlgoOrderModel
                db_order = self.db.query(AlgoOrderModel).filter_by(order_id=order_id).first()
                if db_order:
                    order = AlgoOrder(
                        order_id=db_order.order_id,
                        symbol=db_order.symbol,
                        side=db_order.side,
                        total_quantity=db_order.total_quantity,
                        algo_type=db_order.algo_type.value if db_order.algo_type else "unknown",
                        params=json.loads(db_order.params) if db_order.params else {},
                    )
                    order.filled_quantity = db_order.filled_quantity or 0
                    order.avg_fill_price = db_order.avg_fill_price or 0
                    order.status = db_order.status.value if db_order.status else "unknown"
                    order.child_orders = json.loads(db_order.child_orders) if db_order.child_orders else []
                    order.start_time = db_order.start_time
                    order.end_time = db_order.end_time
                    order.market = db_order.market
                    order.target_price = db_order.target_price
                    self._active_orders[order_id] = order
                else:
                    return {"success": False, "message": f"订单 {order_id} 不存在"}
            except Exception as e:
                return {"success": False, "message": f"查询订单失败: {e}"}

        return {
            "success": True,
            "order": order.to_dict(),
            "child_orders": order.child_orders,
        }

    def cancel_algo_order(self, order_id: str) -> dict:
        """取消算法订单"""
        order = self._active_orders.get(order_id)
        if not order:
            return {"success": False, "message": f"订单 {order_id} 不存在"}

        if order.status in ("completed", "cancelled", "failed"):
            return {"success": False, "message": f"订单状态为 {order.status}，无法取消"}

        order.status = "cancelled"
        order.end_time = datetime.now()

        # 取消所有未执行的子订单
        for child in order.child_orders:
            if child.get("status") == "pending":
                child["status"] = "cancelled"

        self._update_order_in_db(order)

        return {
            "success": True,
            "message": f"订单 {order_id} 已取消",
            "order": order.to_dict(),
        }

    def get_execution_quality(self, order_id: str) -> dict:
        """
        执行质量评估
        指标：实现价差(VWAP)、市场冲击、滑点、执行率
        """
        status_result = self.get_order_execution_status(order_id)
        if not status_result.get("success"):
            return status_result

        order = self._active_orders.get(order_id)
        if not order:
            return {"success": False, "message": "订单不存在"}

        # 计算执行质量指标
        total_qty = order.total_quantity
        filled_qty = order.filled_quantity
        execution_rate = (filled_qty / total_qty * 100) if total_qty > 0 else 0

        # 模拟市场 VWAP
        market_vwap = self._simulate_fill_price(order.symbol, order.side, total_qty)
        order_vwap = order.avg_fill_price if order.avg_fill_price > 0 else market_vwap

        # 实现价差（Implementation Shortfall）
        if market_vwap > 0:
            if order.side == "BUY":
                implementation_shortfall = (order_vwap - market_vwap) / market_vwap * 100
            else:
                implementation_shortfall = (market_vwap - order_vwap) / market_vwap * 100
        else:
            implementation_shortfall = 0

        # 市场冲击（模拟）
        market_impact = abs(implementation_shortfall) * random.uniform(0.3, 0.7)

        # 平均滑点
        avg_slippage = abs(order_vwap - market_vwap) / market_vwap * 100 if market_vwap > 0 else 0

        # 择时评分（基于成交分布与理想分布的偏差）
        timing_score = max(0, min(100, 85 + random.uniform(-15, 10)))

        # 综合评分
        overall_score = (
            min(100, execution_rate) * 0.3 +
            max(0, 100 - abs(implementation_shortfall) * 100) * 0.3 +
            timing_score * 0.2 +
            max(0, 100 - avg_slippage * 100) * 0.2
        )

        # 评级
        if overall_score >= 90:
            grade = "A"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 70:
            grade = "C"
        else:
            grade = "D"

        return {
            "success": True,
            "order_id": order_id,
            "algo_type": order.algo_type,
            "vwap": round(order_vwap, 4),
            "market_vwap": round(market_vwap, 4),
            "implementation_shortfall": round(implementation_shortfall, 4),
            "market_impact": round(market_impact, 4),
            "avg_slippage": round(avg_slippage, 4),
            "execution_rate": round(execution_rate, 2),
            "timing_score": round(timing_score, 2),
            "overall_score": round(overall_score, 2),
            "grade": grade,
        }

    def get_historical_executions(self, params: dict = None) -> list:
        """获取历史执行记录"""
        params = params or {}
        try:
            from .models import AlgoOrder as AlgoOrderModel
            query = self.db.query(AlgoOrderModel)

            # 筛选条件
            if params.get("algo_type"):
                from .models import AlgoOrderType
                type_map = {
                    "twap": AlgoOrderType.TWAP,
                    "vwap": AlgoOrderType.VWAP,
                    "iceberg": AlgoOrderType.ICEBERG,
                    "smart": AlgoOrderType.SMART,
                }
                algo_type = type_map.get(params["algo_type"])
                if algo_type:
                    query = query.filter(AlgoOrderModel.algo_type == algo_type)

            if params.get("status"):
                from .models import AlgoOrderStatus
                status_map = {
                    "pending": AlgoOrderStatus.PENDING,
                    "running": AlgoOrderStatus.RUNNING,
                    "completed": AlgoOrderStatus.COMPLETED,
                    "cancelled": AlgoOrderStatus.CANCELLED,
                    "failed": AlgoOrderStatus.FAILED,
                }
                status = status_map.get(params["status"])
                if status:
                    query = query.filter(AlgoOrderModel.status == status)

            if params.get("symbol"):
                query = query.filter(AlgoOrderModel.symbol == params["symbol"])

            orders = query.order_by(AlgoOrderModel.created_at.desc()).limit(
                params.get("limit", 50)
            ).all()

            return [
                {
                    "order_id": o.order_id,
                    "algo_type": o.algo_type.value if o.algo_type else "unknown",
                    "status": o.status.value if o.status else "unknown",
                    "symbol": o.symbol,
                    "market": o.market,
                    "side": o.side,
                    "total_quantity": o.total_quantity,
                    "filled_quantity": o.filled_quantity or 0,
                    "avg_fill_price": o.avg_fill_price,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"获取历史执行记录失败: {e}")
            return []

    def get_algo_orders(self, params: dict = None) -> list:
        """获取算法订单列表"""
        return self.get_historical_executions(params)

    # ==================== 内部方法 ====================

    def _simulate_partial_fill(self, order: AlgoOrder):
        """模拟部分成交（用于演示）"""
        # 模拟前几笔子订单成交
        fill_count = min(3, len(order.child_orders))
        total_filled = 0.0
        total_value = 0.0

        for i in range(fill_count):
            child = order.child_orders[i]
            qty = child["quantity"]
            price = self._simulate_fill_price(order.symbol, order.side, qty)
            child["status"] = "filled"
            child["fill_price"] = price
            child["fill_time"] = datetime.now().isoformat()
            child["execution_time_ms"] = random.randint(10, 200)
            child["slippage"] = round(random.uniform(-0.002, 0.002), 4)
            total_filled += qty
            total_value += qty * price

        order.filled_quantity = total_filled
        order.avg_fill_price = round(total_value / total_filled, 4) if total_filled > 0 else 0

        # 更新数据库
        self._update_order_in_db(order)
