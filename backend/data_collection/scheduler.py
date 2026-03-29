import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from app.database import SessionLocal
from app.config import settings
from app.crud import create_system_log
from .a_stock_collector import AStockCollector
from .hk_stock_collector import HKStockCollector
from .us_stock_collector import USStockCollector

logger = logging.getLogger(__name__)


def collect_a_stock():
    """A股每日采集任务"""
    logger.info("开始执行A股每日数据采集")
    try:
        db = SessionLocal()
        collector = AStockCollector(db)
        count = collector.collect_today()
        create_system_log(db, "INFO", "collector", f"A股每日数据采集完成，采集 {count} 条K线")
        db.close()
        logger.info(f"A股每日数据采集完成，采集 {count} 条K线")
    except Exception as e:
        logger.error(f"A股每日数据采集失败: {str(e)}")
        try:
            db = SessionLocal()
            create_system_log(db, "ERROR", "collector", f"A股每日数据采集失败: {str(e)}")
            db.close()
        except:
            pass


def collect_hk_stock():
    """港股每日采集任务"""
    logger.info("开始执行港股每日数据采集")
    try:
        db = SessionLocal()
        collector = HKStockCollector(db)
        count = collector.collect_today()
        create_system_log(db, "INFO", "collector", f"港股每日数据采集完成，采集 {count} 条K线")
        db.close()
        logger.info(f"港股每日数据采集完成，采集 {count} 条K线")
    except Exception as e:
        logger.error(f"港股每日数据采集失败: {str(e)}")
        try:
            db = SessionLocal()
            create_system_log(db, "ERROR", "collector", f"港股每日数据采集失败: {str(e)}")
            db.close()
        except:
            pass


def collect_us_stock():
    """美股每日采集任务"""
    logger.info("开始执行美股每日数据采集")
    try:
        db = SessionLocal()
        collector = USStockCollector(db)
        count = collector.collect_today()
        create_system_log(db, "INFO", "collector", f"美股每日数据采集完成，采集 {count} 条K线")
        db.close()
        logger.info(f"美股每日数据采集完成，采集 {count} 条K线")
    except Exception as e:
        logger.error(f"美股每日数据采集失败: {str(e)}")
        try:
            db = SessionLocal()
            create_system_log(db, "ERROR", "collector", f"美股每日数据采集失败: {str(e)}")
            db.close()
        except:
            pass


def run_scheduler():
    """启动定时任务"""
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')
    
    # A股 收盘后 15:15 执行
    a_cron = settings.a_stock_collect_cron
    a_trigger = CronTrigger.from_crontab(a_cron, timezone='Asia/Shanghai')
    scheduler.add_job(collect_a_stock, a_trigger)
    
    # 港股 收盘后 16:16 执行
    hk_cron = settings.hk_stock_collect_cron
    hk_trigger = CronTrigger.from_crontab(hk_cron, timezone='Asia/Shanghai')
    scheduler.add_job(collect_hk_stock, hk_trigger)
    
    # 美股 收盘后次日凌晨 5:00 执行
    us_cron = settings.us_stock_collect_cron
    us_trigger = CronTrigger.from_crontab(us_cron, timezone='Asia/Shanghai')
    scheduler.add_job(collect_us_stock, us_trigger)
    
    logger.info("数据采集定时任务启动")
    print("数据采集定时任务启动...")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("定时任务停止")
        scheduler.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_scheduler()
