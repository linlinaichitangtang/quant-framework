"""
FMZ 持仓同步调度器

定时从 FMZ 获取机器人状态和持仓信息，同步到本地数据库。
"""

import logging
import time
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.blocking import BlockingScheduler

from app.fmz_client import FMZClient, FMZAPIError
from app.database import SessionLocal
from app import crud, models

logger = logging.getLogger(__name__)


class FMZSyncScheduler:
    """FMZ 持仓同步调度器"""

    def __init__(self, robot_id: Optional[int] = None, interval_minutes: int = 5):
        """
        Args:
            robot_id: FMZ 机器人 ID
            interval_minutes: 同步间隔（分钟）
        """
        self.robot_id = robot_id
        self.interval_minutes = interval_minutes
        self.scheduler = BlockingScheduler()
        self.client: Optional[FMZClient] = None

    def _init_client(self):
        """初始化 FMZ 客户端"""
        if not self.client:
            self.client = FMZClient(robot_id=self.robot_id)

    def sync_robot_status(self):
        """同步机器人状态"""
        self._init_client()
        db = SessionLocal()
        try:
            status = self.client.sync_robot_status()
            logger.info(
                f"FMZ 机器人状态: id={status['robot_id']}, "
                f"name={status['name']}, "
                f"status={status['status_text']}"
            )

            # 记录系统日志
            crud.create_system_log(
                db=db,
                level="INFO",
                module="fmz_sync",
                message=f"机器人状态同步: {status['status_text']}",
                details=str(status)
            )
        except FMZAPIError as e:
            logger.error(f"FMZ 状态同步失败: {e.message}")
            crud.create_system_log(
                db=db,
                level="ERROR",
                module="fmz_sync",
                message=f"机器人状态同步失败: {e.message}"
            )
        except Exception as e:
            logger.error(f"FMZ 状态同步异常: {e}")
        finally:
            db.close()

    def sync_pending_orders(self):
        """轮询待成交订单状态"""
        self._init_client()
        db = SessionLocal()
        try:
            # 获取所有 PENDING 状态的交易记录
            pending_trades = crud.get_trade_records(db, status="PENDING", limit=50)

            if not pending_trades:
                return

            logger.info(f"轮询 {len(pending_trades)} 笔待成交订单")

            for trade in pending_trades:
                # 检查订单是否超时（超过 5 分钟未成交）
                elapsed = (datetime.now() - trade.created_at).total_seconds()
                if elapsed > 300:  # 5 分钟超时
                    logger.warning(
                        f"订单超时: id={trade.id}, "
                        f"symbol={trade.symbol}, "
                        f"elapsed={elapsed:.0f}s"
                    )
                    trade.status = "CANCELLED"
                    db.commit()

                    # 如果关联的信号没有其他成交记录，回退信号状态
                    if trade.signal_id:
                        signal = crud.get_trading_signal(db, trade.signal_id)
                        if signal and signal.status == "EXECUTED":
                            signal.status = "FAILED"
                            db.commit()

        except Exception as e:
            logger.error(f"订单轮询异常: {e}")
        finally:
            db.close()

    def sync_positions(self):
        """同步持仓信息（通过查询命令）"""
        self._init_client()
        db = SessionLocal()
        try:
            result = self.client.query_position()
            if result and result.get("success"):
                logger.info("持仓同步完成")
                crud.create_system_log(
                    db=db,
                    level="INFO",
                    module="fmz_sync",
                    message="持仓同步完成",
                    details=str(result)
                )
        except Exception as e:
            logger.error(f"持仓同步失败: {e}")
        finally:
            db.close()

    def run(self):
        """启动同步调度器"""
        logger.info(
            f"FMZ 同步调度器启动: "
            f"robot_id={self.robot_id}, "
            f"interval={self.interval_minutes}min"
        )

        # 机器人状态同步
        self.scheduler.add_job(
            self.sync_robot_status,
            'interval',
            minutes=self.interval_minutes,
            id='sync_robot_status',
            name='同步FMZ机器人状态'
        )

        # 待成交订单轮询
        self.scheduler.add_job(
            self.sync_pending_orders,
            'interval',
            minutes=1,
            id='sync_pending_orders',
            name='轮询待成交订单'
        )

        # 持仓同步
        self.scheduler.add_job(
            self.sync_positions,
            'interval',
            minutes=self.interval_minutes,
            id='sync_positions',
            name='同步FMZ持仓'
        )

        # 启动时立即执行一次
        self.sync_robot_status()
        self.sync_pending_orders()

        try:
            self.scheduler.start()
        except KeyboardInterrupt:
            logger.info("FMZ 同步调度器停止")
            self.scheduler.shutdown()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    )
    sync = FMZSyncScheduler(interval_minutes=5)
    sync.run()
