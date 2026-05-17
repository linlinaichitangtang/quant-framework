"""
Qlib 数据提供模块
提供数据缓存和获取功能，供 QlibFactorEngine 等模块使用
"""

import os
import sys
import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta

# 确保项目根目录在 path 中
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.utils.logging import logger


class QlibDataCache:
    """
    Qlib 数据缓存层
    封装数据获取逻辑，支持历史数据缓存
    """
    
    def __init__(self, cache_dir: str = './cache/qlib', fetcher=None):
        """
        初始化
        :param cache_dir: 缓存目录
        :param fetcher: 数据获取器，如果为 None 则使用 TushareDataFetcher
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        if fetcher is None:
            # 导入 TushareDataFetcher
            from src.ml_strategy.data_fetcher import TushareDataFetcher
            self.fetcher = TushareDataFetcher()
        else:
            self.fetcher = fetcher
    
    def get_stock_data(self, 
                       ts_code: str, 
                       start_date: str, 
                       end_date: str,
                       use_cache: bool = True) -> pd.DataFrame:
        """
        获取股票日线数据
        :param ts_code: 股票代码 (tushare 格式, 如 600000.SH)
        :param start_date: 开始日期 YYYYMMDD
        :param end_date: 结束日期 YYYYMMDD
        :param use_cache: 是否使用缓存
        :return: DataFrame (trade_date, open, high, low, close, volume)
        """
        # 标准化日期格式
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')
        
        # 缓存文件路径
        cache_file = self.cache_dir / f"{ts_code}_{start_date}_{end_date}.csv"
        
        # 检查缓存
        if use_cache and cache_file.exists():
            logger.info(f"[QlibDataCache] 从缓存加载 {ts_code}")
            df = pd.read_csv(cache_file)
            return self._validate_format(df)
        
        # 通过 Tushare 获取数据
        logger.info(f"[QlibDataCache] 从 Tushare 获取 {ts_code} ({start_date} ~ {end_date})")
        df = self.fetcher.get_daily_data(ts_code, start_date, end_date)
        
        if df.empty:
            logger.warning(f"[QlibDataCache] 未获取到数据: {ts_code}")
            return pd.DataFrame()
        
        # 转换为统一格式
        df = self._convert_to_qlib_format(df)
        
        # 缓存到 CSV
        if use_cache:
            df.to_csv(cache_file, index=False)
            logger.info(f"[QlibDataCache] 已缓存到 {cache_file}")
        
        return df
    
    def _convert_to_qlib_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将 Tushare 格式转换为 Qlib 兼容格式
        Tushare 返回列: trade_date, open, high, low, close, vol
        目标列: trade_date, open, high, low, close, volume
        """
        # 确保有必要的列
        required_cols = ['trade_date', 'open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必要列: {col}")
        
        # 重命名 vol -> volume (如果存在)
        result = pd.DataFrame()
        result['trade_date'] = df['trade_date'].astype(str)
        result['open'] = df['open'].astype(float)
        result['high'] = df['high'].astype(float)
        result['low'] = df['low'].astype(float)
        result['close'] = df['close'].astype(float)
        
        if 'vol' in df.columns:
            result['volume'] = df['vol'].astype(float)
        elif 'volume' in df.columns:
            result['volume'] = df['volume'].astype(float)
        else:
            result['volume'] = 0.0
        
        return result
    
    def _validate_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证 DataFrame 格式是否正确"""
        expected_cols = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            raise ValueError(f"缓存格式错误，缺少列: {missing}")
        return df[expected_cols]
    
    def get_multiple_stocks(self, 
                            ts_codes: List[str], 
                            start_date: str, 
                            end_date: str) -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票数据
        :param ts_codes: 股票代码列表
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return: {ts_code: DataFrame}
        """
        result = {}
        for code in ts_codes:
            try:
                df = self.get_stock_data(code, start_date, end_date)
                if not df.empty:
                    result[code] = df
            except Exception as e:
                logger.error(f"[QlibDataCache] 获取 {code} 失败: {e}")
        return result
    
    def clear_cache(self, ts_code: Optional[str] = None):
        """
        清除缓存
        :param ts_code: 指定股票代码，为 None 则清除全部
        """
        if ts_code:
            for f in self.cache_dir.glob(f"{ts_code}_*.csv"):
                f.unlink()
            logger.info(f"[QlibDataCache] 已清除 {ts_code} 缓存")
        else:
            for f in self.cache_dir.glob("*.csv"):
                f.unlink()
            logger.info("[QlibDataCache] 已清除全部缓存")


def get_qlib_data_config() -> dict:
    """
    返回 Qlib Provider 配置说明
    供未来人工配置 qlib 的 MySQL/CSV provider 使用
    """
    return {
        "provider_type": "csv",
        "description": "Qlib 数据源配置 (Phase 2B)",
        "data_format": {
            "columns": ["$open", "$high", "$low", "$close", "$volume", "$factor"],
            "index": ["datetime", "instrument"],
        },
        "config": {
            "provider_uri": "qlib_data/csv_data",
            "cache": "mem",
        },
        "crawlers": {
            "tushare": {
                "data_source": "tushare_pro",
                "token_env": "TUSHARE_TOKEN",
                "description": "通过 Tushare Pro API 获取数据",
            }
        },
        "usage_example": """
# 1. 下载 qlib 历史数据
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn

# 2. 初始化 qlib
import qlib
qlib.init(provider_uri='~/.qlib/qlib_data/cn_data')

# 3. 使用 qlib 数据接口
from qlib.data import D
df = D.features(['SH600000'], ['$close', '$volume'], '2020-01-01', '2020-12-31')

# 4. 或使用 QlibDataCache (本模块) 作为备轨
from src.data.qlib_data_provider import QlibDataCache
cache = QlibDataCache()
df = cache.get_stock_data('600000.SH', '20200101', '20201231')
"""
    }


# ─── 单元测试 ──────────────────────────────────────────────

def _run_test():
    """简单测试：获取一只股票最近 60 个交易日数据"""
    import sys
    
    print("=" * 60)
    print("QlibDataCache 单元测试")
    print("=" * 60)
    
    cache = QlibDataCache()
    
    # 计算日期范围 (近 120 天，覆盖 60 个交易日)
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')
    
    ts_code = '000001.SZ'  # 平安银行
    
    print(f"\n测试: 获取 {ts_code} 从 {start_date} 到 {end_date}")
    
    try:
        df = cache.get_stock_data(ts_code, start_date, end_date)
        
        # 验证结果
        print(f"\n[OK] 获取成功")
        print(f"    行数: {len(df)}")
        print(f"    列名: {list(df.columns)}")
        print(f"    预期列: ['trade_date', 'open', 'high', 'low', 'close', 'volume']")
        
        # 验证列名
        expected_cols = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
        if list(df.columns) == expected_cols:
            print("    [OK] 列名匹配")
        else:
            print("    [FAIL] 列名不匹配!")
            return False
        
        # 验证行数
        if len(df) >= 10:
            print(f"    [OK] 数据行数 >= 10 (实际 {len(df)})")
        else:
            print(f"    [FAIL] 数据行数不足 (实际 {len(df)})")
            return False
        
        # 显示前 3 行
        print("\n    前 3 行数据:")
        print(df.head(3).to_string(index=False))
        
        # 验证数据类型
        print(f"\n    数据类型:")
        print(f"      trade_date: {df['trade_date'].dtype}")
        print(f"      open: {df['open'].dtype}")
        print(f"      close: {df['close'].dtype}")
        print(f"      volume: {df['volume'].dtype}")
        
        print("\n" + "=" * 60)
        print("全部测试通过!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[FAIL] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = _run_test()
    sys.exit(0 if success else 1)
