"""
v1.2 期权模块单元测试
"""
import math
import pytest
from datetime import date, datetime

from app.options_engine import (
    _norm_cdf, _norm_pdf, _d1, _d2,
    bs_call_price, bs_put_price,
    calculate_greeks, calculate_implied_volatility,
    generate_option_chain, calculate_strategy_pnl,
    Greeks,
)
from app import models, crud


# ========== 数学基础函数测试 ==========
class TestMathFunctions:
    def test_norm_cdf_symmetry(self):
        assert abs(_norm_cdf(0) - 0.5) < 0.001

    def test_norm_cdf_monotonic(self):
        for i in range(-30, 30):
            x1 = i * 0.1
            x2 = (i + 1) * 0.1
            assert _norm_cdf(x2) >= _norm_cdf(x1)

    def test_norm_cdf_bounds(self):
        assert _norm_cdf(-10) < 0.001
        assert _norm_cdf(10) > 0.999

    def test_norm_pdf_positive(self):
        for x in [-3, -1, 0, 1, 3]:
            assert _norm_pdf(x) > 0

    def test_norm_pdf_peak_at_zero(self):
        assert _norm_pdf(0) > _norm_pdf(1)
        assert _norm_pdf(0) > _norm_pdf(-1)

    def test_d1_calculation(self):
        d = _d1(S=100, K=100, T=1, r=0.05, sigma=0.2)
        assert abs(d) < 1  # ATM 时 d1 应接近 0

    def test_d2_equals_d1_minus_sigma_sqrt_t(self):
        d1_val = _d1(100, 100, 1, 0.05, 0.2)
        d2_val = _d2(d1_val, 1, 0.2)
        expected = d1_val - 0.2 * math.sqrt(1)
        assert abs(d2_val - expected) < 1e-10


# ========== BS 定价测试 ==========
class TestBlackScholes:
    def test_call_put_parity(self):
        """看涨-看跌平价: C - P = S - K*e^(-rT)"""
        S, K, T, r, sigma = 100, 100, 1, 0.05, 0.2
        C = bs_call_price(S, K, T, r, sigma)
        P = bs_put_price(S, K, T, r, sigma)
        left = C - P
        right = S - K * math.exp(-r * T)
        assert abs(left - right) < 0.01

    def test_call_price_positive(self):
        for S in [80, 100, 120]:
            for K in [90, 100, 110]:
                assert bs_call_price(S, K, 1, 0.05, 0.3) >= 0

    def test_put_price_positive(self):
        for S in [80, 100, 120]:
            for K in [90, 100, 110]:
                assert bs_put_price(S, K, 1, 0.05, 0.3) >= 0

    def test_itm_call_worth_more(self):
        """实值看涨期权价格 > 虚值"""
        S, K, T, r, sigma = 120, 100, 0.5, 0.05, 0.2
        itm_call = bs_call_price(S, K, T, r, sigma)
        otm_call = bs_call_price(S, 140, T, r, sigma)
        assert itm_call > otm_call

    def test_expired_option(self):
        """到期日期权价值 = 内在价值"""
        C = bs_call_price(110, 100, 0, 0.05, 0.2)
        assert abs(C - 10) < 0.01
        P = bs_put_price(90, 100, 0, 0.05, 0.2)
        assert abs(P - 10) < 0.01

    def test_higher_vol_higher_price(self):
        """波动率越高，期权价格越高"""
        S, K, T, r = 100, 100, 1, 0.05
        low_vol = bs_call_price(S, K, T, r, 0.1)
        high_vol = bs_call_price(S, K, T, r, 0.5)
        assert high_vol > low_vol

    def test_longer_expiry_higher_price(self):
        """到期时间越长，期权价格越高"""
        S, K, r, sigma = 100, 100, 0.05, 0.2
        short = bs_call_price(S, K, 0.1, r, sigma)
        long = bs_call_price(S, K, 1.0, r, sigma)
        assert long > short


