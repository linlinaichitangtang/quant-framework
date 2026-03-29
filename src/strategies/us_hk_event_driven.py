"""
港股美股事件驱动期权策略
策略逻辑：基于财报/新闻事件驱动，选择合适期权策略，持有数天到数周
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple
import pandas as pd


class EventType(Enum):
    """事件类型"""
    EARNINGS_BEAT = "earnings_beat"        # 财报超预期
    EARNINGS_MISS = "earnings_miss"        # 财报不及预期
    POLICY_POSITIVE = "policy_positive"    # 重大政策利好
    PRODUCT_LAUNCH = "product_launch"      # 重大产品发布
    NEGATIVE_NEWS = "negative_news"        # 黑天鹅负面事件
    EARNINGS_UNCERTAIN = "earnings_uncertain"  # 财报前，方向不确定


class OptionStrategy(Enum):
    """期权策略类型"""
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    BULL_SPREAD = "bull_spread"
    BEAR_SPREAD = "bear_spread"


class EventDetector:
    """事件检测器"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.params = {
            # 财报超预期/不及预期阈值
            'earnings_beat_threshold': 3.0,     # 高开>3%认为超预期
            'earnings_miss_threshold': -3.0,    # 低开<-3%认为不及预期
            # 政策/产品阈值
            'positive_event_threshold': 2.0,    # 上涨>2%确认利好
            # 黑天鹅阈值
            'negative_event_threshold': -5.0,   # 下跌>5%确认负面
            # 流动性要求
            'min_daily_volume_us': 10_000_000,  # 美股日均成交量 1000万美元
            'min_daily_volume_hk': 10_000_000,  # 港股日均成交量 1000万港币
            'min_market_cap': 2_000_000_000,    # 最小市值 20亿美元
            'max_option_spread': 0.5,           # 期权最大买卖价差
        }
        if config:
            self.params.update(config)
    
    def detect_event(self, 
                    event_info: Dict, 
                    price_change: float,
                    daily_volume: float,
                    market_cap: float,
                    has_option_liquidity: bool,
                    market: str = 'US') -> Tuple[bool, Optional[EventType]]:
        """
        检测是否触发有效事件
        :param event_info: 事件信息，包含type事件类型
        :param price_change: 事件发生后价格变动百分比
        :param daily_volume: 日均成交量
        :param market_cap: 市值
        :param has_option_liquidity: 是否有充足期权流动性
        :param market: 市场 US/HK
        :return: (是否触发事件, 事件类型)
        """
        # 先检查流动性和市值要求
        if market_cap < self.params['min_market_cap']:
            return False, None
        
        min_vol = (self.params['min_daily_volume_us'] if market == 'US' 
                  else self.params['min_daily_volume_hk'])
        if daily_volume < min_vol:
            return False, None
        
        if not has_option_liquidity:
            return False, None
        
        event_type = EventType(event_info['type'])
        
        # 根据事件类型和价格变动判断是否有效触发
        if event_type == EventType.EARNINGS_BEAT:
            if price_change >= self.params['earnings_beat_threshold']:
                return True, event_type
        elif event_type == EventType.EARNINGS_MISS:
            if price_change <= self.params['earnings_miss_threshold']:
                return True, event_type
        elif event_type in [EventType.POLICY_POSITIVE, EventType.PRODUCT_LAUNCH]:
            if price_change >= self.params['positive_event_threshold']:
                return True, event_type
        elif event_type == EventType.NEGATIVE_NEWS:
            if price_change <= self.params['negative_event_threshold']:
                return True, event_type
        elif event_type == EventType.EARNINGS_UNCERTAIN:
            # 财报前不确定方向，波动率即将放大，直接触发
            return True, event_type
        
        return False, None


