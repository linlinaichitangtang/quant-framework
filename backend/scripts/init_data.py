#!/usr/bin/env python
"""
初始化数据采集
采集A股、港股、美股的历史数据
"""

import sys
import logging
sys.path.append('..')

from app.database import SessionLocal
from data_collection import AStockCollector, HKStockCollector, USStockCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    
    logger.info("=== 开始初始化数据采集 ===")
    
    # 采集A股
    logger.info("1. 开始采集A股数据...")
    a_collector = AStockCollector(db)
    # 只采集最近一年数据，A股全部股票
    a_count = a_collector.collect_all_stocks(days_back=365)
    logger.info(f"A股采集完成: {a_count} 条K线")
    
    # 采集港股
    logger.info("2. 开始采集港股数据...")
    hk_collector = HKStockCollector(db)
    # 只采集最近一年500只港股
    hk_count = hk_collector.collect_all_stocks(days_back=365)
    logger.info(f"港股采集完成: {hk_count} 条K线")
    
    # 采集美股主流股票
    logger.info("3. 开始采集美股主流股票...")
    us_collector = USStockCollector(db)
    us_count = us_collector.collect_popular_stocks(days_back=730)
    logger.info(f"美股采集完成: {us_count} 条K线")
    
    total = a_count + hk_count + us_count
    logger.info(f"=== 数据采集完成，总计 {total} 条K线数据 ===")
    
    db.close()


if __name__ == "__main__":
    main()