# ========== 希腊字母测试 ==========
class TestGreeks:
    def test_call_delta_range(self):
        g = calculate_greeks(100, 100, 1, 0.05, 0.2, "CALL")
        assert 0 < g.delta < 1  # ATM call delta ~0.5

    def test_put_delta_range(self):
        g = calculate_greeks(100, 100, 1, 0.05, 0.2, "PUT")
        assert -1 < g.delta < 0  # ATM put delta ~-0.5

    def test_delta_deep_itm_call(self):
        g = calculate_greeks(150, 100, 1, 0.05, 0.2, "CALL")
        assert g.delta > 0.9  # 深度实值接近 1

    def test_delta_deep_otm_call(self):
        g = calculate_greeks(50, 100, 1, 0.05, 0.2, "CALL")
        assert g.delta < 0.1  # 深度虚值接近 0

    def test_gamma_positive(self):
        for opt in ["CALL", "PUT"]:
            g = calculate_greeks(100, 100, 0.5, 0.05, 0.3, opt)
            assert g.gamma > 0

    def test_theta_negative(self):
        """期权 Theta 通常为负（时间衰减）"""
        for opt in ["CALL", "PUT"]:
            g = calculate_greeks(100, 100, 0.5, 0.05, 0.3, opt)
            assert g.theta < 0

    def test_vega_positive(self):
        for opt in ["CALL", "PUT"]:
            g = calculate_greeks(100, 100, 0.5, 0.05, 0.3, opt)
            assert g.vega > 0

    def test_call_put_gamma_equal(self):
        """看涨看跌 Gamma 相同"""
        gc = calculate_greeks(100, 100, 0.5, 0.05, 0.3, "CALL")
        gp = calculate_greeks(100, 100, 0.5, 0.05, 0.3, "PUT")
        assert abs(gc.gamma - gp.gamma) < 1e-10

    def test_call_put_vega_equal(self):
        """看涨看跌 Vega 相同"""
        gc = calculate_greeks(100, 100, 0.5, 0.05, 0.3, "CALL")
        gp = calculate_greeks(100, 100, 0.5, 0.05, 0.3, "PUT")
        assert abs(gc.vega - gp.vega) < 1e-10

    def test_greeks_return_type(self):
        g = calculate_greeks(100, 100, 1, 0.05, 0.2, "CALL")
        assert isinstance(g, Greeks)
        assert hasattr(g, 'delta')
        assert hasattr(g, 'gamma')
        assert hasattr(g, 'theta')
        assert hasattr(g, 'vega')

    def test_expired_greeks(self):
        g = calculate_greeks(100, 100, 0, 0.05, 0.2, "CALL")
        assert g.theta == 0
        assert g.gamma == 0
        assert g.vega == 0


# ========== 隐含波动率测试 ==========
class TestImpliedVolatility:
    def test_iv_recovers_original(self):
        """用 BS 价格反解 IV 应恢复原始波动率"""
        S, K, T, r, sigma = 100, 100, 0.5, 0.05, 0.3
        market_price = bs_call_price(S, K, T, r, sigma)
        iv = calculate_implied_volatility(S, K, T, r, market_price, "CALL")
        assert iv is not None
        assert abs(iv - sigma) < 0.001

    def test_iv_put_recovers(self):
        S, K, T, r, sigma = 100, 100, 0.5, 0.05, 0.25
        market_price = bs_put_price(S, K, T, r, sigma)
        iv = calculate_implied_volatility(S, K, T, r, market_price, "PUT")
        assert iv is not None
        assert abs(iv - sigma) < 0.001

    def test_iv_invalid_price(self):
        iv = calculate_implied_volatility(100, 100, 0.5, 0.05, -1, "CALL")
        assert iv is None

    def test_iv_zero_time(self):
        iv = calculate_implied_volatility(100, 100, 0, 0.05, 5, "CALL")
        assert iv is None


# ========== 期权链测试 ==========
class TestOptionChain:
    def test_generate_chain(self):
        chain = generate_option_chain("AAPL", 185, "2025-06-20", n_strikes=5)
        assert len(chain) == 10  # 5 strikes * 2 types

    def test_chain_has_calls_and_puts(self):
        chain = generate_option_chain("AAPL", 185, "2025-06-20")
        types = set(c["option_type"] for c in chain)
        assert types == {"CALL", "PUT"}

    def test_chain_strike_range(self):
        chain = generate_option_chain("AAPL", 100, "2025-06-20", n_strikes=11)
        strikes = set(c["strike_price"] for c in chain)
        assert min(strikes) < 100
        assert max(strikes) > 100

    def test_chain_greeks_present(self):
        chain = generate_option_chain("AAPL", 185, "2025-06-20")
        for c in chain:
            assert "delta" in c
            assert "gamma" in c
            assert "theta" in c
            assert "vega" in c
            assert "implied_vol" in c

    def test_chain_itm_flag(self):
        chain = generate_option_chain("AAPL", 100, "2025-06-20")
        for c in chain:
            if c["option_type"] == "CALL" and c["strike_price"] < 100:
                assert c["is_itm"] is True
            elif c["option_type"] == "PUT" and c["strike_price"] > 100:
                assert c["is_itm"] is True


