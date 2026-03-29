import logging
import akshare as ak
import pandas as pd
from typing import List, Dict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from .collector_base import BaseCollector
from app.models import MarketType

logger = logging.getLogger(__name__)


class USStockCollector(BaseCollector):
    """美股数据采集器"""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    def get_stock_list(self) -> List[Dict]:
        """获取美股股票列表"""
        logger.info("正在获取美股股票列表...")
        stock_info = ak.stock_us_spot()
        result = []
        for _, row in stock_info.iterrows():
            result.append({
                "symbol": row["symbol"],
                "name": row["name"],
                "market": MarketType.US
            })
        logger.info(f"获取到 {len(result)} 只美股")
        return result
    
    def get_daily_bars(self, symbol: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """获取美股日线数据"""
        try:
            df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
            
            if df.empty:
                logger.warning(f"{symbol} 未获取到数据")
                return []
            
            # 过滤日期范围
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y%m%d")
                df = df[df.index >= start_dt.date()]
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y%m%d")
                df = df[df.index <= end_dt.date()]
            
            # 转换格式
            result = []
            for idx, row in df.iterrows():
                date = datetime(idx.year, idx.month, idx.day)
                result.append({
                    "date": date,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "turnover": float(row["close"] * row["volume"])
                })
            
            logger.debug(f"{symbol} 获取到 {len(result)} 条日线数据")
            return result
        
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据失败: {str(e)}")
            return []
    
    def collect_popular_stocks(self, days_back: int = 730):
        """采集主流美股（前100只）历史数据"""
        # 获取常用美股列表（这里简化处理，只取热门股票）
        popular_symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "BABA", 
            "PDD", "NFLX", "V", "JPM", "JNJ", "WMT", "DIS", "HD", "BAC", "PG", "XOM"
        ]
        total_saved = 0
        
        # 计算开始日期
        end_date = (datetime.now()).strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        
        for symbol in popular_symbols:
            # 先保存基础信息
            self.save_stock_info(
                symbol=symbol,
                name=symbol,
                market=MarketType.US
            )
            bars = self.get_daily_bars(symbol, start_date, end_date)
            if bars:
                saved = self.save_daily_bars(symbol, MarketType.US, bars)
                total_saved += saved
        
        logger.info(f"美股数据采集完成，共保存 {total_saved} 条K线")
        return total_saved
    
    def collect_today(self):
        """采集今日数据（用于定时任务）"""
        today = datetime.now().strftime("%Y%m%d")
        from app.database import SessionLocal
        db = SessionLocal()
        from app.crud import get_stock_list
        stock_list = get_stock_list(db, market=MarketType.US, limit=200)
        total_saved = 0
        
        for stock in stock_list:
            bars = self.get_daily_bars(stock.symbol, today, today)
            if bars:
                saved = self.save_daily_bars(stock.symbol, MarketType.US, bars)
                total_saved += saved
        
        logger.info(f"美股今日数据采集完成，共保存 {total_saved} 条K线")
        return total_saved
