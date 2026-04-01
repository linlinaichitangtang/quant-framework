"""
数据模块
"""
from .cache import DataCache
from .factors import calculate_all_factors

# TushareProvider 需要安装 tushare 包
# 如果未安装则跳过导入
try:
    from .tushare_provider import TushareProvider
    _HAS_TUSHARE = True
except ImportError:
    _HAS_TUSHARE = False

__all__ = [
    'DataCache',
    'calculate_all_factors',
]

if _HAS_TUSHARE:
    __all__.append('TushareProvider')
