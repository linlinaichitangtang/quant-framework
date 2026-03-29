"""
Pytest配置文件
定义测试夹具
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_stock_data():
    """创建示例股票数据用于选股测试"""
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
            'circulate_cap': 100e8,  # 100亿
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
            'circulate_cap': 200e8,  # 200亿
            'consecutive_limit': 1,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        },
        {
            'code': '000003',
            'name': 'ST测试',
            'close': 5.0,
            'open': 4.8,
            'high': 5.1,
            'low': 4.7,
            'volume': 500000,
            'turnover': 3.0,
            'amount': 2500000,
            'ma20': 4.9,
            'ma20_prev': 4.9,
            'change_pct': 4.17,
            'change_3d': 1.0,
            'volume_5d_avg': 300000,
            'volume_ratio': 1.67,
            'circulate_cap': 50e8,  # 50亿
            'consecutive_limit': 0,
            'is_st': True,  # ST股票，应该被排除
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        },
        {
            'code': '000004',
            'name': '涨幅不达标',
            'close': 10.1,
            'open': 10.0,
            'high': 10.3,
            'low': 9.9,
            'volume': 800000,
            'turnover': 4.0,
            'amount': 8000000,
            'ma20': 9.9,
            'ma20_prev': 9.8,
            'change_pct': 1.0,  # 涨幅不足3%，应该被排除
            'change_3d': 2.0,
            'volume_5d_avg': 500000,
            'volume_ratio': 1.6,
            'circulate_cap': 150e8,
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        },
        {
            'code': '000005',
            'name': '超大盘',
            'close': 10.0,
            'open': 9.8,
            'high': 10.2,
            'low': 9.7,
            'volume': 5000000,
            'turnover': 2.0,  # 换手率不足3%
            'amount': 50000000,
            'ma20': 9.9,
            'ma20_prev': 9.8,
            'change_pct': 4.08,
            'change_3d': 3.0,
            'volume_5d_avg': 3000000,
            'volume_ratio': 1.67,
            'circulate_cap': 600e8,  # 600亿超过上限，应该被排除
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        },
        {
            'code': '000006',
            'name': '利空股票',
            'close': 15.0,
            'open': 14.5,
            'high': 15.2,
            'low': 14.3,
            'volume': 1500000,
            'turnover': 6.0,
            'amount': 22500000,
            'ma20': 14.0,
            'ma20_prev': 13.9,
            'change_pct': 3.45,
            'change_3d': 2.0,
            'volume_5d_avg': 900000,
            'volume_ratio': 1.67,
            'circulate_cap': 150e8,
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': True,  # 有利空，应该被排除
            'late_rally': True,
        },
        {
            'code': '000007',
            'name': '均线向下',
            'close': 10.0,
            'open': 9.5,
            'high': 10.2,
            'low': 9.4,
            'volume': 1200000,
            'turnover': 5.0,
            'amount': 12000000,
            'ma20': 10.1,
            'ma20_prev': 10.2,  # 均线向下，应该被排除
            'change_pct': 5.26,
            'change_3d': 4.0,
            'volume_5d_avg': 700000,
            'volume_ratio': 1.71,
            'circulate_cap': 120e8,
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': True,
        },
        {
            'code': '000008',
            'name': '尾盘未拉升',
            'close': 10.0,
            'open': 9.8,
            'high': 10.3,
            'low': 9.4,
            'volume': 1000000,
            'turnover': 4.5,
            'amount': 10000000,
            'ma20': 9.8,
            'ma20_prev': 9.7,
            'change_pct': 4.08,
            'change_3d': 3.0,
            'volume_5d_avg': 600000,
            'volume_ratio': 1.67,
            'circulate_cap': 100e8,
            'consecutive_limit': 0,
            'is_st': False,
            'is_suspended': False,
            'has_bad_news': False,
            'late_rally': False,  # 尾盘未拉升，应该被排除
        },
    ]
    return pd.DataFrame(data)


@pytest.fixture
def empty_positions():
    """空持仓"""
    return {}


@pytest.fixture
def sample_positions():
    """示例持仓数据"""
    return {
        '000001': {
            'quantity': 1000,
            'cost': 10.0,
            'current_price': 10.5,
            'is_today_open': True,
            'sector': '银行',
        },
        '000002': {
            'quantity': 500,
            'cost': 20.0,
            'current_price': 19.8,
            'is_today_open': True,
            'sector': '地产',
        }
    }
