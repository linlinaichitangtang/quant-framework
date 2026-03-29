import logging
import akshare as ak
import pandas as pd
from typing import List, Dict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from .collector_base import BaseCollector
from app.models import MarketType

logger = logging.getLogger(__name__)


class AStockCollector(BaseCollector):
    """A股数据采集器"""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    def get_stock_list(self) -> List[Dict]:
        """获取A股股票列表"""
        logger.info("正在获取A股股票列表...")
        stock_info = ak.stock_info_a_code_name()
        result = []
        for _, row in stock_info.iterrows():
            result.append({
                "symbol": row["code"],
                "name": row["name"],
                "market": MarketType.A
            })
        logger.info(f"获取到 {len(result)} 只A股股票")
        return result
    
    def get_daily_bars(self, symbol: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """获取A股日线数据"""
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            
            if df.empty:
                logger.warning(f"{symbol} 未获取到数据")
                return []
            
            # 转换格式
            result = []
            for _, row in df.iterrows():
                date = datetime.strptime(str(row["日期"]), "%Y-%m-%d")
                result.append({
                    "date": date,
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": float(row["成交量"]) * 100,  # 转换成股
                    "turnover": float(row["成交额"]) * 1000  # 转换成元
                })
            
            logger.debug(f"{symbol} 获取到 {len(result)} 条日线数据")
            return result
        
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据失败: {str(e)}")
            return []
    
    def collect_all_stocks(self, days_back: int = 365):
        """采集所有A股股票的历史数据"""
        stock_list = self.get_stock_list()
        total_saved = 0
        
        # 先保存所有股票基础信息
        for stock in stock_list:
            self.save_stock_info(
                symbol=stock["symbol"],
                name=stock["name"],
                market=MarketType.A
            )
        
        # 计算开始日期
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        
        # 逐个采集
        for stock in stock_list:
            bars = self.get_daily_bars(stock["symbol"], start_date, end_date)
            if bars:
                saved = self.save_daily_bars(stock["symbol"], MarketType.A, bars)
                total_saved += saved
        
        logger.info(f"A股数据采集完成，共保存 {total_saved} 条K线")
        return total_saved
    
    def collect_today(self):
        """采集今日数据（用于定时任务）"""
        today = datetime.now().strftime("%Y%m%d")
        stock_list = self.get_stock_list()
        total_saved = 0
        
        for stock in stock_list:
            bars = self.get_daily_bars(stock["symbol"], today, today)
            if bars:
                saved = self.save_daily_bars(stock["symbol"], MarketType.A, bars)
                total_saved += saved
        
        logger.info(f"A股今日数据采集完成，共保存 {total_saved} 条K线")
        return total_saved
