"""
量化特征工程引擎 - V2.2 深度学习策略引擎

从 OHLCV DataFrame 构建全面的量化特征矩阵，包含 50+ 个技术指标特征。
所有特征使用纯 pandas/numpy 实现，无 talib 依赖。
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import logging
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """量化特征工程引擎"""

    def __init__(self):
        self.feature_names: List[str] = []
        self.scaler: Optional[StandardScaler] = None

    def build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """从 OHLCV DataFrame 构建特征矩阵

        Args:
            df: DataFrame with columns [open, high, low, close, volume]
                 Must have DatetimeIndex

        Returns:
            DataFrame with all feature columns added
        """
        df = df.copy()

        # 确保列名小写
        df.columns = [c.lower().strip() for c in df.columns]

        # ========== Price-based (10 features) ==========
        df['returns_1d'] = df['close'].pct_change(1)
        df['returns_5d'] = df['close'].pct_change(5)
        df['returns_10d'] = df['close'].pct_change(10)
        df['returns_20d'] = df['close'].pct_change(20)
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))
        df['close_to_high'] = df['close'] / df['high']
        df['close_to_low'] = df['close'] / df['low']
        df['close_to_open'] = df['close'] / df['open']
        df['high_low_range'] = (df['high'] - df['low']) / df['close']
        df['close_to_ma5'] = df['close'] / df['close'].rolling(5).mean()

        # ========== Moving averages (8 features) ==========
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        # Slopes: (current_ma - ma_n_periods_ago) / ma_n_periods_ago
        df['ma5_slope'] = (df['ma5'] - df['ma5'].shift(5)) / df['ma5'].shift(5)
        df['ma10_slope'] = (df['ma10'] - df['ma10'].shift(10)) / df['ma10'].shift(10)
        df['ma20_slope'] = (df['ma20'] - df['ma20'].shift(10)) / df['ma20'].shift(10)
        df['price_above_ma20'] = (df['close'] > df['ma20']).astype(int)

        # ========== Volatility (7 features) ==========
        df['volatility_5d'] = df['returns_1d'].rolling(5).std()
        df['volatility_20d'] = df['returns_1d'].rolling(20).std()
        # ATR (Average True Range)
        tr = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low'] - df['close'].shift(1)).abs()
        ], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(14).mean()
        df['atr_ratio'] = df['atr_14'] / df['close']
        # Bollinger Bands
        bb_ma = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bollinger_upper'] = bb_ma + 2 * bb_std
        df['bollinger_lower'] = bb_ma - 2 * bb_std
        df['bollinger_width'] = (df['bollinger_upper'] - df['bollinger_lower']) / bb_ma
        # Keltner Channel
        kc_ma = df['close'].rolling(20).mean()
        kc_atr = tr.rolling(20).mean()
        df['keltner_upper'] = kc_ma + 1.5 * kc_atr
        df['keltner_lower'] = kc_ma - 1.5 * kc_atr

        # ========== Volume (7 features) ==========
        df['volume_ratio_5d'] = df['volume'] / df['volume'].rolling(5).mean()
        df['volume_ratio_10d'] = df['volume'] / df['volume'].rolling(10).mean()
        df['volume_ma5'] = df['volume'].rolling(5).mean()
        df['volume_ma20'] = df['volume'].rolling(20).mean()
        # OBV (On Balance Volume)
        obv = pd.Series(0, index=df.index, dtype=float)
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i - 1]
        df['obv'] = obv
        df['obv_ma20'] = df['obv'].rolling(20).mean()
        df['obv_slope'] = (df['obv'] - df['obv'].shift(10)) / (df['obv'].shift(10).abs() + 1e-8)
        # Volume Price Trend
        df['volume_price_trend'] = df['volume'] * (df['close'].pct_change(1))

        # ========== Momentum (10 features) ==========
        # RSI
        df['rsi_6'] = self._compute_rsi(df['close'], 6)
        df['rsi_14'] = self._compute_rsi(df['close'], 14)
        df['rsi_24'] = self._compute_rsi(df['close'], 24)
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        # Stochastic
        low14 = df['low'].rolling(14).min()
        high14 = df['high'].rolling(14).max()
        df['stochastic_k'] = 100 * (df['close'] - low14) / (high14 - low14 + 1e-8)
        df['stochastic_d'] = df['stochastic_k'].rolling(3).mean()
        # CCI
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = typical_price.rolling(20).mean()
        mean_dev = typical_price.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        df['cci_20'] = (typical_price - sma_tp) / (0.015 * mean_dev + 1e-8)
        # Williams %R
        df['williams_r'] = -100 * (high14 - df['close']) / (high14 - low14 + 1e-8)

        # ========== Trend (6 features) ==========
        # ADX
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        atr14 = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / (atr14 + 1e-8))
        minus_di = 100 * (minus_dm.rolling(14).mean() / (atr14 + 1e-8))
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
        df['adx_14'] = dx.rolling(14).mean()
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        # Ichimoku
        df['ichimoku_tenkan'] = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2
        df['ichimoku_kijun'] = (df['high'].rolling(26).max() + df['low'].rolling(26).min()) / 2
        # Supertrend direction (simplified)
        hl2 = (df['high'] + df['low']) / 2
        atr_period = 10
        atr_val = tr.rolling(atr_period).mean()
        upper_band = hl2 + 3 * atr_val
        lower_band = hl2 - 3 * atr_val
        df['supertrend_direction'] = np.where(df['close'] > upper_band, 1,
                                               np.where(df['close'] < lower_band, -1, 0))

        # ========== Pattern (5 features) ==========
        body = df['close'] - df['open']
        full_range = df['high'] - df['low']
        upper_shadow = df['high'] - df[['open', 'close']].max(axis=1)
        lower_shadow = df[['open', 'close']].min(axis=1) - df['low']
        # Doji: body < 10% of range
        df['doji'] = (np.abs(body) < 0.1 * (full_range + 1e-8)).astype(int)
        # Hammer: lower shadow > 2*body, upper shadow < body
        df['hammer'] = ((lower_shadow > 2 * np.abs(body)) & (upper_shadow < np.abs(body))).astype(int)
        # Engulfing: current body engulfs previous body
        prev_body = body.shift(1)
        df['engulfing'] = ((np.sign(body) != np.sign(prev_body)) &
                           (np.abs(body) > np.abs(prev_body))).astype(int)
        # Morning Star: 3-candle pattern (simplified)
        df['morning_star'] = 0
        for i in range(2, len(df)):
            if (body.iloc[i - 2] < 0 and abs(body.iloc[i - 2]) > 0.01 * df['close'].iloc[i - 2] and
                abs(body.iloc[i - 1]) < 0.003 * df['close'].iloc[i - 1] and
                body.iloc[i] > 0 and abs(body.iloc[i]) > 0.01 * df['close'].iloc[i]):
                df.iloc[i, df.columns.get_loc('morning_star')] = 1
        # Evening Star
        df['evening_star'] = 0
        for i in range(2, len(df)):
            if (body.iloc[i - 2] > 0 and abs(body.iloc[i - 2]) > 0.01 * df['close'].iloc[i - 2] and
                abs(body.iloc[i - 1]) < 0.003 * df['close'].iloc[i - 1] and
                body.iloc[i] < 0 and abs(body.iloc[i]) > 0.01 * df['close'].iloc[i]):
                df.iloc[i, df.columns.get_loc('evening_star')] = 1

        # ========== Statistical (5 features) ==========
        df['z_score_20d'] = (df['close'] - df['close'].rolling(20).mean()) / (df['close'].rolling(20).std() + 1e-8)
        df['skewness_20d'] = df['returns_1d'].rolling(20).skew()
        df['kurtosis_20d'] = df['returns_1d'].rolling(20).kurt()
        # percentile_rank_20d: 使用纯 numpy 实现以兼容 pandas 2.x
        def _rolling_percentile_rank(s, window=20):
            result = np.full(len(s), np.nan)
            for i in range(window - 1, len(s)):
                window_data = s.iloc[i - window + 1:i + 1]
                result[i] = (window_data.rank(pct=True).iloc[-1])
            return result
        df['percentile_rank_20d'] = _rolling_percentile_rank(df['close'], 20)
        rolling_max = df['close'].rolling(20).max()
        df['max_drawdown_20d'] = (df['close'] - rolling_max) / rolling_max

        # ========== Cross-features (5 features) ==========
        # MA5/MA20 cross
        df['ma5_cross_ma20'] = 0
        ma5_above = (df['ma5'] > df['ma20']).fillna(False)
        ma5_above_prev = ma5_above.shift(1).fillna(False)
        df['ma5_cross_ma20'] = np.where(ma5_above & ~ma5_above_prev, 1,
                                         np.where(~ma5_above & ma5_above_prev, -1, 0))
        # MACD cross signal
        macd_above = (df['macd'] > df['macd_signal']).fillna(False)
        macd_above_prev = macd_above.shift(1).fillna(False)
        df['macd_cross_signal'] = np.where(macd_above & ~macd_above_prev, 1,
                                            np.where(~macd_above & macd_above_prev, -1, 0))
        # RSI divergence (simplified: price makes new high but RSI doesn't)
        price_higher = df['close'] > df['close'].rolling(20).max().shift(1)
        rsi_lower = df['rsi_14'] < df['rsi_14'].shift(1)
        df['rsi_divergence'] = ((price_higher & rsi_lower).astype(int) -
                                ((df['close'] < df['close'].rolling(20).min().shift(1)) &
                                 (df['rsi_14'] > df['rsi_14'].shift(1))).astype(int))
        # Volume breakout
        df['volume_breakout'] = (df['volume'] > 2 * df['volume_ma20']).astype(int)
        # Price momentum acceleration
        df['price_momentum_acceleration'] = df['returns_5d'] - df['returns_5d'].shift(5)

        # Define feature names
        self.feature_names = [
            # Price-based
            'returns_1d', 'returns_5d', 'returns_10d', 'returns_20d',
            'log_return', 'close_to_high', 'close_to_low', 'close_to_open',
            'high_low_range', 'close_to_ma5',
            # Moving averages
            'ma5', 'ma10', 'ma20', 'ma60',
            'ma5_slope', 'ma10_slope', 'ma20_slope', 'price_above_ma20',
            # Volatility
            'volatility_5d', 'volatility_20d', 'atr_14', 'atr_ratio',
            'bollinger_upper', 'bollinger_lower', 'bollinger_width',
            'keltner_upper', 'keltner_lower',
            # Volume
            'volume_ratio_5d', 'volume_ratio_10d', 'volume_ma5', 'volume_ma20',
            'obv', 'obv_ma20', 'obv_slope', 'volume_price_trend',
            # Momentum
            'rsi_6', 'rsi_14', 'rsi_24',
            'macd', 'macd_signal', 'macd_hist',
            'stochastic_k', 'stochastic_d', 'cci_20', 'williams_r',
            # Trend
            'adx_14', 'plus_di', 'minus_di',
            'ichimoku_tenkan', 'ichimoku_kijun', 'supertrend_direction',
            # Pattern
            'doji', 'hammer', 'engulfing', 'morning_star', 'evening_star',
            # Statistical
            'z_score_20d', 'skewness_20d', 'kurtosis_20d',
            'percentile_rank_20d', 'max_drawdown_20d',
            # Cross-features
            'ma5_cross_ma20', 'macd_cross_signal', 'rsi_divergence',
            'volume_breakout', 'price_momentum_acceleration',
        ]

        return df

    def _compute_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """计算 RSI (Relative Strength Index)"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-8)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def normalize(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """StandardScaler normalization

        Args:
            df: DataFrame with feature columns
            fit: If True, fit the scaler on this data

        Returns:
            Normalized DataFrame
        """
        feature_cols = [c for c in self.feature_names if c in df.columns]
        data = df[feature_cols].copy()

        if fit:
            self.scaler = StandardScaler()
            normalized = self.scaler.fit_transform(data)
        else:
            if self.scaler is None:
                raise ValueError("Scaler not fitted. Call normalize(fit=True) first.")
            normalized = self.scaler.transform(data)

        df[feature_cols] = normalized
        return df

    def create_sequences(self, df: pd.DataFrame, seq_length: int = 60) -> Tuple:
        """Create sequences for LSTM/Transformer input

        Args:
            df: DataFrame with feature columns (after normalization)
            seq_length: Sequence length

        Returns:
            (X, y) where X shape is (samples, seq_length, n_features)
            and y shape is (samples,) for next-day return direction
        """
        feature_cols = [c for c in self.feature_names if c in df.columns]
        data = df[feature_cols].values

        # Drop NaN rows
        valid_mask = ~np.isnan(data).any(axis=1)
        data = data[valid_mask]

        if len(data) <= seq_length:
            return np.array([]), np.array([])

        X, y = [], []
        for i in range(seq_length, len(data) - 1):
            X.append(data[i - seq_length:i])
            # Label: next day return direction (0=down, 1=flat, 2=up)
            next_return = data[i + 1, 0] if i + 1 < len(data) else 0  # returns_1d
            if next_return > 0.01:
                label = 2  # up
            elif next_return < -0.01:
                label = 0  # down
            else:
                label = 1  # flat
            y.append(label)

        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)

    def get_feature_importance(self, model) -> dict:
        """Get feature importance from trained model

        Args:
            model: Trained model with feature_importances_ attribute
                   (e.g., RandomForest, XGBoost)

        Returns:
            Dict mapping feature names to importance scores
        """
        if hasattr(model, 'feature_importances_'):
            return dict(zip(self.feature_names, model.feature_importances_.tolist()))
        elif hasattr(model, 'coef_'):
            return dict(zip(self.feature_names, np.abs(model.coef_[0]).tolist()))
        else:
            logger.warning("Model does not have feature_importances_ or coef_ attribute")
            return {}