class OptionStrategySelector:
    """期权策略选择器"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.params = {
            'default_expire_days': 28,     # 默认到期天数
            'earnings_expire_days': 14,   # 财报跨式到期天数
            'max_position_pct': 10,       # 单策略最大仓位占比 %
            'stop_loss_pct': 50,          # 止损：权利金亏损百分比 %
            'take_profit_pct': 50,        # 止盈：盈利百分比 %
            'straddle_stop_loss_pct': 30, # 跨式止损百分比
        }
        if config:
            self.params.update(config)
    
    def select_strategy(self, event_type: EventType, 
                       current_price: float,
                       volatility: float = None,
                       expected_move: Optional[str] = None) -> Dict:
        """
        根据事件类型选择期权策略
        :param event_type: 事件类型
        :param current_price: 当前股价
        :param volatility: 当前波动率（可选）
        :param expected_move: 预期方向 'up'/'down'/None
        :return: 策略配置字典
        """
        result = {
            'strategy': None,
            'contract_rules': {},
            'entry_rules': {},
            'exit_rules': {},
            'position_limit': self.params['max_position_pct'],
            'stop_loss_pct': self.params['stop_loss_pct'],
        }
        
        if event_type == EventType.EARNINGS_BEAT or \
           event_type == EventType.POLICY_POSITIVE or \
           event_type == EventType.PRODUCT_LAUNCH:
            # 明确看多，选择Long Call
            if volatility is not None and volatility > 30:
                # 波动率高，用牛市价差降低成本
                result['strategy'] = OptionStrategy.BULL_SPREAD
                result['contract_rules'] = {
                    'buy_strike': current_price,  # 买入平值Call
                    'sell_strike': current_price * 1.05,  # 卖出虚值5%Call
                    'expire_days': self.params['default_expire_days'],
                }
            else:
                result['strategy'] = OptionStrategy.LONG_CALL
                result['contract_rules'] = {
                    'strike_type': 'at_the_money',  # 平值或轻微实值
                    'target_strike': current_price,
                    'expire_days': self.params['default_expire_days'],
                }
            result['exit_rules'] = {
                'take_profit_pct': 100,  # 翻倍止盈
                'stop_loss_pct': self.params['stop_loss_pct'],
                'close_before_expire_days': 7,
            }
        
        elif event_type == EventType.EARNINGS_MISS or \
             event_type == EventType.NEGATIVE_NEWS:
            # 明确看空，选择Long Put
            if volatility is not None and volatility > 30:
                result['strategy'] = OptionStrategy.BEAR_SPREAD
                result['contract_rules'] = {
                    'buy_strike': current_price,  # 买入平值Put
                    'sell_strike': current_price * 0.95,  # 卖出虚值5%Put
                    'expire_days': self.params['default_expire_days'],
                }
            else:
                result['strategy'] = OptionStrategy.LONG_PUT
                result['contract_rules'] = {
                    'strike_type': 'at_the_money',
                    'target_strike': current_price,
                    'expire_days': self.params['default_expire_days'],
                }
            result['exit_rules'] = {
                'take_profit_pct': 100,
                'stop_loss_pct': self.params['stop_loss_pct'],
                'close_before_expire_days': 7,
            }
        
        elif event_type == EventType.EARNINGS_UNCERTAIN:
            # 财报前方向不确定，波动率放大，选择跨式或宽跨
            if expected_move is None:
                # 完全不确定，用跨式
                result['strategy'] = OptionStrategy.STRADDLE
                result['contract_rules'] = {
                    'call_strike': current_price,
                    'put_strike': current_price,
                    'expire_days': self.params['earnings_expire_days'],
                }
                result['position_ratio'] = {'call': 0.5, 'put': 0.5}
                result['exit_rules'] = {
                    'take_profit_pct': 50,
                    'stop_loss_pct': self.params['straddle_stop_loss_pct'],
                    'close_after_earnings': True,
                }
                result['stop_loss_pct'] = self.params['straddle_stop_loss_pct']
            else:
                # 有方向倾向但不确定，用宽跨降低成本
                result['strategy'] = OptionStrategy.STRANGLE
                result['contract_rules'] = {
                    'call_strike': current_price * 1.05,
                    'put_strike': current_price * 0.95,
                    'expire_days': self.params['earnings_expire_days'],
                }
                result['position_ratio'] = {'call': 0.5, 'put': 0.5}
                result['exit_rules'] = {
                    'take_profit_pct': 100,
                    'stop_loss_pct': self.params['straddle_stop_loss_pct'],
                    'close_after_earnings': True,
                }
                result['stop_loss_pct'] = self.params['straddle_stop_loss_pct']
        
        return result
    
    def check_exit_signal(self, strategy: OptionStrategy, 
                         entry_premium: float,
                         current_premium: float) -> Tuple[bool, str]:
        """
        检查是否触发退出信号
        :param strategy: 期权策略
        :param entry_premium: 建仓时权利金总价
        :param current_premium: 当前权利金总价
        :return: (是否退出, 退出原因)
        """
        change_pct = (current_premium - entry_premium) / entry_premium * 100
        
        if strategy in [OptionStrategy.LONG_CALL, OptionStrategy.LONG_PUT]:
            if change_pct >= 100:
                return True, f"止盈：权利金翻倍，盈利{change_pct:.1f}%"
            if change_pct <= -self.params['stop_loss_pct']:
                return True, f"止损：权利金亏损{self.params['stop_loss_pct']}%"
        
        elif strategy in [OptionStrategy.STRADDLE, OptionStrategy.STRANGLE]:
            if change_pct >= 50:
                return True, f"止盈：整体盈利{change_pct:.1f}%"
            if change_pct <= -self.params['straddle_stop_loss_pct']:
                return True, f"止损：整体亏损{self.params['straddle_stop_loss_pct']}%"
        
        elif strategy in [OptionStrategy.BULL_SPREAD, OptionStrategy.BEAR_SPREAD]:
            if change_pct >= 50:
                return True, f"止盈：价差盈利{change_pct:.1f}%"
            if change_pct <= -30:
                return True, f"止损：价差亏损30%"
        
        return False, ""