# ========== 组合盈亏测试 ==========
class TestStrategyPnl:
    def test_long_call_pnl(self):
        """买入看涨期权"""
        legs = [{"option_type": "CALL", "strike": 100, "action": "buy", "quantity": 1, "premium": 5, "multiplier": 100}]
        result = calculate_strategy_pnl(legs, [90, 100, 105, 110])
        # 在 90: 亏损 500 (权利金)
        assert result[0]["pnl"] == -500
        # 在 110: 盈利 500 ((110-100)*100 - 500)
        assert result[3]["pnl"] == 500

    def test_bull_spread_pnl(self):
        """牛市价差"""
        legs = [
            {"option_type": "CALL", "strike": 100, "action": "buy", "quantity": 1, "premium": 5, "multiplier": 100},
            {"option_type": "CALL", "strike": 110, "action": "sell", "quantity": 1, "premium": 2, "multiplier": 100},
        ]
        result = calculate_strategy_pnl(legs, [100, 105, 110, 115])
        # 在 100: 亏损 300 (买5卖2)
        assert result[0]["pnl"] == -300
        # 在 115: 盈利 700 ((15-10)*100 - (5-2)*100)
        assert result[3]["pnl"] == 700

    def test_straddle_pnl(self):
        """跨式组合"""
        legs = [
            {"option_type": "CALL", "strike": 100, "action": "buy", "quantity": 1, "premium": 5, "multiplier": 100},
            {"option_type": "PUT", "strike": 100, "action": "buy", "quantity": 1, "premium": 4, "multiplier": 100},
        ]
        result = calculate_strategy_pnl(legs, [90, 95, 100, 105, 110])
        # 在 100: 亏损 900 (两个权利金)
        assert result[2]["pnl"] == -900
        # 在 90: 盈亏 = (0-500) + (1000-400) = 100
        assert result[0]["pnl"] == 100

    def test_iron_condor_four_legs(self):
        """铁鹰四条腿"""
        legs = [
            {"option_type": "PUT", "strike": 90, "action": "buy", "quantity": 1, "premium": 1, "multiplier": 100},
            {"option_type": "PUT", "strike": 95, "action": "sell", "quantity": 1, "premium": 3, "multiplier": 100},
            {"option_type": "CALL", "strike": 105, "action": "sell", "quantity": 1, "premium": 3, "multiplier": 100},
            {"option_type": "CALL", "strike": 110, "action": "buy", "quantity": 1, "premium": 1, "multiplier": 100},
        ]
        result = calculate_strategy_pnl(legs, [100])
        # 在 100: 所有期权到期无价值，净收入 = (3-1)*100 + (3-1)*100 = 400
        assert result[0]["pnl"] == 400


# ========== 期权 CRUD 测试 ==========
class TestOptionCRUD:
    def test_create_option_position(self, db_session):
        pos = crud.create_option_position(
            db_session,
            name="牛市价差",
            strategy_type="bull_call_spread",
            underlying_symbol="AAPL",
            legs='[{"option_type": "CALL", "strike": 100}]',
            max_profit=500,
            max_loss=300,
        )
        assert pos.id is not None
        assert pos.name == "牛市价差"

    def test_get_option_positions(self, db_session):
        crud.create_option_position(db_session, name="策略1", underlying_symbol="AAPL", legs='[]')
        crud.create_option_position(db_session, name="策略2", underlying_symbol="TSLA", legs='[]', status="closed")

        open_pos = crud.get_option_positions(db_session, status="open")
        assert len(open_pos) == 1
        assert open_pos[0].name == "策略1"

    def test_delete_option_position(self, db_session):
        pos = crud.create_option_position(db_session, name="删除测试", underlying_symbol="AAPL", legs='[]')
        crud.delete_option_position(db_session, pos.id)
        all_pos = crud.get_option_positions(db_session)
        assert len(all_pos) == 0
