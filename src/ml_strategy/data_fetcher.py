"""
基于tushare的数据获取模块
"""
import tushare as ts
import pandas as pd
import numpy as np
import os
from typing import List, Optional, Dict
from datetime import datetime


class TushareDataFetcher:
    """基于tushare的数据获取"""
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化
        :param token: tushare token，如果为None则从环境变量获取
        """
        if token is None:
            token = os.environ.get('TUSHARE_TOKEN')
        
        if token:
            ts.set_token(token)
            self.pro = ts.pro_api()
        else:
            self.pro = None
            print("Warning: TUSHARE_TOKEN not set, using old tushare API (may be limited)")
    
    def get_daily_data(self, 
                       ts_code: str, 
                       start_date: str = '20180101', 
                       end_date: str = None,
                       cache_dir: str = './cache') -> pd.DataFrame:
        """
        获取日K线数据
        :param ts_code: 股票代码 tushare格式
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param cache_dir: 缓存目录
        :return: DataFrame
        """
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = f"{cache_dir}/{ts_code}_{start_date}_{end_date}.pkl"
        
        # 如果有缓存直接读取
        if os.path.exists(cache_file):
            print(f"Loading {ts_code} from cache...")
            return pd.read_pickle(cache_file)
        
        if self.pro:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        else:
            # 旧版API
            code = ts_code.split('.')[0]
            df = ts.get_hist_data(code, start=start_date, end=end_date)
            if df is not None:
                df = df.reset_index()
                df.rename(columns={'date': 'trade_date'}, inplace=True)
                # 调整列名匹配
                df['ts_code'] = ts_code
                df['open'] = df['open']
                df['high'] = df['high']
                df['low'] = df['low']
                df['close'] = df['close']
                df['volume'] = df['volume']
        
        if df is None or len(df) == 0:
            print(f"Warning: No data for {ts_code}")
            return pd.DataFrame()
        
        # 按日期排序
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 转换日期格式
        if df['trade_date'].dtype == object:
            df['trade_date'] = df['trade_date'].astype(str)
        
        # 缓存
        df.to_pickle(cache_file)
        
        return df
    
    def get_stock_list(self, list_status: str = 'L', exchange: str = 'SHSZ') -> pd.DataFrame:
        """获取股票列表"""
        if self.pro:
            return self.pro.stock_basic(exchange=exchange, list_status=list_status)
        else:
            return ts.get_stock_basics().reset_index()
    
    def get_all_stock_daily(self, 
                           ts_codes: List[str], 
                           start_date: str, 
                           end_date: str,
                           cache_dir: str = './cache') -> Dict[str, pd.DataFrame]:
        """批量获取多个股票的日线数据"""
        result = {}
        for ts_code in ts_codes:
            df = self.get_daily_data(ts_code, start_date, end_date, cache_dir)
            if len(df) > 0:
                result[ts_code] = df
        return result
    
    def get_index_daily(self, ts_code: str = '000001.SH', 
                       start_date: str = '20180101', 
                       end_date: str = None) -> pd.DataFrame:
        """获取指数日线数据"""
        if self.pro:
            df = self.pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        else:
            if ts_code == '000001.SH':
                df = ts.get_hist_data('sh', start=start_date, end=end_date).reset_index()
                df.rename(columns={'date': 'trade_date'}, inplace=True)
            else:
                code = ts_code.split('.')[0]
                df = ts.get_hist_data(code, start=start_date, end=end_date).reset_index()
                df.rename(columns={'date': 'trade_date'}, inplace=True)
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        return df


def prepare_daily_candidates(daily_data: Dict[str, pd.DataFrame], 
                           trade_date: str,
                           filter_rules: Optional[Dict] = None) -> pd.DataFrame:
    """
    准备某日的候选股票数据，合并所有因子
    :param daily_data: 所有股票的历史数据字典
    :param trade_date: 目标日期
    :param filter_rules: 基础过滤规则（对应策略文档中的选股规则）
    :return: 候选股票DataFrame
    """
    candidates = []
    
    default_rules = {
        'min_change_pct': 3.0,
        'max_change_pct': 8.0,
        'min_amplitude': 4.0,
        'min_turnover': 3.0,
        'max_turnover': 20.0,
        'min_volume_ratio_5d': 1.5,
        'min_cap': 50e8,
        'max_cap': 500e8,
    }
    
    if filter_rules:
        default_rules.update(filter_rules)
    
    from .factor_extractor import FactorExtractor
    fe = FactorExtractor()
    
    for code, df in daily_data.items():
        # 找到目标日期的数据
        day_df = df[df['trade_date'] == trade_date]
        if len(day_df) == 0:
            continue
        
        # 提取因子（使用全部历史到该日的数据）
        df_up_to_date = df[df['trade_date'] <= trade_date].copy()
        df_up_to_date = fe.extract_all_factors(df_up_to_date)[0]
        
        # 只保留目标日期那一行
        day_row = df_up_to_date[df_up_to_date['trade_date'] == trade_date]
        if len(day_row) > 0:
            candidates.append(day_row.iloc[0])
    
    result = pd.DataFrame(candidates)
    return result
