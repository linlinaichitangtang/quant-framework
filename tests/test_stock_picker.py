"""
单元测试：A股尾盘选股模块
测试选股逻辑是否正确
"""

import pytest
import pandas as pd
from src.strategies.a_stock_evening import AStockEveningPicker, AStockExitRule


class TestAStockEveningPicker:
    """测试A股尾盘选股器"""

    def test_default_init(self):
        """测试默认初始化"""
        picker = AStockEveningPicker()
        assert picker.params is not None
        assert picker.params['max_daily_select'] == 3
        assert picker.params['min_daily_change'] == 3.0

    def test_custom_config_override(self):
        """测试自定义配置覆盖默认参数"""
        picker = AStockEveningPicker({'max_daily_select': 5, 'min_daily_change': 2.0})
        assert picker.params['max_daily_select'] == 5
        assert picker.params['min_daily_change'] == 2.0
        # 其他默认参数保留
        assert picker.params['above_ma20'] is True

    def test_filter_all_pass(self, sample_stock_data):
        """测试符合条件的股票能够通过筛选"""
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        # 预期通过：000001, 000002 -> 共2只
        assert len(filtered) == 2
        assert '000001' in list(filtered['code'])
        assert '000002' in list(filtered['code'])

    def test_filter_exclude_st(self, sample_stock_data):
        """测试正确排除ST股票"""
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        assert '000003' not in list(filtered['code'])

    def test_filter_exclude_bad_news(self, sample_stock_data):
        """测试正确排除利空股票"""
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        assert '000006' not in list(filtered['code'])

    def test_filter_min_daily_change(self, sample_stock_data):
        """测试涨幅下限筛选"""
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        # 000004涨幅1% < 3%，应该被排除
        assert '000004' not in list(filtered['code'])

    def test_filter_circulate_cap_range(self, sample_stock_data):
        """测试流通市值范围筛选"""
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        # 000005流通市值600亿 > 500亿上限，应该被排除
        assert '000005' not in list(filtered['code'])

    def test_filter_ma20_up(self, sample_stock_data):
        """测试20日均线向上要求"""
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        # 000007均线向下，应该被排除
        assert '000007' not in list(filtered['code'])

    def test_filter_late_rally(self, sample_stock_data):
        """测试尾盘拉升要求"""
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(sample_stock_data)
        # 000008尾盘未拉升，应该被排除
        assert '000008' not in list(filtered['code'])

    def test_disable_above_ma20_condition(self, sample_stock_data):
        """测试禁用股价站在均线上条件"""
        # 创建一只收盘价在均线下方的股票，收盘价接近最高（价差小于2%）
        df = sample_stock_data.copy()
        df.loc[len(df)] = {
            'code': '000009',
            'name': '均线下方',
            'close': 9.68,  # close near high (9.7)
            'open': 9.3,
            'high': 9.7,
            'low': 9.2,
            'volume': 1000000,
            'turnover': 5.0,
            'amount': 9500000,
            'ma20': 10.0,
            'ma20_prev': 9.9,
            'change_pct': 4.3,
            'change_3d': 3.0,
            'volume_5d_avg': 600000,
            'volume_ratio': 1.67,
            'circulate_cap': 100e8,
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        }
        # 默认配置启用above_ma20，应该被排除（因为close 9.5 < ma20 10.0）
        picker = AStockEveningPicker()
        filtered = picker.filter_stocks(df)
        assert '000009' not in list(filtered['code'])
        
        # 同时满足ma20_up也满足，只禁用above_ma20条件
        # 000009的ma20(10.0) > ma20_prev(9.9)，所以ma20_up条件通过
        # 只禁用above_ma20，所以应该通过
        picker3 = AStockEveningPicker({'above_ma20': False, 'max_daily_select': 10})
        filtered3 = picker3.filter_stocks(df)
        codes = list(filtered3['code'])
        # 因为ma20_up满足，所以应该在列表中
        assert '000009' in codes

    def test_max_daily_select_limit(self, sample_stock_data):
        """测试每日选股数量限制"""
        # 创建更多符合条件的股票
        df = sample_stock_data.copy()
        for i in range(10, 15):
            df.loc[len(df)] = {
                'code': f'0000{i}',
                'name': f'测试{i}',
                'close': 10.0 + i * 0.1,
                'open': 9.5 + i * 0.1,
                'high': 10.2 + i * 0.1,
                'low': 9.4 + i * 0.1,
                'volume': 1000000,
                'turnover': 5.0,
                'amount': 10000000,
                'ma20': 9.8 + i * 0.1,
                'ma20_prev': 9.7 + i * 0.1,
                'change_pct': 5.0,
                'change_3d': 3.0,
                'volume_5d_avg': 600000,
                'volume_ratio': 1.67 + i * 0.01,
                'circulate_cap': 100e8,
                'consecutive_limit': 0,
                'is_st': False,
                'is_suspended': False,
                'has_bad_news': False,
                'late_rally': True,
            }
        picker = AStockEveningPicker()  # 默认限制3只
        filtered = picker.filter_stocks(df)
        assert len(filtered) == 3  # 只保留前3名得分最高的

    def test_check_market_condition_normal(self):
        """测试正常市场条件判断"""
        picker = AStockEveningPicker()
        # 大盘涨，可以操作
        assert picker.check_market_condition(1.0) is True
        # 大盘跌0.5% > -2%，可以操作
        assert picker.check_market_condition(-0.5) is True

    def test_check_market_condition_bad(self):
        """测试恶劣市场条件判断"""
        picker = AStockEveningPicker()
        # 大盘跌超过2%，不操作
        assert picker.check_market_condition(-2.5) is False
        # VIX超过25，不操作
        assert picker.check_market_condition(0, vix=26) is False
        # VIX正常，可以操作
        assert picker.check_market_condition(0, vix=20) is True

    def test_should_buy_today(self):
        """测试今日是否开仓判断"""
        picker = AStockEveningPicker()
        assert picker.should_buy_today(1.0) is True
        assert picker.should_buy_today(-2.5) is False


