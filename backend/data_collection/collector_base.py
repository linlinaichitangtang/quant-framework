import logging
from abc import ABC, abstractmethod
from typing import List, Dict
from datetime import datetime

from sqlalchemy.orm import Session
from app import crud, schemas
from app.models import MarketType, BarType

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """行情采集器基类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @abstractmethod
    def get_stock_list(self) -> List[Dict]:
        """获取股票列表"""
        pass
    
    @abstractmethod
    def get_daily_bars(self, symbol: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """获取日线数据"""
        pass
    
    def save_stock_info(self, symbol: str, name: str, market: MarketType, industry: str = None, list_date: str = None):
        """保存股票基础信息"""
        existing = crud.get_stock_info(self.db, symbol)
        if existing:
            logger.debug(f"股票 {symbol} 已存在，跳过")
            return existing
        
        stock = schemas.StockInfoCreate(
            symbol=symbol,
            name=name,
            market=market,
            industry=industry,
            list_date=list_date
        )
        return crud.create_stock_info(self.db, stock)
    
    def save_daily_bars(self, symbol: str, market: MarketType, bars: List[Dict]):
        """批量保存日线数据"""
        db_bars = []
        for bar in bars:
            db_bar = schemas.HistoricalBarCreate(
                symbol=symbol,
                market=market,
                bar_type=BarType.DAILY,
                timestamp=bar["date"],
                open=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar["volume"],
                turnover=bar.get("turnover")
            )
            db_bars.append(db_bar)
        
        crud.bulk_create_historical_bars(self.db, db_bars)
        logger.info(f"保存 {symbol} {len(db_bars)} 条日线数据完成")
        
        return len(db_bars)
