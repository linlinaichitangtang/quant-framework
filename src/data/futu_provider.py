"""
富途数据获取模块
负责从富途（OpenD API）获取A股/港股/美股实时行情和历史K线
"""

import sys
import time
import signal
from typing import List, Optional, Dict, Tuple
from pathlib import Path

import pandas as pd
import numpy as np

from src.utils.logging import logger


# 富途代码格式 → 内部格式映射
_FUTU_CODE_MAP = {
    "SH": "CN",  # A股上交所 → 内部CN
    "SZ": "CN",  # A股深交所 → 内部CN
    "HK": "HK",  # 港股
    "US": "US",  # 美股
}

# 内部格式 → 富途代码格式
_INTERNAL_TO_FUTU = {
    "CN": "SH",  # 默认用沪股通
    "HK": "HK",
    "US": "US",
}

# 市场枚举
class MarketType:
    CN = "CN"   # A股
    HK = "HK"   # 港股
    US = "US"   # 美股


class FutuProvider:
    """
    富途数据提供者

    替换 TushareProvider，提供：
    - A股/港股/美股 实时行情
    - A股/港股/美股 历史K线（日/分钟）
    - 股票列表（按市场）
    - 基本面数据（股票信息）
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 11111):
        self.host = host
        self.port = port
        self._quote_ctx = None
        self._connected = False

    # ─── 连接管理 ──────────────────────────────────────────────

    def connect(self):
        """建立行情连接"""
        if self._connected and self._quote_ctx:
            return

        from futu import OpenQuoteContext
        self._quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
        self._connected = True
        logger.info(f"[FutuProvider] 连接成功 {self.host}:{self.port}")

    def close(self):
        """关闭连接"""
        if self._quote_ctx:
            self._quote_ctx.close()
            self._quote_ctx = None
            self._connected = False
            logger.info("[FutuProvider] 连接已关闭")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    # ─── 内部工具 ──────────────────────────────────────────────

    @staticmethod
    def _convert_code(code: str, to_futu: bool = True) -> str:
        """
        转换股票代码格式

        Args:
            code: 股票代码，如 "SH.600000" 或 "600000"
            to_futu: True=转为富途格式 "SH.600000"，False=转为内部格式 "CN.600000"

        富途格式: SH.600000 / SZ.000001 / HK.00700 / US.QQQ
        内部格式: CN.600000 / HK.00700 / US.QQQ
        """
        if to_futu:
            # 内部格式 → 富途格式
            if "." in code:
                market, symbol = code.split(".", 1)
                if market == "CN":
                    # A股默认用 SH，也可选 SZ
                    return f"SH.{symbol}"
                return f"{market}.{symbol}"
            else:
                # 无前缀默认当A股处理
                if len(code) == 6 and code.isdigit():
                    return f"SH.{code}"
                return code
        else:
            # 富途格式 → 内部格式
            if "." in code:
                market, symbol = code.split(".", 1)
                internal_market = _FUTU_CODE_MAP.get(market, market)
                return f"{internal_market}.{symbol}"
            return code

    @staticmethod
    def _ensure_connected(ctx, max_retries: int = 3) -> bool:
        """确保连接有效，超时后重试"""
        for attempt in range(max_retries):
            try:
                ret, data = ctx.get_global_state()
                if ret == 0:
                    return True
                time.sleep(1)
            except Exception:
                time.sleep(2)
        return False

    def _with_connection(self, func):
        """装饰器：自动管理连接生命周期"""
        def wrapper(*args, **kwargs):
            needs_close = False
            if not self._connected or self._quote_ctx is None:
                self.connect()
                needs_close = True
            try:
                return func(*args, **kwargs)
            finally:
                if needs_close:
                    self.close()
        return wrapper

    # ─── 实时行情 ──────────────────────────────────────────────

    def get_stock_quote(self, symbols: List[str]) -> pd.DataFrame:
        """
        获取实时行情快照（支持A股/港股/美股）

        Args:
            symbols: 股票代码列表，内部格式，如 ["CN.600000", "HK.00700", "US.QQQ"]

        Returns:
            DataFrame，含 last_price / change_rate / volume 等字段
        """
        if not symbols:
            return pd.DataFrame()

        self.connect()
        from futu import SubType

        # 转换为富途格式
        futu_codes = [self._convert_code(s, to_futu=True) for s in symbols]

        # 订阅
        for code in futu_codes:
            ret, _ = self._quote_ctx.subscribe(code, SubType.QUOTE)
            if ret != 0:
                logger.warning(f"订阅失败 {code}: {_}")

        # 等待数据推送
        time.sleep(2)

        # 拉取
        ret, data = self._quote_ctx.get_stock_quote(futu_codes)
        if ret != 0:
            logger.error(f"get_stock_quote 失败: {data}")
            return pd.DataFrame()

        # 转换代码为内部格式
        if 'code' in data.columns:
            data['code'] = data['code'].apply(lambda x: self._convert_code(x, to_futu=False))

        logger.info(f"[FutuProvider] 实时行情获取成功 {len(data)} 条")
        return data

    # ─── 历史K线 ──────────────────────────────────────────────

    def get_daily_bars(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日线历史数据

        Args:
            symbol: 股票代码，内部格式，如 "CN.600000"
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            DataFrame，含 time_key / open / close / high / low / volume / change_rate
        """
        self.connect()
        from futu import KLType, AuType

        futu_code = self._convert_code(symbol, to_futu=True)

        ret, data, _ = self._quote_ctx.request_history_kline(
            futu_code,
            start=start_date,
            end=end_date,
            ktype=KLType.K_DAY,
            autype=AuType.QFQ,
            max_count=1000,
        )

        if ret != 0:
            logger.error(f"get_daily_bars 失败 {symbol}: {data}")
            return pd.DataFrame()

        # 富途返回列: time_key, open, close, high, low, volume, turnover, change_rate, last_close, pe_ratio, turnover_rate
        df = data[['time_key', 'open', 'close', 'high', 'low', 'volume', 'turnover', 'change_rate', 'last_close']].copy()

        # 转换日期格式
        df['time_key'] = pd.to_datetime(df['time_key']).dt.strftime('%Y-%m-%d')
        df = df.rename(columns={'time_key': 'date', 'turnover': 'amount', 'change_rate': 'pct_change'})
        df['code'] = symbol

        logger.info(f"[FutuProvider] 日K获取成功 {symbol}: {len(df)} 条")
        return df

    def get_minute_bars(self, symbol: str, start_date: str, end_date: str, freq: int = 1) -> pd.DataFrame:
        """
        获取分钟K线数据

        Args:
            symbol: 股票代码，内部格式
            start_date: 开始日期 YYYY-MM-DD HH:MM:SS
            end_date: 结束日期 YYYY-MM-DD HH:MM:SS
            freq: 分钟周期，默认1分钟

        Returns:
            DataFrame，含 time_key / open / close / high / low / volume
        """
        self.connect()
        from futu import KLType, AuType

        # 富途支持 1/3/5/10/15/30/60 分钟K线
        kl_type_map = {1: KLType.K_1M, 3: KLType.K_3M, 5: KLType.K_5M,
                       10: KLType.K_10M, 15: KLType.K_15M, 30: KLType.K_30M, 60: KLType.K_60M}
        kl_type = kl_type_map.get(freq, KLType.K_1M)

        futu_code = self._convert_code(symbol, to_futu=True)

        ret, data, _ = self._quote_ctx.request_history_kline(
            futu_code,
            start=start_date,
            end=end_date,
            ktype=kl_type,
            autype=AuType.QFQ,
            max_count=1000,
        )

        if ret != 0:
            logger.error(f"get_minute_bars 失败 {symbol}: {data}")
            return pd.DataFrame()

        df = data[['time_key', 'open', 'close', 'high', 'low', 'volume', 'turnover', 'change_rate']].copy()
        df['time_key'] = pd.to_datetime(df['time_key'])
        df['code'] = symbol

        return df

    # ─── 股票列表 ──────────────────────────────────────────────

    def get_stock_list(self, market: str = "CN") -> List[str]:
        """
        获取市场全部股票代码列表

        Args:
            market: "CN" A股 / "HK" 港股 / "US" 美股

        Returns:
            股票代码列表，内部格式
        """
        self.connect()
        from futu import PlateType

        # 富途不支持直接获取A股全量列表，用板块列表代替
        if market == "CN":
            # A股：尝试用板块获取沪深股票
            try:
                ret, data = self._quote_ctx.get_plate_list("SH.SSE", PlateType.ALL)
                if ret == 0:
                    codes = [self._convert_code(f"SH.{r['code']}", to_futu=False) for _, r in data.iterrows()]
                    return codes
            except Exception:
                pass

            # 备用：返回常用指数成分
            logger.warning("[FutuProvider] A股全量列表不可用，返回主要股票")
            return ["CN.600000", "CN.600519", "CN.601318"]  # 茅台、平安等

        elif market == "HK":
            ret, data = self._quote_ctx.get_plate_list("HK.HS", PlateType.SECTOR)
            if ret == 0:
                return [self._convert_code(r['code'], to_futu=False) for _, r in data.iterrows()]

        elif market == "US":
            # 美股：返回主要指数ETF
            return ["US.QQQ", "US.SPY", "US.IWM", "US.SNDK", "US.GOOGL"]

        return []

    # ─── 基本面数据 ──────────────────────────────────────────────

    def get_fundamental(self, symbol: str) -> Dict:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码

        Returns:
            基本面数据字典
        """
        self.connect()

        futu_code = self._convert_code(symbol, to_futu=True)
        ret, data = self._quote_ctx.get_stock_info([futu_code])

        if ret != 0 or data.empty:
            return {}

        row = data.iloc[0]
        return {
            "code": symbol,
            "name": row.get("name", ""),
            "listing_date": row.get("listing_date", ""),
            "issued_shares": row.get("issued_shares", 0),
            "total_share": row.get("total_share", 0),
            "net_asset": row.get("net_asset", 0),
            "pe_ratio": row.get("pe_ratio", 0),
            "pb_ratio": row.get("pb_ratio", 0),
            "market_cap": row.get("market_cap", 0),
        }

    # ─── 批量数据 ──────────────────────────────────────────────

    def get_all_daily_bars(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票日线数据

        Returns:
            {symbol: DataFrame}
        """
        result = {}
        for i, sym in enumerate(symbols):
            df = self.get_daily_bars(sym, start_date, end_date)
            if not df.empty:
                result[sym] = df
            if i % 10 == 0:
                logger.info(f"批量获取进度: {i+1}/{len(symbols)}")
        return result

    # ─── 指数/大盘数据 ─────────────────────────────────────────

    def get_index_quote(self, index_code: str = "US.QQQ") -> Dict:
        """
        获取指数行情（用于大盘择时）

        Args:
            index_code: 指数代码，默认纳指100
        """
        data = self.get_stock_quote([index_code])
        if data.empty:
            return {}

        row = data.iloc[0]
        return {
            "code": index_code,
            "last_price": row.get("last_price"),
            "change_rate": row.get("change_rate"),
            "volume": row.get("volume"),
        }

    # ─── 数据源接口适配 ─────────────────────────────────────────

    def get_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """实现 BaseDataSource 接口"""
        return self.get_daily_bars(symbol, start_date, end_date)

    def get_minute(self, symbol: str, freq: int = 1) -> pd.DataFrame:
        """实现 BaseDataSource 接口（需要手动给日期范围）"""
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=30)
        return self.get_minute_bars(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), freq)

    def get_stock_list_by_market(self, market: str = "CN") -> List[str]:
        """获取市场全量股票列表"""
        return self.get_stock_list(market)

    def get_fundamental_data(self, symbol: str) -> dict:
        """获取基本面数据"""
        return self.get_fundamental(symbol)


if __name__ == "__main__":
    # 测试
    with FutuProvider() as provider:
        # 测试A股日K
        df = provider.get_daily_bars("CN.600000", "2026-04-01", "2026-04-30")
        print(f"A股日K: {len(df)} 条")
        print(df.head(3))

        # 测试港股日K
        df2 = provider.get_daily_bars("HK.00700", "2026-04-01", "2026-04-30")
        print(f"\n港股日K: {len(df2)} 条")
        print(df2.head(3))

        # 测试美股实时行情
        quotes = provider.get_stock_quote(["US.QQQ", "US.SNDK", "CN.600519"])
        print(f"\n实时行情: {len(quotes)} 条")
        print(quotes[['code', 'name', 'last_price', 'change_rate', 'volume']].to_string())
