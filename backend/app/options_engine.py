"""
期权希腊字母计算引擎 — 基于 Black-Scholes 模型
"""
import math
from typing import Optional
from dataclasses import dataclass


@dataclass
class Greeks:
    """希腊字母"""
    delta: float
    gamma: float
    theta: float
    vega: float
    implied_vol: float
    theoretical_price: float


@dataclass
class OptionPricingResult:
    """期权定价结果"""
    call_price: float
    put_price: float
    call_greeks: Greeks
    put_greeks: Greeks


# 常量
SQRT_2PI = math.sqrt(2 * math.pi)
TRADING_DAYS_PER_YEAR = 252


def _norm_pdf(x: float) -> float:
    """标准正态分布概率密度函数"""
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _norm_cdf(x: float) -> float:
    """标准正态分布累积分布函数（近似）"""
    if x < -8:
        return 0.0
    if x > 8:
        return 1.0
    # Abramowitz and Stegun 近似
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """BS 模型 d1 参数"""
    if T <= 0 or sigma <= 0:
        return 0.0
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))


def _d2(d1_val: float, T: float, sigma: float) -> float:
    """BS 模型 d2 参数"""
    return d1_val - sigma * math.sqrt(T)


def bs_call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes 看涨期权价格"""
    if T <= 0:
        return max(S - K, 0.0)
    d1_val = _d1(S, K, T, r, sigma)
    d2_val = _d2(d1_val, T, sigma)
    return S * _norm_cdf(d1_val) - K * math.exp(-r * T) * _norm_cdf(d2_val)


def bs_put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes 看跌期权价格"""
    if T <= 0:
        return max(K - S, 0.0)
    d1_val = _d1(S, K, T, r, sigma)
    d2_val = _d2(d1_val, T, sigma)
    return K * math.exp(-r * T) * _norm_cdf(-d2_val) - S * _norm_cdf(-d1_val)


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "CALL",
) -> Greeks:
    """
    计算单个合约的希腊字母

    :param S: 标的当前价格
    :param K: 行权价
    :param T: 剩余时间（年）
    :param r: 无风险利率
    :param sigma: 隐含波动率
    :param option_type: CALL 或 PUT
    :return: Greeks dataclass
    """
    if T <= 0:
        # 已到期
        if option_type.upper() == "CALL":
            itm = S > K
            delta = 1.0 if itm else 0.0
        else:
            itm = S < K
            delta = -1.0 if itm else 0.0
        return Greeks(delta=delta, gamma=0, theta=0, vega=0, implied_vol=sigma, theoretical_price=0)

    d1_val = _d1(S, K, T, r, sigma)
    d2_val = _d2(d1_val, T, sigma)

    sqrt_T = math.sqrt(T)
    pdf_d1 = _norm_pdf(d1_val)
    exp_rt = math.exp(-r * T)

    # Delta
    if option_type.upper() == "CALL":
        delta = _norm_cdf(d1_val)
        theoretical = bs_call_price(S, K, T, r, sigma)
    else:
        delta = _norm_cdf(d1_val) - 1
        theoretical = bs_put_price(S, K, T, r, sigma)

    # Gamma (看涨看跌相同)
    gamma = pdf_d1 / (S * sigma * sqrt_T)

    # Theta
    if option_type.upper() == "CALL":
        theta = (-S * pdf_d1 * sigma / (2 * sqrt_T)
                 - r * K * exp_rt * _norm_cdf(d2_val)) / TRADING_DAYS_PER_YEAR
    else:
        theta = (-S * pdf_d1 * sigma / (2 * sqrt_T)
                 + r * K * exp_rt * _norm_cdf(-d2_val)) / TRADING_DAYS_PER_YEAR

    # Vega (看涨看跌相同)
    vega = S * pdf_d1 * sqrt_T / 100  # 除以100，每1%波动率变化

    return Greeks(
        delta=round(delta, 6),
        gamma=round(gamma, 6),
        theta=round(theta, 4),
        vega=round(vega, 4),
        implied_vol=sigma,
        theoretical_price=round(theoretical, 4),
    )


