
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

conditions = pd.Series(True, index=df.index)
# 1. exclude ST
conditions = conditions & (~df['is_st']) & (~df['is_suspended'])
# 2. exclude bad news
conditions = conditions & (~df['has_bad_news'])
# 3. cap
conditions = conditions & (df['circulate_cap'] >= picker3.params['min_cap'])
conditions = conditions & (df['circulate_cap'] <= picker3.params['max_cap'])
# 4. above ma20
if picker3.params['above_ma20']:
    conditions = conditions & (df['close'] > df['ma20'])
print(f"After above_ma20 (disabled):\n{conditions}")
# 5. ma20 up
if picker3.params['ma20_up']:
    conditions = conditions & (df['ma20'] > df['ma20_prev'])
print(f"After ma20_up:\n{conditions}")
# 6. change pct
conditions = conditions & (df['change_pct'] > picker3.params['min_daily_change'])
conditions = conditions & (df['change_pct'] < picker3.params['max_daily_change'])
print(f"After change_pct:\n{conditions}")
# 7. amplitude
amplitude = (df['high'] - df['low']) / df['open'] * 100
conditions = conditions & (amplitude > picker3.params['min_amplitude'])
print(f"After amplitude:\n{conditions}")
# 8. turnover
conditions = conditions & (df['turnover'] > picker3.params['min_turnover'])
conditions = conditions & (df['turnover'] < picker3.params['max_turnover'])
print(f"After turnover:\n{conditions}")
# 9. volume 5d
conditions = conditions & (df['volume'] > df['volume_5d_avg'] * picker3.params['volume_ratio_5d'])
print(f"After volume 5d:\n{conditions}")
# 10. volume ratio
conditions = conditions & (df['volume_ratio'] > picker3.params['min_volume_ratio'])
print(f"After volume ratio:\n{conditions}")
# 11. up 3d
if picker3.params['up_3d']:
    conditions = conditions & (df['change_3d'] > 0)
print(f"After up_3d:\n{conditions}")
# 12. consecutive limit
conditions = conditions & (df['consecutive_limit'] <= picker3.params['max_consecutive_limit'])
print(f"After consecutive limit:\n{conditions}")
# 13. late rally
if picker3.params['require_late_rally']:
    conditions = conditions & df['late_rally']
print(f"After late rally:\n{conditions}")
# 14. close near high
if picker3.params['close_near_high']:
    close_to_high = (df['high'] - df['close']) / df['high'] < 0.02
    print(f"close_to_high 000009: {(df.loc[2]['high'] - df.loc[2]['close']) / df.loc[2]['high']:.4f} < 0.02 → {((df.loc[2]['high'] - df.loc[2]['close']) / df.loc[2]['high'] < 0.02)}")
    conditions = conditions & close_to_high
print(f"After close_near_high:\n{conditions}")

print(f"\nFINAL conditions:")
print(conditions)
print(f"Count: {conditions.sum()}")

filtered = df[conditions].copy()
print(f"\nfiltered after conditions:")
print(filtered['code'])
