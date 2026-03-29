"""
风控管理器
实现仓位限制、止损规则、整体市场风控等规则
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd


class RiskManager:
    """综合风控管理器"""
    
    def __init__(self, total_capital: float, config: Optional[Dict] = None):
        """
        初始化风控管理器
        :param total_capital: 账户总资金
        :param config: 配置参数
        """
        self.total_capital = total_capital
        
        # 默认风控参数
        self.params = {
            # A股风控
            'a_stock_max_single_pct': 10.0,    # 单票最大仓位 %
            'a_stock_max_daily_open': 5,       # 每日新开仓最大数量
            'a_stock_max_total_pct': 80.0,     # 总持仓最大占比 %
            'a_stock_stop_loss_pct': 2.0,      # 强制止损线 %
            
            # 期权风控
            'option_max_single_loss_pct': 3.0, # 单个策略最大亏损占总资金 %
            'option_max_total_premium_pct': 20.0, # 总权利金最大占比 %
            'option_stop_loss_pct': 50.0,      # 权利金止损 %
            
            # 整体市场风控
            'vix_pause_level': 25,             # VIX暂停开仓水平
            'vix_single_day_rise': 20,         # VIX单日涨幅暂停开仓 %
            'max_sector_pct': 30.0,            # 单一板块最大持仓占比 %
            'consecutive_loss_days_pause': 3,  # 连续亏损天数暂停开仓
        }
        
        if config:
            self.params.update(config)
    
    def check_a_stock_position(self, current_positions: Dict, new_quantity: int, 
                               new_price: float) -> Tuple[bool, str]:
        """
        检查A股新仓位是否符合风控规则
        :param current_positions: 当前持仓 {symbol: {quantity, cost, ...}}
        :param new_quantity: 新买入数量
        :param new_price: 新买入价格
        :return: (是否通过, 原因)
        """
        new_value = new_quantity * new_price
        max_single_value = self.total_capital * self.params['a_stock_max_single_pct'] / 100
        
        if new_value > max_single_value:
            return False, f"单票仓位超限：计划市值{new_value:.0f}，最大允许{max_single_value:.0f}"
        
        # 计算当前总持仓
        total_value = sum(p['quantity'] * p['current_price'] for p in current_positions.values())
        new_total = total_value + new_value
        max_total = self.total_capital * self.params['a_stock_max_total_pct'] / 100
        
        if new_total > max_total:
            return False, f"总仓位超限：当前{new_total:.0f}，最大允许{max_total:.0f}"
        
        # 计算新开仓数量
        current_open_count = sum(1 for p in current_positions.values() if p['is_today_open'])
        if current_open_count >= self.params['a_stock_max_daily_open']:
            return False, f"每日新开仓数量超限：已开{current_open_count}，最大允许{self.params['a_stock_max_daily_open']}"
        
        return True, "通过"
    
    def check_option_position(self, current_option_positions: Dict, 
                             new_premium_total: float) -> Tuple[bool, str]:
        """
        检查期权新仓位是否符合风控规则
        :param current_option_positions: 当前期权持仓
        :param new_premium_total: 新策略权利金总价
        :return: (是否通过, 原因)
        """
        max_single_loss = self.total_capital * self.params['option_max_single_loss_pct'] / 100
        
        if new_premium_total > max_single_loss:
            return False, f"期权单策略最大亏损超限：计划权利金{new_premium_total:.0f}，最大允许{max_single_loss:.0f}"
        
        total_premium = sum(p['premium_total'] for p in current_option_positions.values())
        new_total = total_premium + new_premium_total
        max_total = self.total_capital * self.params['option_max_total_premium_pct'] / 100
        
        if new_total > max_total:
            return False, f"期权总权利金超限：当前{new_total:.0f}，最大允许{max_total:.0f}"
        
        if len(current_option_positions) >= 3:
            return False, "同时持有事件不超过3个"
        
        return True, "通过"
    
    def check_market_global_condition(self, vix: Optional[float], 
                                     vix_daily_change: Optional[float],
                                     consecutive_loss_days: int) -> Tuple[bool, str]:
        """
        检查整体市场风控
        :param vix: 当前VIX指数
        :param vix_daily_change: VIX单日涨跌幅 %
        :param consecutive_loss_days: 连续亏损天数
        :return: (是否允许开新仓, 原因)
        """
        if vix is not None and vix >= self.params['vix_pause_level']:
            return False, f"VIX恐慌指数{vix:.1f}超过阈值{self.params['vix_pause_level']}，暂停新开仓"
        
        if vix_daily_change is not None and vix_daily_change >= self.params['vix_single_day_rise']:
            return False, f"VIX单日上涨{vix_daily_change:.1f}%超过阈值，暂停新开仓"
        
        if consecutive_loss_days >= self.params['consecutive_loss_days_pause']:
            return False, f"连续{consecutive_loss_days}日亏损，暂停新开仓"
        
        return True, "通过"
    
    def check_sector_concentration(self, positions: Dict) -> Tuple[bool, str]:
        """
        检查板块集中度
        :param positions: 当前持仓，包含sector信息
        :return: (是否通过, 原因)
        """
        total_value = self.total_capital
        sector_value: Dict[str, float] = {}
        
        for pos in positions.values():
            sector = pos.get('sector', 'unknown')
            value = pos['quantity'] * pos['current_price']
            sector_value[sector] = sector_value.get(sector, 0) + value
        
        for sector, value in sector_value.items():
            pct = value / total_value * 100
            if pct > self.params['max_sector_pct']:
                return False, f"板块{sector}持仓占比{pct:.1f}%超过限制{self.params['max_sector_pct']}%"
        
        return True, "通过"
    
    def check_a_stock_stop_loss(self, buy_price: float, current_price: float) -> Tuple[bool, str]:
        """检查A股是否触发强制止损"""
        change_pct = (current_price - buy_price) / buy_price * 100
        if change_pct <= -self.params['a_stock_stop_loss_pct']:
            return True, f"触发强制止损：亏损{change_pct:.2f}%"
        return False, ""
    
    def check_option_stop_loss(self, entry_premium: float, current_premium: float) -> Tuple[bool, str]:
        """检查期权是否触发止损"""
        change_pct = (current_premium - entry_premium) / entry_premium * 100
        if change_pct <= -self.params['option_stop_loss_pct']:
            return True, f"期权权利金亏损{change_pct:.1f}%触发止损"
        return False, ""
    
    def calculate_position_size(self, current_price: float, max_pct: Optional[float] = None) -> int:
        """
        计算可买数量（A股）
        :param current_price: 当前价格
        :param max_pct: 最大仓位占比，默认使用配置值
        :return: 可买整数股数（100的倍数）
        """
        if max_pct is None:
            max_pct = self.params['a_stock_max_single_pct']
        
        max_value = self.total_capital * max_pct / 100
        shares = int(max_value / current_price / 100) * 100
        return shares