def calculate_implied_volatility(
    S: float,
    K: float,
    T: float,
    r: float,
    market_price: float,
    option_type: str = "CALL",
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> Optional[float]:
    """
    牛顿法求解隐含波动率

    :param S: 标的当前价格
    :param K: 行权价
    :param T: 剩余时间（年）
    :param r: 无风险利率
    :param market_price: 市场价格
    :param option_type: CALL 或 PUT
    :return: 隐含波动率，求解失败返回 None
    """
    if T <= 0 or market_price <= 0:
        return None

    # 初始猜测
    sigma = 0.3  # 30%

    for _ in range(max_iterations):
        greeks = calculate_greeks(S, K, T, r, sigma, option_type)
        diff = greeks.theoretical_price - market_price

        if abs(diff) < tolerance:
            return sigma

        if greeks.vega <= 0:
            break

        # Vega 需要乘回 100（因为 calculate_greeks 中除以了100）
        vega_full = greeks.vega * 100
        if vega_full <= 1e-10:
            break

        sigma -= diff / vega_full
        sigma = max(0.001, min(sigma, 5.0))  # 限制范围

    return sigma


def generate_option_chain(
    symbol: str,
    S: float,
    expiry_date: str,
    r: float = 0.05,
    base_sigma: float = 0.3,
    n_strikes: int = 11,
) -> list:
    """
    生成模拟期权链数据

    :param symbol: 标的代码
    :param S: 标的当前价格
    :param expiry_date: 到期日 YYYY-MM-DD
    :param r: 无风险利率
    :param base_sigma: 基础波动率
    :param n_strikes: 行权价数量（奇数，以 ATM 为中心）
    :return: 期权合约列表
    """
    from datetime import datetime, date

    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()
    except ValueError:
        expiry = date.today()

    today = date.today()
    T = max((expiry - today).days / 365.0, 0.001)
    dte = (expiry - today).days

    # 生成行权价（ATM 为中心，间距 5%）
    atm = round(S, 2)
    step = round(S * 0.05, 2)  # 5% 间距
    strikes = [round(atm + (i - n_strikes // 2) * step, 2) for i in range(n_strikes)]

    contracts = []
    for K in strikes:
        # 微调波动率（OTM 略高，ITM 略低）
        moneyness = K / S
        sigma = base_sigma * (1 + 0.1 * abs(math.log(moneyness)))

        for opt_type in ["CALL", "PUT"]:
            greeks = calculate_greeks(S, K, T, r, sigma, opt_type)
            mid_price = greeks.theoretical_price
            spread = round(mid_price * 0.05, 2)  # 5% 买卖价差

            # 内在价值和时间价值
            if opt_type == "CALL":
                intrinsic = max(S - K, 0)
            else:
                intrinsic = max(K - S, 0)
            time_val = max(mid_price - intrinsic, 0)

            contracts.append({
                "symbol": symbol,
                "underlying_price": S,
                "option_type": opt_type,
                "strike_price": K,
                "expiry_date": expiry_date,
                "days_to_expiry": dte,
                "bid": round(max(mid_price - spread / 2, 0.01), 4),
                "ask": round(mid_price + spread / 2, 4),
                "last_price": round(mid_price, 4),
                "volume": int(abs(S * 1000 * (1 + hash(f"{symbol}{K}{opt_type}") % 5))),
                "open_interest": int(abs(S * 500 * (1 + hash(f"{symbol}{K}{opt_type}2") % 3))),
                "delta": greeks.delta,
                "gamma": greeks.gamma,
                "theta": greeks.theta,
                "vega": greeks.vega,
                "implied_vol": round(sigma, 4),
                "intrinsic_value": round(intrinsic, 4),
                "time_value": round(time_val, 4),
                "is_itm": intrinsic > 0,
            })

    return contracts


def calculate_strategy_pnl(
    legs: list,
    underlying_prices: list,
) -> list:
    """
    计算期权组合在不同标的价格下的盈亏

    :param legs: 组合腿列表 [{"option_type": "CALL", "strike": 100, "expiry": "2024-06-21",
              "action": "buy", "quantity": 1, "premium": 5.0}, ...]
    :param underlying_prices: 标的价格列表
    :return: 盈亏列表 [{"price": 100, "pnl": 500}, ...]
    """
    from datetime import datetime, date

    results = []
    for S in underlying_prices:
        total_pnl = 0
        for leg in legs:
            K = leg["strike"]
            opt_type = leg.get("option_type", "CALL").upper()
            action = leg.get("action", "buy").lower()
            qty = leg.get("quantity", 1)
            premium = leg.get("premium", 0)
            multiplier = leg.get("multiplier", 100)

            # 计算到期期权价值
            if opt_type == "CALL":
                intrinsic = max(S - K, 0)
            else:
                intrinsic = max(K - S, 0)

            # 盈亏 = (到期价值 - 权利金) * 数量 * 乘数 * 方向
            if action == "buy":
                pnl = (intrinsic - premium) * qty * multiplier
            else:
                pnl = (premium - intrinsic) * qty * multiplier

            total_pnl += pnl

        results.append({"price": round(S, 2), "pnl": round(total_pnl, 2)})

    return results
