"""
Tushare数据获取模块
负责从Tushare获取A股历史行情和基本面数据
"""
import os
import sys
import pandas as pd
import numpy as np
import tushare as ts
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from src.utils.logging import logger
from src.data.cache import DataCache


class TushareProvider:
    """Tushare数据提供者"""
    
    def __init__(self, token: Optional[str] = None, cache_dir: str = "../../storage/cache"):
        """
        初始化
        
        Args:
            token: Tushare API token，如果不传则从环境变量获取
            cache_dir: 缓存目录
        """
        if token is None:
            token = os.getenv("TUSHARE_TOKEN")
            if token is None:
                raise ValueError("TUSHARE_TOKEN not found in environment variables")
        
        self.token = token
        ts.set_token(token)
        self.pro = ts.pro_api()
        self.cache = DataCache(cache_dir)
    
    def get_stock_list(self, list_status: str = "L", exchange: Optional[str] = None) -> pd.DataFrame:
        """
        获取股票列表
        
        Args:
            list_status: 上市状态 L上市 D退市 P暂停上市
            exchange: 交易所 SSE上交所 SZSE深交所
        
        Returns:
            股票列表DataFrame
        """
        cache_key = f"stock_list_{list_status}_{exchange}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.info(f"从缓存加载股票列表，共 {len(cached)} 只")
            return cached
        
        logger.info("从Tushare获取股票列表")
        df = self.pro.stock_basic(exchange=exchange, list_status=list_status, 
                                  fields='ts_code,symbol,name,area,industry,fullname,enname,market,exchange,list_date,delist_date')
        self.cache.set(cache_key, df)
        logger.info(f"获取到 {len(df)} 只股票")
        return df
    
    def get_daily_bars(self, ts_code: str, start_date: str, end_date: str, 
                       adj: str = "qfq") -> pd.DataFrame:
        """
        获取日线行情数据
        
        Args:
            ts_code: 股票代码（Tushare格式）
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adj: 复权方式 None/qfq/hfq
        
        Returns:
            日线行情DataFrame，按日期升序排列
        """
        cache_key = f"daily_{ts_code}_{start_date}_{end_date}_{adj}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        
        logger.debug(f"从Tushare获取日线: {ts_code}")
        df = ts.pro_bar(ts_code=ts_code, api=self.pro, adj=adj, 
                       start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            logger.warning(f"未获取到数据: {ts_code}")
            return pd.DataFrame()
        
        # 按日期升序排列
        df = df.sort_values("trade_date").reset_index(drop=True)
        # 转换日期格式
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        
        self.cache.set(cache_key, df)
        return df
    
    def get_all_daily_bars(self, ts_codes: List[str], start_date: str, end_date: str,
                           adj: str = "qfq") -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票日线数据
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权方式
        
        Returns:
            {ts_code: DataFrame}
        """
        result = {}
        total = len(ts_codes)
        for i, ts_code in enumerate(ts_codes):
            if i % 100 == 0:
                logger.info(f"批量获取进度: {i+1}/{total}")
            df = self.get_daily_bars(ts_code, start_date, end_date, adj)
            if not df.empty:
                result[ts_code] = df
        logger.info(f"批量获取完成，成功获取 {len(result)}/{total} 只")
        return result
    
    def get_factor_data(self, ts_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        获取因子数据（需要Tushare专业版）
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            因子DataFrame
        """
        try:
            df = self.pro.cn_stock_factors(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return df.sort_values("trade_date").reset_index(drop=True)
        except Exception as e:
            logger.warning(f"获取因子数据失败 {ts_code}: {e}")
            return None
    
    def filter_universe(self, df: pd.DataFrame) -> List[str]:
        """
        过滤选股池：去除ST、退市、停牌等
        
        Args:
            df: 股票列表DataFrame
        
        Returns:
            过滤后的ts_code列表
        """
        # 排除ST
        df = df[~df.name.str.contains("ST")]
        # 排除退市
        df = df[df.list_status == "L"]
        # 排除新股上市不足3个月？这里可以根据需求调整
        # df = df[df.list_date.apply(lambda x: (datetime.now() - datetime.strptime(x, "%Y%m%d")).days > 90)]
        return df.ts_code.tolist()


if __name__ == "__main__":
    # 测试
    from dotenv import load_dotenv
    load_dotenv("../../.env")
    provider = TushareProvider()
    stocks = provider.get_stock_list()
    print(stocks.head())
    print(f"Total stocks: {len(stocks)}")
