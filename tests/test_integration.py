"""
集成测试：完整流程验证
选股 → 风控检查 → 生成交易信号
"""

import pytest
import pandas as pd
from src.strategies.a_stock_evening import AStockEveningPicker
from src.risk.risk_manager import RiskManager
from src.api.fmz_api import FMZClient, ActionType, MarketType


class TestFullWorkflow:
    """完整流程集成测试"""

    def test_full_buy_workflow(self, sample_stock_data):
        """测试完整买入流程：选股 → 风控检查 → 生成交易信号"""
        # 1. 选股阶段
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        assert len(filtered) == 2
        
        # 检查大盘条件，确认可以开仓
        can_buy = picker.should_buy_today(index_change=0.5)
        assert can_buy is True
        
        # 获取排名第一的股票
        top_stock = filtered.iloc[0]
        assert top_stock['code'] in ['000001', '000002']

        # 2. 风控计算可买仓位
        total_capital = 1000000  # 100万总资金
        rm = RiskManager(total_capital)
        shares = rm.calculate_position_size(top_stock['close'])
        assert shares > 0
        assert shares % 100 == 0  # 必须是100整数倍
        
        # 3. 风控检查新仓位
        result, reason = rm.check_a_stock_position({}, shares, top_stock['close'])
        assert result is True, f"风控检查应该通过，但失败了: {reason}"
        
        # 检查整体市场风控
        global_ok, global_reason = rm.check_market_global_condition(vix=15, vix_daily_change=1, consecutive_loss_days=0)
        assert global_ok is True, f"市场风控应该通过，但失败了: {global_reason}"

        # 4. 创建FMZ交易信号
        client = FMZClient()
        signal = client.create_trading_signal(
            strategy="a股隔夜",
            action="buy",
            symbol=top_stock['code'],
            market="CN",
            price=top_stock['close'],
            quantity=shares
        )
        
        # 验证信号格式
        assert signal.strategy == "a股隔夜"
        assert signal.action == ActionType.BUY
        assert signal.market == MarketType.CN
        assert signal.quantity == shares
        
        # 序列化为JSON，确认可以正常输出
        json_str = signal.to_json()
        assert len(json_str) > 0
        
        print(f"\n[集成测试] 完整流程验证通过")
        print(f"  选出股票: {top_stock['code']} {top_stock['name']}")
        print(f"  计算可买: {shares} 股")
        print(f"  交易信号生成成功")

    def test_full_workflow_rejected_by_risk(self, sample_stock_data):
        """测试完整流程被风控拦截"""
        # 1. 选股
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        assert len(filtered) == 2
        top_stock = filtered.iloc[0]

        # 2. 风控设置非常严格，单票上限只有1%，总资金很少
        total_capital = 10000  # 总资金1万
        rm = RiskManager(total_capital, {'a_stock_max_single_pct': 1.0})
        # 尝试买入1000股 @ 10.5元 = 10500元 > 100元上限（1% * 1万）
        result, reason = rm.check_a_stock_position({}, 1000, 10.5)
        assert result is False
        assert "单票仓位超限" in reason

    def test_full_workflow_rejected_by_market_condition(self, sample_stock_data):
        """测试大盘不好，不允许开仓"""
        picker = AStockEveningPicker()
        # 大盘跌3%，不应该开仓
        can_buy = picker.should_buy_today(index_change=-3.0)
        assert can_buy is False

    def test_stop_loss_workflow(self):
        """测试止损完整流程"""
        # 1. 初始化
        rm = RiskManager(1000000, {'a_stock_stop_loss_pct': 2.0})
        buy_price = 10.0
        
        # 2. 检查止损
        current_price = 9.78  # 亏损2.2%
        should_stop, reason = rm.check_a_stock_stop_loss(buy_price, current_price)
        assert should_stop is True
        
        # 3. 创建卖出信号
        client = FMZClient()
        signal = client.create_trading_signal(
            strategy="a股隔夜",
            action="sell",
            symbol="000001",
            market="CN",
            quantity=1000,
            price=current_price,
            remark=reason
        )
        assert signal.action == ActionType.SELL
        assert signal.remark == reason
        
        json_str = signal.to_json()
        assert len(json_str) > 0

    def test_global_risk_pause_consecutive_loss(self):
        """测试连续亏损触发全局风控暂停"""
        rm = RiskManager(1000000, {'consecutive_loss_days_pause': 3})
        ok, reason = rm.check_market_global_condition(15, 0, consecutive_loss_days=3)
        assert ok is False
        assert "连续3日亏损" in reason


class TestOptionWorkflow:
    """期权策略完整流程集成测试"""

    def test_option_full_workflow(self):
        """测试期权策略完整流程"""
        # 1. 初始化风控
        total_capital = 1000000
        rm = RiskManager(total_capital)
        
        # 2. 检查期权仓位
        ok, reason = rm.check_option_position({}, 20000)  # 2万权利金
        assert ok is True, reason
        
        # 3. 生成交易信号
        client = FMZClient()
        signal = client.create_trading_signal(
            strategy="美股事件驱动",
            action="buy",
            symbol="AAPL240119C180000",
            market="US",
            quantity=10,
            price=2.0,
            remark="财报Long Call"
        )
        assert signal.market == MarketType.US
        assert signal.strategy == "美股事件驱动"
        json_str = signal.to_json()
        assert len(json_str) > 0

    def test_option_overall_limit(self):
        """测试期权总仓位超限"""
        total_capital = 1000000  # 总权利金上限20% → 20万
        rm = RiskManager(total_capital)
        current = {
            'opt1': {'premium_total': 80000},
            'opt2': {'premium_total': 70000},
            'opt3': {'premium_total': 40000},
        }
        # 新增2万 → 累计21万 > 20万
        ok, reason = rm.check_option_position(current, 20000)
        assert ok is False
        assert "期权总权利金超限" in reason