class TestAStockExitRule:
    """测试A股卖出规则"""

    def test_take_profit_trigger(self):
        """测试触发止盈"""
        rule = AStockExitRule()
        # 买入10元，涨到10.3元，涨幅3% > 2%，触发止盈
        should_sell, reason = rule.check_sell_signal(10.0, 10.3, "10:00", True)
        assert should_sell is True
        assert "止盈" in reason
        assert "3.00%" in reason

    def test_stop_loss_trigger(self):
        """测试触发止损"""
        rule = AStockExitRule()
        # 买入10元，跌到9.7元，跌幅3% < -2%，触发止损
        should_sell, reason = rule.check_sell_signal(10.0, 9.7, "10:00", True)
        assert should_sell is True
        assert "止损" in reason
        assert "-3.00%" in reason

    def test_no_signal_hold(self):
        """测试未触发信号，继续持有"""
        rule = AStockExitRule()
        # 涨幅1%，在-2% ~ 2%之间，不触发
        should_sell, reason = rule.check_sell_signal(10.0, 10.1, "10:00", True)
        assert should_sell is False
        assert reason == ""

    def test_time_based_exit_next_day_after_1430(self):
        """测试次日尾盘强制清仓"""
        rule = AStockExitRule()
        # 次日14:30，无论盈亏都卖出
        should_sell, reason = rule.check_sell_signal(10.0, 10.05, "14:30", True)
        assert should_sell is True
        assert "尾盘清仓" in reason

        # 次日14:29，不到时间不卖出
        should_sell, reason = rule.check_sell_signal(10.0, 10.05, "14:29", True)
        assert should_sell is False

    def test_same_day_not_forced_exit(self):
        """测试买入当日不强制卖出"""
        rule = AStockExitRule()
        # 当日14:30，不强制卖出
        should_sell, reason = rule.check_sell_signal(10.0, 10.05, "14:30", False)
        assert should_sell is False

    def test_open_gap_down_trigger(self):
        """测试开盘低开触发止损"""
        rule = AStockExitRule()
        # 买入10元，开盘9.7元，低开-3%，触发止损
        should_sell, reason = rule.check_open_gap_down(10.0, 9.7)
        assert should_sell is True
        assert "开盘低开止损" in reason

    def test_open_gap_down_not_trigger(self):
        """测试开盘低开未达阈值不触发"""
        rule = AStockExitRule()
        # 低开-1%，不触发
        should_sell, reason = rule.check_open_gap_down(10.0, 9.9)
        assert should_sell is False
