"""
富途(Futu) 数据获取模块
用于替换 TushareDataFetcher，获取A股/港股/美股行情数据
"""
import os
import pickle
from typing import List, Optional, Dict
from datetime import datetime
import pandas as pd
import numpy as np

# 富途 SDK
from futu.quote.open_quote_context import OpenQuoteContext
from futu.quote.quote_query import KLType, AuType, KL_FIELD


class FutuDataFetcher:
    """
    基于富途(Futu OpenD)的数据获取
    
    使用方式:
        # A股
        fetcher = FutuDataFetcher(market='CN')
        df = fetcher.get_daily_data('SH.600000', start_date='20230101', end_date='20240101')
        
        # 港股
        fetcher = FutuDataFetcher(market='HK')
        df = fetetcher.get_daily_data('HK.00700', start_date='20230101', end_date='20240101')
        
        # 美股
        fetcher = FutuDataFetcher(market='US')
        df = fetcher.get_daily_data('US.AAPL', start_date='20230101', end_date='20240101')
    """

    # 富途市场代码映射
    MARKET_MAP = {
        'CN': ('SH', 'SZ'),      # A股: 上交所SH, 深交所SZ
        'HK': ('HK',),           # 港股
        'US': ('US',),           # 美股
    }

    # A股交易所前缀
    EXCHANGE_MAP = {
        'SH': 'SH',  # 上交所
        'SZ': 'SZ',  # 深交所
        'HK': 'HK',  # 港交所
        'US': 'US',  # 美股
    }

    def __init__(self, host: str = '127.0.0.1', port: int = 11111,
                 market: str = 'CN', cache_dir: str = './cache'):
        """
        初始化富途行情连接
        
        :param host: Futu OpenD 主机地址 (默认本地)
        :param port: Futu OpenD 端口 (默认11111)
        :param market: 市场标识 'CN'=A股, 'HK'=港股, 'US'=美股
        :param cache_dir: 缓存目录
        """
        self.host = host
        self.port = port
        self.market = market.upper()
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        self._ctx: Optional[OpenQuoteContext] = None
        self._connect()
    
    def _connect(self):
        """建立富途连接"""
        self._ctx = OpenQuoteContext(self.host, self.port)
        
        # 获取用户信息验证连接
        ret, data = self._ctx.get_user_info()
        if ret != 0:
            raise ConnectionError(f"Futu连接失败: {data}")
        print(f"Futu连接成功: {data.get('user_id', 'unknown')}")
    
    def close(self):
        """关闭连接"""
        if self._ctx:
            self._ctx.close()
            self._ctx = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()

    def _cache_file(self, code: str, start_date: str, end_date: str) -> str:
        return f"{self.cache_dir}/futu_{self.market}_{code}_{start_date}_{end_date}.pkl"
    
    def _format_date(self, date_str: str) -> str:
        """
        将日期转换为富途所需的 YYYY-MM-DD 格式
        支持输入: 'YYYYMMDD', 'YYYY-MM-DD', 'YYYY/MM/DD'
        """
        date_str = date_str.strip().replace('/', '-')
        if len(date_str) == 8 and date_str.isdigit():
            # YYYYMMDD -> YYYY-MM-DD
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str
    
    def _normalize_code(self, code: str) -> str:
        """
        标准化股票代码为富途格式
        支持: '600000', 'SH.600000', '00700.HK', 'US.AAPL' 等格式
        
        注意: 美股代码(如'AAPL')会默认转为US市场，A股纯数字会按规则自动判断
        """
        code = code.strip()
        
        # 已经是富途格式，保持不变
        if '.' in code:
            return code.upper()
        
        # A股: 6位数字
        if len(code) == 6 and code.isdigit():
            if code.startswith('6'):
                return f"SH.{code}"
            elif code.startswith(('0', '3')):
                return f"SZ.{code}"
            elif code.startswith(('4', '8')):
                return f"BJ.{code}"  # 北交所
        
        # 港股: 5位数字
        if len(code) == 5 and code.isdigit():
            return f"HK.{code}"
        
        # 美股或其他: 纯字母(<=5位)默认US
        if len(code) <= 5 and code.isalpha():
            return f"US.{code.upper()}"
        
        # 其他情况原样返回
        return code

    def get_daily_data(self,
                       code: str,
                       start_date: str = '20180101',
                       end_date: str = None,
                       autype: str = 'qfq') -> pd.DataFrame:
        """
        获取日K线数据
        
        :param code: 股票代码 (支持多种格式)
            - A股: '600000', 'SH.600000', 'SZ.000001'
            - 港股: '00700', 'HK.00700'
            - 美股: 'AAPL', 'US.AAPL'
        :param start_date: 开始日期 'YYYYMMDD'
        :param end_date: 结束日期 'YYYYMMDD'，None表示今天
        :param autype: 复权类型 'qfq'=前复权, 'hfq'=后复权, 'None'=不复权
        :return: DataFrame with columns: [trade_date, open, high, low, close, volume, amount, turnover]
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 富途要求 YYYY-MM-DD 格式
        start_fmt = self._format_date(start_date)
        end_fmt = self._format_date(end_date)
        
        code = self._normalize_code(code)
        cache_file = self._cache_file(code, start_fmt, end_fmt)
        
        # 读缓存
        if os.path.exists(cache_file):
            print(f"Loading {code} from cache...")
            return pd.read_pickle(cache_file)
        
        if self._ctx is None:
            raise ConnectionError("Futu not connected")
        
        # 富途 K线类型
        ktype = KLType.K_DAY
        
        # 获取数据（分页获取，直到全部获取）
        all_klines = []
        page_key = None
        
        while True:
            ret, data, page_key = self._ctx.request_history_kline(
                code=code,
                start=start_fmt,
                end=end_fmt,
                ktype=ktype,
                autype=autype,  # qfq=前复权
                max_count=1000,
                page_req_key=page_key
            )
            
            if ret != 0:
                raise RuntimeError(f"获取K线失败 [{code}]: {data}")
            
            if data is not None and len(data) > 0:
                all_klines.append(data)
            
            if page_key is None:
                break

        
        if not all_klines:
            return pd.DataFrame()
        
        df = pd.concat(all_klines, ignore_index=True)
        
        # 标准化列名
        df = self._normalize_columns(df)
        
        # 排序并缓存
        df = df.sort_values('trade_date').reset_index(drop=True)
        df.to_pickle(cache_file)
        
        print(f"Fetched {len(df)} klines for {code}")
        return df
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化富途返回的列名"""
        # 富途返回的列名: time_key, open, close, high, low, pe_ratio, turnover(volume/成交额), volume, amount, change_rate, last_close
        # 标准化命名：
        #   time_key -> trade_date (日期，YYYYMMDD格式)
        #   turnover -> amount (成交额，单位元)
        #   volume -> volume (成交量，单位股)
        #   turnover_rate -> turnover (换手率，比例)
        rename_map = {
            'time_key': 'trade_date',
        }
        
        df = df.rename(columns=rename_map)
        
        # 确保日期格式统一 (YYYYMMDD)
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m%d')
        
        # 确保数值列类型正确
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df

    
    def get_stock_quote(self, code: str) -> pd.DataFrame:
        """
        获取股票实时报价
        
        :param code: 股票代码
        :return: DataFrame with 实时行情
        """
        code = self._normalize_code(code)
        
        ret, data, _ = self._ctx.get_stock_quote([code])
        if ret != 0:
            raise RuntimeError(f"获取报价失败 [{code}]: {data}")
        
        return data
    
    def get_market_snapshot(self, codes: List[str]) -> pd.DataFrame:
        """
        获取市场快照（批量股票）
        
        :param codes: 股票代码列表
        :return: DataFrame with 批量股票的实时数据
        """
        codes = [self._normalize_code(c) for c in codes]
        
        ret, data, _ = self._ctx.get_market_snapshot(codes)
        if ret != 0:
            raise RuntimeError(f"获取市场快照失败: {data}")
        
        return data

    
    def get_stock_basicinfo(self, market: str = 'SH') -> pd.DataFrame:
        """
        获取市场股票基本信息
        
        :param market: 市场 'SH'=上交所, 'SZ'=深交所, 'HK'=港交所, 'US'=纳斯达克/纽交所
        :return: 股票基本信息 DataFrame
        """
        ret, data, _ = self._ctx.get_stock_basicinfo(market, [''])
        if ret != 0:
            raise RuntimeError(f"获取股票列表失败: {data}")
        
        return data
    
    def get_trading_days(self, market: str = 'SH') -> List[str]:
        """
        获取交易日历
        
        :param market: 市场
        :return: 交易日列表 ['20240101', ...]
        """
        ret, data, _ = self._ctx.request_trading_days(market)
        if ret != 0:
            raise RuntimeError(f"获取交易日历失败: {data}")
        
        if data is not None:
            return data['time'].tolist() if 'time' in data.columns else []
        return []

    
    def get_multiple_stocks_daily(self,
                                  codes: List[str],
                                  start_date: str,
                                  end_date: str = None,
                                  autype: str = 'qfq') -> Dict[str, pd.DataFrame]:
        """
        批量获取多个股票的日线数据
        
        :param codes: 股票代码列表
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: {code: DataFrame}
        """
        result = {}
        for code in codes:
            try:
                df = self.get_daily_data(code, start_date, end_date, autype)
                if len(df) > 0:
                    result[code] = df
            except Exception as e:
                print(f"获取 {code} 失败: {e}")
                continue
        return result
    
    def get_history_kl_quota(self) -> dict:
        """查询历史K线剩余额度"""
        ret, data = self._ctx.get_history_kl_quota(get_detail=True)
        if ret != 0:
            return {'ret': ret, 'error': data}
        if isinstance(data, pd.DataFrame) and len(data) > 0:
            return data.iloc[0].to_dict()
        return {}




