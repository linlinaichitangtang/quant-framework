"""
A股尾盘选股策略（约炮式超短隔夜）
策略逻辑：尾盘竞价买入，博取次日冲高，严格2%止盈止损，不持仓过夜
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple


class AStockEveningPicker:
    """A股尾盘选股器"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化选股器
        :param config: 配置参数，可覆盖默认参数
        """
        # 默认选股参数
        self.params = {
            # 价格位置
            'above_ma20': True,          # 股价站在20日均线上
            # 当日涨幅
            'min_daily_change': 3.0,    # 最小当日涨幅 %
            'max_daily_change': 8.0,    # 最大当日涨幅 %
            # 振幅要求
            'min_amplitude': 4.0,       # 最小当日振幅 %
            # 量能要求
            'volume_ratio_5d': 1.5,     # 5日均量倍数
            'min_turnover': 3.0,        # 最小换手率 %
            'max_turnover': 20.0,       # 最大换手率 %
            'min_volume_ratio': 1.2,    # 最小量比
            # 趋势要求
            'up_3d': True,              # 近3天累计上涨
            'ma20_up': True,            # 20日均线向上
            # 排除规则
            'max_consecutive_limit': 2, # 最大连续涨停数
            # 流通市值
            'min_cap': 50e8,            # 最小流通市值 50亿
            'max_cap': 500e8,           # 最大流通市值 500亿
            # 分时形态要求（尾盘半小时拉升）
            'require_late_rally': True,
            'close_near_high': True,    # 收盘价接近当日最高点
            # 每日选股数量限制
            'max_daily_select': 3,
        }
        
        if config:
            self.params.update(config)
    
    def filter_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        根据条件筛选股票
        :param df: 包含每日行情数据的DataFrame，需要包含以下列：
            - code: 股票代码
            - name: 股票名称
            - close: 收盘价
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - volume: 成交量
            - turnover: 换手率 %
            - amount: 成交额
            - ma20: 20日均线
            - ma20_prev: 前一日20日均线
            - change_pct: 当日涨幅 %
            - change_3d: 近3日涨幅 %
            - volume_5d_avg: 5日平均成交量
            - volume_ratio: 量比
            - circulate_cap: 流通市值
            - consecutive_limit: 连续涨停数
            - is_st: 是否ST
            - is_suspended: 是否停牌
            - has_bad_news: 近3天是否有利空
            - late_rally: 尾盘半小时是否拉升（True/False）
        :return: 筛选后的股票DataFrame，按优先级排序
        """
        conditions = pd.Series(True, index=df.index)
        
        # 1. 排除ST、退市、停牌
        conditions = conditions & (~df['is_st']) & (~df['is_suspended'])
        
        # 2. 排除重大利空
        conditions = conditions & (~df['has_bad_news'])
        
        # 3. 流通市值筛选
        conditions = conditions & (df['circulate_cap'] >= self.params['min_cap'])
        conditions = conditions & (df['circulate_cap'] <= self.params['max_cap'])
        
        # 4. 股价站在20日均线上
        if self.params['above_ma20']:
            conditions = conditions & (df['close'] > df['ma20'])
        
        # 5. 20日均线向上
        if self.params['ma20_up']:
            conditions = conditions & (df['ma20'] > df['ma20_prev'])
        
        # 6. 当日涨幅区间
        conditions = conditions & (df['change_pct'] > self.params['min_daily_change'])
        conditions = conditions & (df['change_pct'] < self.params['max_daily_change'])
        
        # 7. 振幅要求
        amplitude = (df['high'] - df['low']) / df['open'] * 100
        conditions = conditions & (amplitude > self.params['min_amplitude'])
        
        # 8. 换手率区间
        conditions = conditions & (df['turnover'] > self.params['min_turnover'])
        conditions = conditions & (df['turnover'] < self.params['max_turnover'])
        
        # 9. 成交量大于5日均量N倍
        conditions = conditions & (df['volume'] > df['volume_5d_avg'] * self.params['volume_ratio_5d'])
        
        # 10. 量比要求
        conditions = conditions & (df['volume_ratio'] > self.params['min_volume_ratio'])
        
        # 11. 近3天累计上涨
        if self.params['up_3d']:
            conditions = conditions & (df['change_3d'] > 0)
        
        # 12. 排除连续涨停过多
        conditions = conditions & (df['consecutive_limit'] <= self.params['max_consecutive_limit'])
        
        # 13. 尾盘拉升要求
        if self.params['require_late_rally']:
            conditions = conditions & df['late_rally']
        
        # 14. 收盘价接近当日最高点
        if self.params['close_near_high']:
            close_to_high = (df['high'] - df['close']) / df['high'] < 0.02  # 价差小于2%
            conditions = conditions & close_to_high
        
        # 应用筛选
        filtered = df[conditions].copy()
        
        # 计算得分，用于排序：优先涨幅适中、量比大、流通市值适中
        filtered['score'] = (
            filtered['volume_ratio'] * 10 +
            filtered['change_pct'] * 0.5 +
            (1 - abs(filtered['circulate_cap'] - 200e8) / 500e8) * 20
        )
        
        # 按得分降序排列
        filtered = filtered.sort_values('score', ascending=False)
        
        # 限制每日选股数量
        if len(filtered) > self.params['max_daily_select']:
            filtered = filtered.head(self.params['max_daily_select'])
        
        return filtered
    
    def check_market_condition(self, index_change: float, vix: Optional[float] = None) -> bool:
        """
        检查大盘是否适合操作
        :param index_change: 大盘当日涨跌幅 %
        :param vix: VIX指数（可选）
        :return: True 可以操作，False 不操作
        """
        # 大盘大跌超过2%不操作
        if index_change <= -2:
            return False
        
        # VIX过高不操作
        if vix is not None and vix > 25:
            return False
        
        return True
    
    def should_buy_today(self, index_change: float, vix: Optional[float] = None) -> bool:
        """判断今日是否应该开仓"""
        return self.check_market_condition(index_change, vix)


class AStockExitRule:
    """A股卖出规则（严格2%止盈止损）"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def check_sell_signal(buy_price: float, current_price: float, 
                         current_time: str, is_next_day: bool = True) -> Tuple[bool, str]:
        """
        检查是否触发卖出信号
        :param buy_price: 买入价格
        :param current_price: 当前价格
        :param current_time: 当前时间 (HH:MM)
        :param is_next_day: 是否是买入次日
        :return: (是否卖出, 卖出原因)
        """
        change_pct = (current_price - buy_price) / buy_price * 100
        
        # 止盈：涨幅达到2%
        if change_pct >= 2:
            return True, f"止盈：涨幅达到{change_pct:.2f}%"
        
        # 止损：跌幅达到2%
        if change_pct <= -2:
            return True, f"止损：跌幅达到{change_pct:.2f}%"
        
        # 次日14:30之后，无论盈亏都卖出
        if is_next_day:
            hour, minute = map(int, current_time.split(':'))
            if hour >= 14 and minute >= 30:
                return True, f"尾盘清仓：{current_time}，未触及止盈止损"
        
        return False, ""
    
    @staticmethod
    def check_open_gap_down(buy_price: float, open_price: float) -> Tuple[bool, str]:
        """
        检查开盘是否直接低开超过2%
        :param buy_price: 买入价格
        :param open_price: 次日开盘价
        :return: (是否卖出, 卖出原因)
        """
        change_pct = (open_price - buy_price) / buy_price * 100
        if change_pct <= -2:
            return True, f"开盘低开止损：低开{change_pct:.2f}%"
        return False, ""
