"""
标签构造模块
根据次日收益率构造标签，用于机器学习训练
"""
import pandas as pd
import numpy as np
from typing import Optional


class LabelConstructor:
    """标签构造器"""
    
    def __init__(self, threshold: float = 0.02, forward_days: int = 1):
        """
        初始化标签构造器
        :param threshold: 上涨阈值，超过这个阈值认为是正样本
        :param forward_days: 预测未来几天的收益，默认1天（隔夜）
        """
        self.threshold = threshold
        self.forward_days = forward_days
    
    def construct_label(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        构造标签
        标签y=1表示次日收益率 >= threshold，y=0否则
        严格避免未来函数，只使用当日及之前数据构造
        :param df: 按日期排序的DataFrame
        :return: 添加了标签的DataFrame
        """
        df = df.sort_values('trade_date').copy()
        
        # 计算未来N日收益率（shift(-N)获取未来价格）
        # 注意：这里用shift(-forward_days)将未来数据移到当前行，严格按时间顺序
        df['future_close'] = df['close'].shift(-self.forward_days)
        df['future_return'] = (df['future_close'] - df['close']) / df['close']
        
        # 二分类标签：是否会上涨超过阈值
        df['y'] = (df['future_return'] >= self.threshold).astype(int)
        
        # 也提供回归标签（原始收益率）
        df['y_reg'] = df['future_return']
        
        # 删除最后forward_days行，因为它们没有未来数据
        df = df.iloc[:-self.forward_days].copy()
        
        return df
    
    def construct_label_with_open(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        使用次日开盘价计算收益（更真实，因为实际卖出通常在次日开盘或盘中）
        标签基于次日开盘后到次日收盘的收益
        :param df: 按日期排序的DataFrame
        :return: 添加了标签的DataFrame
        """
        df = df.sort_values('trade_date').copy()
        
        # 次日开盘价
        df['next_open'] = df['open'].shift(-1)
        # 次日收盘价
        df['next_close'] = df['close'].shift(-1)
        
        # 如果尾盘买入，以收盘价买入，次日卖出收益
        # 买入成本：收盘价
        # 卖出收益：次日不同时间点计算
        df['return_next_open'] = (df['next_open'] - df['close']) / df['close']
        df['return_next_close'] = (df['next_close'] - df['close']) / df['close']
        df['max_next_high'] = df['high'].shift(-1)
        df['return_next_max'] = (df['max_next_high'] - df['close']) / df['close']
        
        # 标签：次日最大涨幅超过阈值（考虑冲高卖出可能）
        df['y'] = (df['return_next_max'] >= self.threshold).astype(int)
        
        # 标签：次日收盘涨幅超过阈值
        df['y_close'] = (df['return_next_close'] >= self.threshold).astype(int)
        
        # 删除最后一行，因为没有次日数据
        df = df.iloc[:-1].copy()
        
        return df
    
    def get_class_distribution(self, df: pd.DataFrame) -> dict:
        """获取类别分布"""
        if 'y' not in df.columns:
            return {}
        
        dist = df['y'].value_counts().to_dict()
        total = len(df)
        dist_pct = {k: v/total for k, v in dist.items()}
        
        return {
            'counts': dist,
            'percentages': dist_pct,
            'positive_ratio': dist_pct.get(1, 0)
        }
