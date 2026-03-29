
import pandas as pd
import sys
sys.path.insert(0, '.')
from src.strategies.a_stock_evening import AStockEveningPicker

data = [
    {
        'code': '000001',
        'name': '测试股票1',
        'close': 10.5,
        'open': 10.0,
        'high': 10.6,
        'low': 9.9,
        'volume': 1000000,
        'turnover': 5.0,
        'amount': 10000000,
        'ma20': 10.0,
        'ma20_prev': 9.9,
        'change_pct': 5.0,
        'change_3d': 3.0,
        'volume_5d_avg': 600000,
        'volume_ratio': 1.67,
        'circulate_cap': 100e8,
        'consecutive_limit': 0,
        'is_st': False,
        'is_suspended': False,
        'has_bad_news': False,
        'late_rally': True,
    },
    {
        'code': '000002',
        'name': '测试股票2',
        'close': 20.0,
        'open': 19.0,
        'high': 20.2,
        'low': 18.8,
        'volume': 2000000,
        'turnover': 4.0,
        'amount': 40000000,
        'ma20': 19.5,
        'ma20_prev': 19.4,
        'change_pct': 5.26,
        'change_3d': 2.5,
        'volume_5d_avg': 1200000,
        'volume_ratio': 1.67,
        'circulate_cap': 200e8,
        'consecutive_limit': 1,
        'is_st': False,
        'is_suspended': False,
        'has_bad_news': False,
        'late_rally': True,
    },
]
df = pd.DataFrame(data)
df.loc[len(df)] = {
    'code': '000009',
    'name': '均线下方',
    'close': 9.5,
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

picker3 = AStockEveningPicker({'above_ma20': False, 'max_daily_select': 10})
filtered = picker3.filter_stocks(df)
print(f"filtered shape: {filtered.shape}")
print(f"codes: {list(filtered['code'])}")
print(filtered)