# 兼容性别名
TushareDataFetcher = FutuDataFetcher


def prepare_daily_candidates(daily_data: Dict[str, pd.DataFrame],
                            trade_date: str,
                            filter_rules: Optional[Dict] = None) -> pd.DataFrame:
    """
    准备某日的候选股票数据，合并所有因子
    与 TushareDataFetcher 版本兼容
    """
    candidates = []
    
    default_rules = {
        'min_change_pct': 3.0,
        'max_change_pct': 8.0,
        'min_amplitude': 4.0,
        'min_turnover': 3.0,
        'max_turnover': 20.0,
        'min_volume_ratio_5d': 1.5,
        'min_cap': 50e8,
        'max_cap': 500e8,
    }
    
    if filter_rules:
        default_rules.update(filter_rules)
    
    from .factor_extractor import FactorExtractor
    fe = FactorExtractor()
    
    for code, df in daily_data.items():
        day_df = df[df['trade_date'] == trade_date]
        if len(day_df) == 0:
            continue
        
        df_up_to_date = df[df['trade_date'] <= trade_date].copy()
        df_up_to_date = fe.extract_all_factors(df_up_to_date)[0]
        
        day_row = df_up_to_date[df_up_to_date['trade_date'] == trade_date]
        if len(day_row) > 0:
            candidates.append(day_row.iloc[0])
    
    result = pd.DataFrame(candidates)
    return result


if __name__ == '__main__':
    # 测试代码
    print("=== FutuDataFetcher 测试 ===")
    
    # 注意: 需要先启动 Futu OpenD
    try:
        with FutuDataFetcher(market='CN') as fetcher:
            # 获取A股日线数据测试
            df = fetcher.get_daily_data('SH.600000', start_date='20240101', end_date='20240131')
            print(f"\n获取到 {len(df)} 条数据")
            if len(df) > 0:
                print(df.tail())
            
            # 查询剩余额度
            quota = fetcher.get_history_kl_quota()
            print(f"\nK线额度: {quota}")
            
    except ConnectionError as e:
        print(f"连接失败: {e}")
        print("请确保 Futu OpenD 已启动并监听 127.0.0.1:11111")
    except Exception as e:
        print(f"错误: {e}")