"""
单元测试：风控模块
测试各种风控规则是否正确执行
"""

import pytest
from src.risk.risk_manager import RiskManager


class TestRiskManagerAStock:
    """测试A股风控规则"""

    def test_init_with_default_params(self):
        """测试默认参数初始化"""
        rm = RiskManager(total_capital=1000000)  # 100万总资金
        assert rm.total_capital == 1000000
        assert rm.params['a_stock_max_single_pct'] == 10.0
        assert rm.params['a_stock_max_total_pct'] == 80.0

    def test_custom_config_override(self):
        """测试自定义配置覆盖"""
        rm = RiskManager(1000000, {'a_stock_max_single_pct': 15.0, 'a_stock_max_daily_open': 3})
        assert rm.params['a_stock_max_single_pct'] == 15.0
        assert rm.params['a_stock_max_daily_open'] == 3

    def test_empty_position_allow_new(self, empty_positions):
        """测试空仓允许新开仓"""
        rm = RiskManager(1000000)  # 100万
        # 买入1000股，10元/股 → 市值1万，占总资金1% < 10%上限
        result, reason = rm.check_a_stock_position(empty_positions, 1000, 10.0)
        assert result is True
        assert "通过" in reason

    def test_single_position_over_limit(self, empty_positions):
        """测试单票仓位超限"""
        rm = RiskManager(1000000)  # 100万，单票最大10% → 10万
        # 买入20000股，10元/股 → 市值20万 > 10万上限
        result, reason = rm.check_a_stock_position(empty_positions, 20000, 10.0)
        assert result is False
        assert "单票仓位超限" in reason

    def test_total_position_over_limit(self, sample_positions):
        """测试总仓位超限"""
        # 当前持仓: 1000*10.5 + 500*19.8 = 10500 + 9900 = 20400
        # 总资金25000，总仓位上限80% → 20000
        rm = RiskManager(25000)  # 2.5万总资金
        # 新增100股 * 10元 = 1000 → 总仓位21400 > 20000
        result, reason = rm.check_a_stock_position(sample_positions, 100, 10.0)
        assert result is False
        assert "总仓位超限" in reason

    def test_daily_open_count_over_limit(self):
        """测试每日新开仓数量超限"""
        rm = RiskManager(1000000, {'a_stock_max_daily_open': 2})
        # 当前已有2个今日新开仓
        positions = {
            '000001': {'quantity': 1000, 'current_price': 10, 'is_today_open': True},
            '000002': {'quantity': 500, 'current_price': 20, 'is_today_open': True},
        }
        # 再开一个 → 超限
        result, reason = rm.check_a_stock_position(positions, 100, 10.0)
        assert result is False
        assert "每日新开仓数量超限" in reason

    def test_calculate_position_size(self):
        """测试计算可买数量"""
        rm = RiskManager(1000000)  # 100万，单票最大10% → 10万
        # 当前价格10元 → 10万 / 10 = 10000股 → 10000是100倍数
        shares = rm.calculate_position_size(10.0)
        assert shares == 10000

        # 当前价格10.5元 → 10万 / 10.5 = 9523.8 → 9500股（100倍数）
        shares = rm.calculate_position_size(10.5)
        assert shares == 9500

        # 自定义最大仓位
        shares = rm.calculate_position_size(10.0, max_pct=5.0)
        assert shares == 5000


