"""
使用示例
展示如何使用OpenClaw量化框架进行决策和生成交易信号
"""

import sys
import os
sys.path.insert(0, os.path.abspath('../src'))

import pandas as pd
from quant_framework import (
    AStockEveningPicker,
    AStockExitRule,
    RiskManager,
    EventDetector,
    OptionStrategySelector,
    FMZClient,
    TradingSignal,
)


def example_a_stock_selection():
    """A股尾盘选股示例"""
    print("=== A股尾盘选股示例 ===")
    
    # 初始化选股器
    picker = AStockEveningPicker()
    
    # 模拟行情数据
    data = [
        {
            'code': '000001',
            'name': '平安银行',
            'close': 15.2,
            'open': 14.8,
            'high': 15.3,
            'low': 14.7,
            'volume': 1000000,
            'turnover': 5.2,
            'change_pct': 4.5,
            'change_3d': 6.2,
            'ma20': 14.6,
            'ma20_prev': 14.5,
            'volume_5d_avg': 600000,
            'volume_ratio': 1.6,
            'circulate_cap': 200e8,
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        },
        {
            'code': '600000',
            'name': '浦发银行',
            'close': 8.8,
            'open': 8.5,
            'high': 8.9,
            'low': 8.4,
            'volume': 800000,
            'turnover': 4.1,
            'change_pct': 3.5,
            'change_3d': 4.2,
            'ma20': 8.5,
            'ma20_prev': 8.45,
            'volume_5d_avg': 500000,
            'volume_ratio': 1.5,
            'circulate_cap': 180e8,
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        }
    ]
    
    df = pd.DataFrame(data)
    result = picker.filter_stocks(df)
    
    print(f"筛选结果：共选出{len(result)}只股票")
    print(result[['code', 'name', 'change_pct', 'volume_ratio', 'score']])
    
    # 检查大盘条件
    can_trade = picker.should_buy_today(index_change=0.5, vix=15)
    print(f"\n今日大盘状态：{'适合交易' if can_trade else'不适合交易'}")
    
    return result


def example_risk_check():
    """风控检查示例"""
    print("\n=== 风控检查示例 ===")
    
    # 初始化风控管理器，总资金100万
    risk = RiskManager(total_capital=1_000_000)
    
    # 计算可买数量
    current_price = 15.2
    shares = risk.calculate_position_size(current_price)
    print(f"股价{current_price}，单票最大10%仓位，可买：{shares}股")
    
    # 检查止损
    buy_price = 15.2
    current_price = 14.85
    trigger, reason = risk.check_a_stock_stop_loss(buy_price, current_price)
    print(f"买入价{buy_price}, 当前价{current_price}: {'触发止损' if trigger else '未触发止损'} ({reason})")
    
    return shares


def example_event_driven():
    """港股美股事件驱动示例"""
    print("\n=== 港股美股事件驱动期权策略示例 ===")
    
    detector = EventDetector()
    selector = OptionStrategySelector()
    
    # 财报超预期事件
    event = {'type': 'earnings_beat'}
    triggered, event_type = detector.detect_event(
        event,
        price_change=4.2,
        daily_volume=50_000_000,
        market_cap=50e9,
        has_option_liquidity=True,
        market='US'
    )
    
    print(f"事件检测：{'触发有效事件' if triggered else '未触发'}，类型：{event_type}")
    
    if triggered:
        strategy = selector.select_strategy(
            event_type,
            current_price=100,
            volatility=25
        )
        
        print(f"\n选择策略：{strategy['strategy'].value}")
        print(f"合约规则：{strategy['contract_rules']}")
        print(f"退出规则：{strategy['exit_rules']}")
    
    return strategy


def example_fmz_api():
    """FMZ API接口示例"""
    print("\n=== FMZ API接口示例 ===")
    
    client = FMZClient()
    
    # 创建A股买入信号
    signal = client.create_trading_signal(
        strategy='a股隔夜',
        action='buy',
        symbol='000001',
        market='CN',
        price=15.2,
        quantity=6500,
        stop_loss=15.2 * 0.98,
        take_profit=15.2 * 1.02,
        expire_time='2026-03-17T15:00:00',
        remark='尾盘选股买入'
    )
    
    print("生成的交易信号JSON：")
    print(signal.to_json())
    
    # 解析验证
    parsed = TradingSignal.from_json(signal.to_json())
    print(f"\n解析后验证：symbol={parsed.symbol}, action={parsed.action.value}")


if __name__ == '__main__':
    example_a_stock_selection()
    example_risk_check()
    example_event_driven()
    example_fmz_api()
    print("\n✅ 所有示例运行完成")
