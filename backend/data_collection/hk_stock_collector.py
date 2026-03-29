import logging
import akshare as ak
import pandas as pd
from typing import List, Dict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from .collector_base import BaseCollector
from app.models import MarketType

logger = logging.getLogger(__name__)


class HKStockCollector(BaseCollector):
    """港股数据采集器"""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    def get_stock_list(self) -> List[Dict]:
        """获取港股股票列表"""
        logger.info("正在获取港股股票列表...")
        stock_info = ak.stock_hk_spot()
        result = []
        for _, row in stock_info.iterrows():
            symbol = str(row["代码"])
            # 补零到5位
            symbol = symbol.zfill(5)
            result.append({
                "symbol": symbol,
                "name": row["名称"],
                "market": MarketType.HK
            })
        logger.info(f"获取到 {len(result)} 只港股")
        return result
    
    def get_daily_bars(self, symbol: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """获取港股日线数据"""
        try:
            df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            
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
                    "turnover": float(row.get("amount", 0))
                })
            
            logger.debug(f"{symbol} 获取到 {len(result)} 条日线数据")
            return result
        
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据失败: {str(e)}")
            return []
    
    def collect_all_stocks(self, days_back: int = 365):
        """采集所有港股历史数据"""
        stock_list = self.get_stock_list()
        total_saved = 0
        
        # 先保存所有股票基础信息
        for stock in stock_list:
            self.save_stock_info(
                symbol=stock["symbol"],
                name=stock["name"],
                market=MarketType.HK
            )
        
        # 计算开始日期
        end_date = (datetime.now()).strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
        
        # 只采集主要股票，避免数据量过大
        # 这里只取市值较大的前500只，可根据需要调整
        for stock in stock_list[:500]:
            bars = self.get_daily_bars(stock["symbol"], start_date, end_date)
            if bars:
                saved = self.save_daily_bars(stock["symbol"], MarketType.HK, bars)
                total_saved += saved
        
        logger.info(f"港股数据采集完成，共保存 {total_saved} 条K线")
        return total_saved
    
    def collect_today(self):
        """采集今日数据（用于定时任务）"""
        today = datetime.now().strftime("%Y%m%d")
        # 获取所有已保存的港股
        # 只更新已有的股票，避免全量更新
        from app.database import SessionLocal
        db = SessionLocal()
        from app.crud import get_stock_list
        stock_list = get_stock_list(db, market=MarketType.HK, limit=1000)
        total_saved = 0
        
        for stock in stock_list:
            bars = self.get_daily_bars(stock.symbol, today, today)
            if bars:
                saved = self.save_daily_bars(stock.symbol, MarketType.HK, bars)
                total_saved += saved
        
        logger.info(f"港股今日数据采集完成，共保存 {total_saved} 条K线")
        return total_saved