class TestRiskManagerOption:
    """测试期权风控规则"""

    def test_option_position_allow(self):
        """测试期权新仓位允许开仓"""
        rm = RiskManager(1000000)  # 100万，单策略最大亏损3% → 3万
        result, reason = rm.check_option_position({}, 20000)  # 权利金2万 < 3万
        assert result is True
        assert "通过" in reason

    def test_option_single_loss_over_limit(self):
        """测试期权单策略最大亏损超限"""
        rm = RiskManager(1000000)  # 100万，单策略最大亏损3万
        result, reason = rm.check_option_position({}, 40000)  # 权利金4万 > 3万
        assert result is False
        assert "期权单策略最大亏损超限" in reason

    def test_option_total_premium_over_limit(self):
        """测试期权总权利金超限"""
        rm = RiskManager(1000000)  # 100万，总权利金最大20% → 20万
        positions = {
            'opt1': {'premium_total': 100000},
            'opt2': {'premium_total': 80000},
        }
        # 新增3万 → 累计18万 + 3万 = 21万 > 20万
        result, reason = rm.check_option_position(positions, 30000)
        assert result is False
        assert "期权总权利金超限" in reason

    def test_option_check_stop_loss(self):
        """测试期权止损"""
        rm = RiskManager(1000000)  # 默认止损50%
        # 买入权利金10000，当前4000 → 亏损60% < -50%，触发止损
        should_stop, reason = rm.check_option_stop_loss(10000, 4000)
        assert should_stop is True
        assert "期权权利金亏损-60.0%触发止损" in reason

        # 亏损40%，不触发
        should_stop, reason = rm.check_option_stop_loss(10000, 6000)
        assert should_stop is False


class TestRiskManagerGlobal:
    """测试整体市场风控"""

    def test_vix_pause_condition(self):
        """测试VIX过高暂停开仓"""
        rm = RiskManager(1000000, {'vix_pause_level': 25})
        # VIX 30 > 25，暂停
        result, reason = rm.check_market_global_condition(30, None, 0)
        assert result is False
        assert "VIX恐慌指数" in reason
        assert "超过阈值" in reason

        # VIX正常，允许
        result, reason = rm.check_market_global_condition(20, None, 0)
        assert result is True

    def test_vix_single_day_rise_pause(self):
        """测试VIX单日涨幅过大暂停"""
        rm = RiskManager(1000000)
        # VIX单日涨25% > 20%，暂停
        result, reason = rm.check_market_global_condition(20, 25, 0)
        assert result is False
        assert "VIX单日上涨" in reason

    def test_consecutive_loss_pause(self):
        """测试连续亏损暂停开仓"""
        rm = RiskManager(1000000, {'consecutive_loss_days_pause': 3})
        # 连续3天亏损，暂停
        result, reason = rm.check_market_global_condition(None, None, 3)
        assert result is False
        assert "连续3日亏损" in reason

        # 连续2天，允许
        result, reason = rm.check_market_global_condition(None, None, 2)
        assert result is True

    def test_sector_concentration_ok(self, sample_positions):
        """测试板块集中度正常"""
        rm = RiskManager(1000000, {'max_sector_pct': 30.0})
        # 银行板块 1000*10.5 = 10500 / 100万 = 1.05% < 30%
        # 地产板块 500*19.8 = 9900 / 100万 = 0.99% < 30%
        result, reason = rm.check_sector_concentration(sample_positions)
        assert result is True

    def test_sector_concentration_over_limit(self):
        """测试板块集中度超限"""
        rm = RiskManager(1000000, {'max_sector_pct': 30.0})
        # 同一板块持有50万 → 50% > 30%
        positions = {
            'stock1': {'quantity': 10000, 'current_price': 10, 'sector': '科技'},
            'stock2': {'quantity': 20000, 'current_price': 20, 'sector': '科技'},
            'stock3': {'quantity': 500, 'current_price': 15, 'sector': '金融'},
        }
        # 总市值: 10万 + 40万 = 50万，占50%
        result, reason = rm.check_sector_concentration(positions)
        assert result is False
        assert "板块科技持仓占比50.0%超过限制30.0%" in reason

    def test_a_stock_stop_loss_trigger(self):
        """测试A股强制止损"""
        rm = RiskManager(1000000, {'a_stock_stop_loss_pct': 2.0})
        # 买入10元，跌到9.78元 → 亏损2.2%，触发止损
        should_stop, reason = rm.check_a_stock_stop_loss(10.0, 9.78)
        assert should_stop is True
        assert "-2.20%" in reason

        # 跌到9.85元 → 亏损1.5%，不触发
        should_stop, reason = rm.check_a_stock_stop_loss(10.0, 9.85)
        assert should_stop is False
