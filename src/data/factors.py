"""
量价因子计算模块
提供常用技术因子计算，用于机器学习训练
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional


def calc_returns(df: pd.DataFrame, periods: List[int] = [1, 2, 3, 5, 10, 20]) -> pd.DataFrame:
    """
    计算N日收益率
    
    Args:
        df: 包含close列的DataFrame（按日期升序排列）
        periods: 计算不同周期的收益率
    
    Returns:
        添加了收益率列的DataFrame
    """
    for n in periods:
        df[f'return_{n}d'] = df['close'].pct_change(n)
    return df


def calc_volatility(df: pd.DataFrame, periods: List[int] = [5, 10, 20]) -> pd.DataFrame:
    """
    计算N日波动率（收益率的标准差）
    
    Args:
        df: 包含close列的DataFrame
        periods: 周期
    
    Returns:
        添加了波动率列的DataFrame
    """
    for n in periods:
        df[f'volatility_{n}d'] = df['close'].pct_change().rolling(n).std()
    return df


def calc_turnover_volume(df: pd.DataFrame, periods: List[int] = [5, 10, 20]) -> pd.DataFrame:
    """
    计算换手率和成交量相关因子
    
    Args:
        df: 包含vol/amount列的DataFrame
        periods: 周期
    
    Returns:
        添加了相关因子的DataFrame
    """
    # 日均成交量
    for n in periods:
        df[f'volume_ma{n}d'] = df['vol'].rolling(n).mean()
        df[f'amount_ma{n}d'] = df['amount'].rolling(n).mean()
    
    # 成交量比率（当日成交量 / N日均量）
    if 5 in periods:
        df['volume_ratio_5d'] = df['vol'] / df['volume_ma5d']
    
    # 换手率这里vol就是换手率（Tushare格式）
    for n in periods:
        df[f'turnover_ma{n}d'] = df['vol'].rolling(n).mean()
    
    return df


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    计算MACD指标
    
    Args:
        df: 包含close列的DataFrame
        fast: 快速EMA周期
        slow: 慢速EMA周期
        signal: 信号线周期
    
    Returns:
        添加了macd相关列的DataFrame
    """
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df


def calc_rsi(df: pd.DataFrame, periods: List[int] = [6, 12, 24]) -> pd.DataFrame:
    """
    计算RSI相对强弱指标
    
    Args:
        df: 包含close列的DataFrame
        periods: 周期
    
    Returns:
        添加了RSI列的DataFrame
    """
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    for n in periods:
        avg_gain = gain.rolling(n).mean()
        avg_loss = loss.rolling(n).mean()
        rs = avg_gain / avg_loss
        df[f'rsi{n}'] = 100 - (100 / (1 + rs))
    
    return df


