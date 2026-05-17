"""
因子数据抽取模块
抽取技术因子用于机器学习模型训练
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional


class FactorExtractor:
    """因子抽取器"""
    
    def __init__(self):
        self.factor_names = []
    
    def calculate_ma_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算均线相关因子"""
        # 确保数据按日期排序
        df = df.sort_values('trade_date').copy()
        
        # 移动平均线
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        
        # 价格相对于均线的位置
        df['close_over_ma5'] = df['close'] / df['ma5'] - 1
        df['close_over_ma10'] = df['close'] / df['ma10'] - 1
        df['close_over_ma20'] = df['close'] / df['ma20'] - 1
        df['close_over_ma60'] = df['close'] / df['ma60'] - 1
        
        # 均线斜率
        df['ma5_slope'] = df['ma5'].diff() / df['ma5']
        df['ma20_slope'] = df['ma20'].diff() / df['ma20']
        
        # 均线多空排列
        df['ma_bullish'] = ((df['ma5'] > df['ma10']) & 
                           (df['ma10'] > df['ma20']) & 
                           (df['ma20'] > df['ma60'])).astype(int)
        
        return df
    
    def calculate_return_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算收益相关因子"""
        df = df.sort_values('trade_date').copy()
        
        # 不同周期收益率
        df['return_1d'] = df['close'].pct_change(1)
        df['return_2d'] = df['close'].pct_change(2)
        df['return_3d'] = df['close'].pct_change(3)
        df['return_5d'] = df['close'].pct_change(5)
        df['return_10d'] = df['close'].pct_change(10)
        df['return_20d'] = df['close'].pct_change(20)
        
        # 波动率
        df['volatility_5d'] = df['return_1d'].rolling(5).std()
        df['volatility_10d'] = df['return_1d'].rolling(10).std()
        df['volatility_20d'] = df['return_1d'].rolling(20).std()
        
        # 偏度
        df['skewness_5d'] = df['return_1d'].rolling(5).skew()
        df['skewness_10d'] = df['return_1d'].rolling(10).skew()
        
        return df
    
    def calculate_volume_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算成交量相关因子"""
        df = df.sort_values('trade_date').copy()
        
        # 成交量均线
        df['volume_ma5'] = df['volume'].rolling(5).mean()
        df['volume_ma10'] = df['volume'].rolling(10).mean()
        df['volume_ma20'] = df['volume'].rolling(20).mean()
        
        # 成交量相对比例
        df['volume_ratio_5'] = df['volume'] / df['volume_ma5']
        df['volume_ratio_10'] = df['volume'] / df['volume_ma10']
        df['volume_ratio_20'] = df['volume'] / df['volume_ma20']
        
        # 成交量变化率
        df['volume_change_1d'] = df['volume'].pct_change(1)
        
        # 价量相关性
        def rolling_corr(window):
            if len(window) < 5:
                return np.nan
            return window['close'].pct_change().corr(window['volume'].pct_change())
        
        # 滚动计算价量相关性，这里用更高效的方式
        df['price_volume_corr_5d'] = (
            df['return_1d']
            .rolling(5)
            .corr(df['volume_change_1d'])
        )
        
        # 放量/缩量标记
        df['is_volume_burst'] = (df['volume_ratio_5'] > 1.5).astype(int)
        
        return df
    
    def calculate_hl_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算最高价最低价相关因子"""
        df = df.sort_values('trade_date').copy()
        
        # 位置因子：收盘价在当日区间的位置 (0~1)
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-8)
        
        # 振幅
        df['amplitude'] = (df['high'] - df['low']) / df['open'] * 100
        df['amplitude_5d_avg'] = df['amplitude'].rolling(5).mean()
        df['amplitude_ratio'] = df['amplitude'] / df['amplitude_5d_avg']
        
        # N日最高最低
        df['high_5d'] = df['high'].rolling(5).max()
        df['low_5d'] = df['low'].rolling(5).min()
        df['breakout_5d'] = (df['close'] > df['high_5d'].shift(1)).astype(int)
        df['breakdown_5d'] = (df['close'] < df['low_5d'].shift(1)).astype(int)
        
        # 距离最高最低点的比例
        df['dist_to_5d_high'] = (df['high_5d'] - df['close']) / df['high_5d']
        df['dist_to_5d_low'] = (df['close'] - df['low_5d']) / df['low_5d']
        
        return df
    
    def calculate_cap_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算市值相关因子"""
        if 'circulating_cap' not in df.columns and 'total_cap' not in df.columns:
            # 如果没有市值数据，尝试计算
            if 'close' in df.columns and 'circulating_share' in df.columns:
                df['circulating_cap'] = df['close'] * df['circulating_share']
            else:
                return df
        
        if 'circulating_cap' in df.columns:
            df['log_cap'] = np.log(df['circulating_cap'])
            df['cap_mv_rank'] = df['circulating_cap'].rank(pct=True)
        
        return df
    
    def calculate_momentum_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算动量因子"""
        df = df.sort_values('trade_date').copy()
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / (avg_loss + 1e-8)
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # RSI归一化
        df['rsi_14_norm'] = df['rsi_14'] / 100
        
        # KDJ
        low_9 = df['low'].rolling(9).min()
        high_9 = df['high'].rolling(9).max()
        rsv = (df['close'] - low_9) / (high_9 - low_9 + 1e-8) * 100
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']
        df['k_norm'] = df['k'] / 100
        df['j_norm'] = df['j'] / 100
        
        return df
    
    def extract_all_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """抽取所有因子"""
        df = self.calculate_ma_factors(df)
        df = self.calculate_return_factors(df)
        df = self.calculate_volume_factors(df)
        df = self.calculate_hl_factors(df)
        df = self.calculate_cap_factors(df)
        df = self.calculate_momentum_factors(df)
        
        # 收集所有因子列名
        exclude_cols = ['ts_code', 'trade_date', 'code', 'name', 'open', 'high', 
                       'low', 'close', 'volume', 'amount', 'turnover', 
                       'circulating_cap', 'total_cap', 'circulating_share',
                       'is_st', 'is_suspended', 'has_bad_news', 'consecutive_limit',
                       'late_rally']
        
        factor_cols = [col for col in df.columns if col not in exclude_cols]
        self.factor_names = factor_cols
        
        return df, factor_cols
    
    def get_factor_data(self, df: pd.DataFrame, factor_cols: Optional[List[str]] = None) -> np.ndarray:
        """获取因子矩阵"""
        if factor_cols is None:
            factor_cols = self.factor_names
        
        # 删除NaN值
        factor_data = df[factor_cols].copy()
        factor_data = factor_data.fillna(factor_data.mean())
        
        return factor_data.values