def calc_williams_r(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算威廉指标WR
    
    Args:
        df: 包含high/low/close列的DataFrame
        period: 周期
    
    Returns:
        添加了wr列的DataFrame
    """
    highest_high = df['high'].rolling(period).max()
    lowest_low = df['low'].rolling(period).min()
    df['wr'] = -100 * (highest_high - df['close']) / (highest_high - lowest_low)
    return df


def calc_cci(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算CCI顺势指标
    
    Args:
        df: 包含high/low/close列的DataFrame
        period: 周期
    
    Returns:
        添加了cci列的DataFrame
    """
    tp = (df['high'] + df['low'] + df['close']) / 3
    sma_tp = tp.rolling(period).mean()
    mean_dev = abs(tp - sma_tp).rolling(period).mean()
    df['cci'] = (tp - sma_tp) / (0.015 * mean_dev)
    return df


def calc_bias(df: pd.DataFrame, periods: List[int] = [6, 12, 24]) -> pd.DataFrame:
    """
    计算乖离率BIAS
    
    Args:
        df: 包含close列的DataFrame
        periods: 周期
    
    Returns:
        添加了bias列的DataFrame
    """
    for n in periods:
        ma = df['close'].rolling(n).mean()
        df[f'bias{n}'] = (df['close'] - ma) / ma * 100
    return df


def calc_mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    计算MFI资金流向指标
    
    Args:
        df: 包含high/low/close/vol(amount)列的DataFrame
        period: 周期
    
    Returns:
        添加了mfi列的DataFrame
        注意：Tushare中vol是换手率，amount是成交金额
    """
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    money_flow = typical_price * df['amount']
    
    delta = typical_price.diff()
    positive_flow = money_flow.where(delta > 0, 0)
    negative_flow = money_flow.where(delta < 0, 0)
    
    positive_sum = positive_flow.rolling(period).sum()
    negative_sum = negative_flow.rolling(period).sum()
    
    money_ratio = positive_sum / negative_sum
    df['mfi'] = 100 - (100 / (1 + money_ratio))
    return df


def calc_nlm(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
    """
    计算N日大单资金流（简化版，用涨跌幅成交量代替）
    实际可以用Tushare专业版的cn_stock_factors获取真实数据
    
    Args:
        df: 数据
        period: 周期
    
    Returns:
        添加了nlm列的DataFrame
    """
    # 简化计算：涨跌幅 * 成交量占比
    df['nlm_5'] = (df['close'].diff() / df['close'].shift(1)) * (df['amount'] / df['amount'].rolling(5).mean())
    df['nlm_5'] = df['nlm_5'].rolling(5).sum()
    return df


def calc_psy(df: pd.DataFrame, period: int = 12) -> pd.DataFrame:
    """
    计算心理线PSY
    
    Args:
        df: 包含close列的DataFrame
        period: 周期
    
    Returns:
        添加了psy列的DataFrame
    """
    up_days = (df['close'].diff() > 0).astype(int)
    df[f'psy{period}'] = up_days.rolling(period).mean() * 100
    return df


def calc_ma(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
    """
    计算移动平均线
    
    Args:
        df: 包含close列的DataFrame
        periods: 周期
    
    Returns:
        添加了ma列的DataFrame
    """
    for n in periods:
        df[f'ma{n}'] = df['close'].rolling(n).mean()
    
    # 价格相对于均线的偏离
    for n in periods:
        df[f'close_over_ma{n}'] = df['close'] / df[f'ma{n}'] - 1
    
    # 均线方向
    for n in periods:
        df[f'ma{n}_slope'] = df[f'ma{n}'].diff() / n
    
    return df


def calculate_all_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算所有预设因子，至少20个
    
    Args:
        df: 原始行情DataFrame，需要包含：open, high, low, close, vol, amount
        且已经按日期升序排列
    
    Returns:
        添加了所有因子的DataFrame，去掉了开头有NaN的行
    """
    # 复制一份避免修改原数据
    df = df.copy()
    
    # 确保列名正确（Tushare返回的列名是trade_date, open, high, close, low, vol, amount）
    required_cols = ['open', 'high', 'low', 'close', 'vol', 'amount']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # 计算各种因子
    df = calc_returns(df, [1, 2, 3, 5, 10, 20])
    df = calc_volatility(df, [5, 10, 20])
    df = calc_turnover_volume(df, [5, 10, 20])
    df = calc_macd(df)
    df = calc_rsi(df, [6, 12, 24])
    df = calc_williams_r(df)
    df = calc_cci(df)
    df = calc_bias(df, [6, 12, 24])
    df = calc_mfi(df)
    df = calc_psy(df)
    df = calc_nlm(df)
    df = calc_ma(df, [5, 10, 20, 60])
    
    # 去掉开头的NaN（最长周期是60天，所以去掉前60行肯定够）
    df = df.dropna().reset_index(drop=True)
    
    return df


def get_feature_names() -> List[str]:
    """
    获取所有因子名称列表，用于训练模型
    
    Returns:
        因子名称列表
    """
    features = [
        # returns
        'return_1d', 'return_2d', 'return_3d', 'return_5d', 'return_10d', 'return_20d',
        # volatility
        'volatility_5d', 'volatility_10d', 'volatility_20d',
        # volume/turnover
        'volume_ratio_5d', 'turnover_ma5d', 'turnover_ma10d', 'turnover_ma20d',
        # MACD
        'macd', 'macd_signal', 'macd_hist',
        # RSI
        'rsi6', 'rsi12', 'rsi24',
        # others
        'wr', 'cci',
        'bias6', 'bias12', 'bias24',
        'mfi',
        'psy12',
        'nlm_5',
        # MA
        'close_over_ma5', 'close_over_ma10', 'close_over_ma20', 'close_over_ma60',
        'ma5_slope', 'ma10_slope', 'ma20_slope', 'ma60_slope',
    ]
    return features
