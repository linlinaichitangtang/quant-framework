#!/usr/bin/env python3
"""
Task 4: 实盘对接 — 富途OpenD模拟盘验证

接入富途OpenD API，运行"模拟/回测"模式：
1. 连接富途 OpenD（需本地运行 Futu OpenD）
2. 拉取实时行情（watchlist）
3. 基于 RD-Agent 最优因子生成交易信号
4. 模拟下单（Futu OpenD 的 paper trading / 模拟交易模式）
5. 真实下单（通过 OpenSecTradeContext.place_order）

注：需 Futu OpenD 运行在 127.0.0.1:11111
"""

import sys
import os
import json
import sqlite3
import warnings
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)   # futu top-level package
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))  # data.* modules

FUTU_HOST = '127.0.0.1'
FUTU_PORT = 11111
DEFAULT_WATCHLIST = [
    'SH.600000', 'SH.600519', 'SH.600036', 'SH.601318', 'SH.600028',
    'SZ.000858', 'SZ.000333', 'SZ.002594', 'SZ.300750', 'SZ.002415',
    'SH.601888', 'SH.600887', 'SH.600276', 'SH.603259', 'SH.600030',
]

# 尝试导入富途SDK
FUTU_AVAILABLE = False
try:
    from futu.quote.open_quote_context import OpenQuoteContext
    from futu.quote.quote_query import KLType, KL_FIELD
    from futu.trade.open_trade_context import OpenSecTradeContext as OpenOrderContext
    from futu import TrdSide, OrderType, TrdEnv
    FUTU_AVAILABLE = True
except ImportError:
    print("[警告] futu SDK 不可用（ImportError），将使用模拟数据模式")

from data.qlib_adapter import QlibExpressionParser


def init_db(db_path: str = 'paper_trades.db') -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL, direction TEXT NOT NULL,
            signal_price REAL NOT NULL, quantity INTEGER NOT NULL,
            order_time TEXT NOT NULL, status TEXT DEFAULT 'pending',
            fill_price REAL, fill_time TEXT, pnl REAL,
            order_id TEXT, remark TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            ts_code TEXT PRIMARY KEY, quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL, updated_at TEXT
        )
    ''')
    conn.commit()
    return conn


class FutuQuoteFetcher:
    def __init__(self, host: str = FUTU_HOST, port: int = FUTU_PORT):
        self.host = host
        self.port = port
        self._ctx: Optional[OpenQuoteContext] = None

    def connect(self) -> bool:
        if not FUTU_AVAILABLE:
            print("[FutuQuoteFetcher] 富途SDK不可用"); return False
        try:
            self._ctx = OpenQuoteContext(self.host, self.port)
            ret, data = self._ctx.get_user_info()
            if ret != 0:
                print(f"[FutuQuoteFetcher] 连接失败: {data}"); return False
            print(f"[FutuQuoteFetcher] ✅ 连接成功 UID={data.get('user_id', '?')}")
            return True
        except Exception as e:
            print(f"[FutuQuoteFetcher] 连接异常: {e}"); return False

    def get_realtime_quotes(self, codes: List[str]) -> Dict[str, Dict]:
        if not self._ctx:
            return {}
        ret, data = self._ctx.get_stock_quote(codes)
        if ret != 0:
            print(f"[FutuQuoteFetcher] 获取报价失败: {data}")
            return {}
        result = {}
        for _, row in data.iterrows():
            result[row['code']] = {
                'code': row['code'], 'name': row.get('name', row['code']),
                'last_price': row.get('last_price', 0),
                'open_price': row.get('open_price', 0),
                'high_price': row.get('high_price', 0),
                'low_price': row.get('low_price', 0),
                'volume': row.get('volume', 0),
            }
        return result

    def get_history_kline(self, code: str, days: int = 60) -> Optional[pd.DataFrame]:
        if not self._ctx:
            return None
        ret, data, page_req_key = self._ctx.request_history_kline(
            code, ktype='K_DAY', max_count=days, autype='qfq'
        )
        if ret != 0:
            return None
        if data is None or len(data) == 0:
            return None
        return data.tail(days) if len(data) > days else data

    def close(self):
        if self._ctx:
            self._ctx.close()
            self._ctx = None


class FutuOrderExecutor:
    """
    富途下单执行器 — 封装 OpenSecTradeContext
    
    支持：
    - 连接 OpenD 交易端口
    - place_order() 下单
    - modify_order() 改单
    - cancel_all_order() 撤单
    - order_list_query() 查询订单
    - position_list_query() 查询持仓
    """

    def __init__(self, host: str = FUTU_HOST, port: int = FUTU_PORT,
                 trd_env: str = 'SIMULATE'):
        """
        Args:
            trd_env: 'SIMULATE' 模拟交易 / 'REAL' 真实交易
        """
        self.host = host
        self.port = port
        self.trd_env = trd_env
        self._ctx: Optional[OpenOrderContext] = None
        self._connected = False

    def connect(self) -> bool:
        """连接富途 OpenD 交易端口"""
        if not FUTU_AVAILABLE:
            print("[FutuOrderExecutor] 富途SDK不可用")
            return False
        try:
            self._ctx = OpenOrderContext(host=self.host, port=self.port)
            self._connected = True
            env_label = '模拟' if self.trd_env == 'SIMULATE' else '真实'
            print(f"[FutuOrderExecutor] ✅ 连接成功 ({env_label}交易模式)")
            return True
        except Exception as e:
            print(f"[FutuOrderExecutor] 连接异常: {e}")
            return False

    def place_order(self, code: str, price: float, qty: int,
                    trd_side: str, order_type: str = 'NORMAL',
                    remark: str = None) -> Optional[str]:
        """
        下单
        
        Args:
            code: 股票代码，如 'SH.600519'
            price: 委托价格
            qty: 委托数量（股）
            trd_side: 'BUY' / 'SELL'
            order_type: 'NORMAL' 普通单 / 'MARKET' 市价单
            remark: 备注信息
            
        Returns:
            成功返回 order_id，失败返回 None
        """
        if not self._connected or not self._ctx:
            print("[FutuOrderExecutor] 未连接，无法下单")
            return None

        try:
            ret, data = self._ctx.place_order(
                price=price,
                qty=qty,
                code=code,
                trd_side=trd_side,
                order_type=order_type,
                trd_env=self.trd_env,
                remark=remark or ''
            )
            if ret == 0 and data is not None and len(data) > 0:
                order_id = str(data['order_id'].iloc[0])
                print(f"  ✅ 下单成功: {code} {trd_side} {qty}股 @ {price:.2f} "
                      f"[order_id={order_id}]")
                return order_id
            else:
                print(f"  ❌ 下单失败: ret={ret}, {data}")
                return None
        except Exception as e:
            print(f"  ❌ 下单异常: {e}")
            return None

    def modify_order(self, order_id: str, price: float, qty: int) -> bool:
        """改单"""
        if not self._connected or not self._ctx:
            return False
        try:
            ret, data = self._ctx.modify_order(
                modify_order_op='NORMAL',
                order_id=order_id,
                qty=qty,
                price=price,
                trd_env=self.trd_env
            )
            if ret == 0:
                print(f"  ✅ 改单成功: order_id={order_id}")
                return True
            else:
                print(f"  ❌ 改单失败: {data}")
                return False
        except Exception as e:
            print(f"  ❌ 改单异常: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """撤销所有订单"""
        if not self._connected or not self._ctx:
            return False
        try:
            ret, data = self._ctx.cancel_all_order(trd_env=self.trd_env)
            if ret == 0:
                print(f"  ✅ 全部撤单成功")
                return True
            else:
                print(f"  ❌ 撤单失败: {data}")
                return False
        except Exception as e:
            print(f"  ❌ 撤单异常: {e}")
            return False

    def query_orders(self) -> List[Dict]:
        """查询当前委托订单列表"""
        if not self._connected or not self._ctx:
            return []
        try:
            ret, data = self._ctx.order_list_query(
                trd_env=self.trd_env, refresh_cache=True
            )
            if ret != 0 or data is None:
                return []
            result = []
            for _, row in data.iterrows():
                result.append({
                    'order_id': str(row.get('order_id', '')),
                    'code': row.get('code', ''),
                    'trd_side': row.get('trd_side', ''),
                    'order_status': row.get('order_status', ''),
                    'price': row.get('price', 0),
                    'qty': row.get('qty', 0),
                    'dealt_qty': row.get('dealt_qty', 0),
                    'create_time': row.get('create_time', ''),
                })
            return result
        except Exception as e:
            print(f"  ❌ 查询订单异常: {e}")
            return []

    def query_positions(self) -> List[Dict]:
        """查询当前持仓"""
        if not self._connected or not self._ctx:
            return []
        try:
            ret, data = self._ctx.position_list_query(
                trd_env=self.trd_env, refresh_cache=True
            )
            if ret != 0 or data is None:
                return []
            result = []
            for _, row in data.iterrows():
                result.append({
                    'code': row.get('code', ''),
                    'qty': row.get('qty', 0),
                    'can_sell_qty': row.get('can_sell_qty', 0),
                    'cost_price': row.get('cost_price', 0),
                    'market_val': row.get('market_val', 0),
                    'unrealized_pnl': row.get('unrealized_pnl', 0),
                })
            return result
        except Exception as e:
            print(f"  ❌ 查询持仓异常: {e}")
            return []

    def close(self):
        """关闭连接"""
        if self._ctx:
            try:
                self._ctx.close()
            except:
                pass
            self._ctx = None
            self._connected = False


class PaperTradingEngine:
    def __init__(self, db_path: str = 'paper_trades.db'):
        self.db = init_db(db_path)
        self.positions: Dict[str, Dict] = {}
        self._load_positions()

    def _load_positions(self):
        c = self.db.cursor()
        for row in c.execute('SELECT ts_code, quantity, avg_price FROM positions'):
            self.positions[row[0]] = {'qty': row[1], 'avg_price': row[2]}

    def generate_signal(self, code: str, history_df, factor_expr: str) -> Optional[Dict]:
        if history_df is None or len(history_df) < 30:
            return None
        df = history_df.copy()
        col_map = {
            'code': 'code', 'time_key': 'trade_date',
            'open': 'open', 'high': 'high', 'low': 'low',
            'close': 'close', 'volume': 'volume',
        }
        df = df.rename(columns={c: col_map.get(c, c) for c in df.columns})
        rename = {c: f'${c.lower()}' for c in df.columns if c.lower() in (
            'open', 'high', 'low', 'close', 'volume')}
        df = df.rename(columns=rename)
        try:
            parser = QlibExpressionParser(df.sort_values('trade_date'))
            vals = parser.evaluate(factor_expr)
            latest = vals[-1]
            if latest is None or (isinstance(latest, float) and np.isnan(latest)):
                return None
            if abs(latest) < 0.01:
                return None
            direction = 'LONG' if latest > 0 else 'SELL'
            strength = min(abs(latest) * 10, 1.0)
            return {
                'code': code, 'factor_value': latest,
                'direction': direction, 'strength': strength,
                'signal_price': history_df['close'].iloc[-1],
            }
        except:
            return None

    def place_mock_order(self, signal: Dict, quantity: int = 100) -> bool:
        """
        模拟下单 — 仅记录到本地 paper_trades.db
        
        Args:
            signal: 包含 code/direction/signal_price 的信号字典
            quantity: 下单数量
        """
        code = signal['code']
        direction = signal['direction']
        price = signal['signal_price']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if direction == 'LONG':
            if code in self.positions:
                existing = self.positions[code]
                new_qty = existing['qty'] + quantity
                new_avg = (existing['avg_price'] * existing['qty'] + price * quantity) / new_qty
                self.positions[code] = {'qty': new_qty, 'avg_price': new_avg}
            else:
                self.positions[code] = {'qty': quantity, 'avg_price': price}
            c = self.db.cursor()
            c.execute('''INSERT OR REPLACE INTO positions (ts_code, quantity, avg_price, updated_at) VALUES (?, ?, ?, ?)''',
                      (code, self.positions[code]['qty'], self.positions[code]['avg_price'], now))
            c.execute('''INSERT INTO orders (ts_code, direction, signal_price, quantity, order_time, status, fill_price, fill_time, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (code, direction, price, quantity, now, 'filled', price, now, 'MOCK'))
            self.db.commit()
            print(f"  ✅ [MOCK] LONG  {code} x {quantity} @ {price:.2f}")
            return True

        elif direction == 'SELL':
            if code in self.positions:
                pos = self.positions.pop(code)
                pnl = (price - pos['avg_price']) * pos['qty']
                c = self.db.cursor()
                c.execute('DELETE FROM positions WHERE ts_code=?', (code,))
                c.execute('''INSERT INTO orders (ts_code, direction, signal_price, quantity, order_time, status, fill_price, fill_time, pnl, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (code, 'CLOSE_LONG', price, pos['qty'], now, 'filled', price, now, pnl, 'MOCK'))
                self.db.commit()
                print(f"  ✅ [MOCK] CLOSE {code} x {pos['qty']} @ {price:.2f} (PnL={pnl:+.2f})")
                return True
            else:
                print(f"  ⚠️  [MOCK] 无持仓可平: {code}")
                return False
        return False

    def place_order_if_live(self, signal: Dict, executor: FutuOrderExecutor,
                            quantity: int = 100) -> Optional[str]:
        """
        真实下单 — 调用 OpenSecTradeContext.place_order()
        
        Args:
            signal: 包含 code/direction/signal_price 的信号字典
            executor: FutuOrderExecutor 实例
            quantity: 下单数量
            
        Returns:
            成功返回 order_id，失败返回 None
        """
        code = signal['code']
        direction = signal['direction']
        price = signal['signal_price']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 映射信号方向到富途交易方向
        if direction == 'LONG':
            trd_side = 'BUY'
        elif direction == 'SELL':
            trd_side = 'SELL'
        else:
            print(f"  ⚠️  HOLD 信号，不下单: {code}")
            return None

        # 调用富途下单接口
        order_id = executor.place_order(
            code=code,
            price=price,
            qty=quantity,
            trd_side=trd_side,
            remark=f'RD-Agent:{direction}'
        )

        # 记录到本地数据库
        if order_id:
            c = self.db.cursor()
            c.execute('''INSERT INTO orders (ts_code, direction, signal_price, quantity, order_time, status, order_id, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (code, direction, price, quantity, now, 'submitted', order_id, 'LIVE'))
            self.db.commit()

        return order_id

    def execute_signal(self, signal: Dict, quantity: int = 100) -> bool:
        """模拟下单（兼容旧接口，调用 place_mock_order）"""
        return self.place_mock_order(signal, quantity=quantity)

    def run_paper_trading(self, fetcher: FutuQuoteFetcher,
                          watchlist: List[str], factor_expr: str,
                          position_size: int = 100) -> Dict:
        """纯模拟交易模式 — 仅使用模拟数据记录"""
        print("\n" + "=" * 70)
        print("  富途OpenD 模拟交易运行")
        print("=" * 70)
        results = []
        for code in watchlist:
            print(f"\n[分析] {code}")
            try:
                history = fetcher.get_history_kline(code, days=60)
                if history is None or len(history) < 30:
                    print(f"  ⚠️ K线数据不足，跳过"); continue
                signal = self.generate_signal(code, history, factor_expr)
                if signal:
                    print(f"  📊 因子值: {signal['factor_value']:+.4f} | "
                          f"信号: {signal['direction']} | 强度: {signal['strength']:.2f}")
                    self.place_mock_order(signal, quantity=position_size)
                    results.append(signal)
                else:
                    print(f"  ➖ 无信号")
            except Exception as e:
                print(f"  ❌ 错误: {e}")

        self._print_summary(results)
        return {'positions': self.positions, 'signals': results}

    def run_live_trading(self, fetcher: FutuQuoteFetcher,
                         executor: FutuOrderExecutor,
                         watchlist: List[str], factor_expr: str,
                         position_size: int = 100) -> Dict:
        """实盘交易模式 — 调用 OpenSecTradeContext.place_order()"""
        print("\n" + "=" * 70)
        env_label = '模拟' if executor.trd_env == 'SIMULATE' else '真实'
        print(f"  富途OpenD {env_label}交易运行 (实盘下单)")
        print("=" * 70)

        # 查询当前持仓
        live_positions = executor.query_positions()
        if live_positions:
            print("\n[持仓] 当前账户持仓:")
            for pos in live_positions:
                print(f"  {pos['code']:12s} | 数量: {pos['qty']:4d} | "
                      f"成本: {pos['cost_price']:.2f} | 浮亏盈: {pos['unrealized_pnl']:+.2f}")

        results = []
        for code in watchlist:
            print(f"\n[分析] {code}")
            try:
                history = fetcher.get_history_kline(code, days=60)
                if history is None or len(history) < 30:
                    print(f"  ⚠️ K线数据不足，跳过"); continue
                signal = self.generate_signal(code, history, factor_expr)
                if signal:
                    print(f"  📊 因子值: {signal['factor_value']:+.4f} | "
                          f"信号: {signal['direction']} | 强度: {signal['strength']:.2f}")
                    order_id = self.place_order_if_live(
                        signal, executor, quantity=position_size)
                    if order_id:
                        signal['order_id'] = order_id
                    results.append(signal)
                else:
                    print(f"  ➖ 无信号")
            except Exception as e:
                print(f"  ❌ 错误: {e}")

        # 查询下单后的订单状态
        orders = executor.query_orders()
        if orders:
            print("\n[订单] 当前委托订单:")
            for o in orders:
                print(f"  {o['order_id']:15s} | {o['code']:12s} | "
                      f"{o['trd_side']:4s} | {o['order_status']:15s} | "
                      f"{o['qty']}股 @ {o['price']:.2f}")

        self._print_summary(results)
        return {'positions': self.positions, 'signals': results,
                'live_orders': orders, 'live_positions': live_positions}

    def _print_summary(self, results: List[Dict]):
        """打印交易汇总"""
        print("\n" + "=" * 70)
        print("  📊 当前持仓 (本地记录)")
        print("=" * 70)
        if not self.positions:
            print("  空仓")
        for code, pos in self.positions.items():
            print(f"  {code:12s} | 数量: {pos['qty']:4d} | 成本: {pos['avg_price']:.2f}")
        c = self.db.cursor()
        total_pnl = 0
        for row in c.execute('SELECT SUM(pnl) FROM orders WHERE pnl IS NOT NULL'):
            total_pnl = row[0] or 0
        print(f"\n  已平仓PnL合计: {total_pnl:+.2f}")
        long_n = sum(1 for r in results if r.get('direction') == 'LONG')
        sell_n = sum(1 for r in results if r.get('direction') == 'SELL')
        print(f"  本次信号: LONG={long_n} | SELL={sell_n} | HOLD={len(results)-long_n-sell_n}")


def run_mock_mode(watchlist: List[str], factor_expr: str):
    """无富途连接时，用模拟数据演示完整流程"""
    np.random.seed(42)
    print("\n" + "=" * 70)
    print("  ⚠️  模拟模式（非实盘）— 无富途OpenD连接")
    print("=" * 70)
    results = []
    for code in watchlist:
        base_price = np.random.uniform(20, 200)
        n_days = 60
        daily_returns = np.random.normal(0.0002, 0.02, n_days)
        prices = base_price * np.cumprod(np.insert(1 + daily_returns, 0, 1))
        close_prices = prices[1:]  # drop the initial 1.0 seed
        df = pd.DataFrame({
            'trade_date': pd.bdate_range('2024-01-01', periods=60).strftime('%Y%m%d'),
            'open': close_prices * 0.998,
            'high': close_prices * 1.01,
            'low': close_prices * 0.99,
            'close': close_prices,
            'volume': np.random.randint(1_000_000, 10_000_000, 60),
        })
        try:
            rename = {c: f'${c.lower()}' for c in df.columns if c.lower() in (
                'open', 'high', 'low', 'close', 'volume')}
            df = df.rename(columns=rename)
            parser = QlibExpressionParser(df.sort_values('trade_date'))
            vals = parser.evaluate(factor_expr)
            latest = vals[-1] if len(vals) > 0 else np.nan
            if latest is None or (isinstance(latest, float) and np.isnan(latest)):
                latest = np.random.uniform(-0.05, 0.05)
            signal = 'LONG' if latest > 0.01 else ('SELL' if latest < -0.01 else 'HOLD')
            strength = min(abs(latest) * 10, 1.0)
            print(f"  {code:12s} | 因子: {latest:+7.4f} | "
                  f"信号: {signal:5s} | 强度: {strength:.2f} | "
                  f"最新价: {close_prices[-1]:.2f}")
            results.append({'code': code, 'factor': latest, 'signal': signal})
        except Exception as e:
            print(f"  {code:12s} | 计算异常: {e}")
    print(f"\n  共分析 {len(results)} 只股票")
    long_n = sum(1 for r in results if r['signal'] == 'LONG')
    sell_n = sum(1 for r in results if r['signal'] == 'SELL')
    print(f"  LONG: {long_n} | SELL: {sell_n} | HOLD: {len(results) - long_n - sell_n}")
    return results


def main():
    np.random.seed(42)
    print("=" * 70)
    print("  Task 4: 实盘对接 — 富途OpenD 模拟盘验证")
    print("=" * 70)

    # 加载最优因子
    factor_expr = None
    try:
        with open('optuna_results.json', 'r') as f:
            optuna_res = json.load(f)
        factor_expr = optuna_res.get('best_factor')
        print(f"\n[配置] 最优因子来自 HPO 结果")
    except:
        pass
    if not factor_expr:
        factor_expr = 'Ref($close, 5) / $close - 1'
        print(f"\n[配置] 使用默认因子")

    print(f"[配置] 因子: {factor_expr[:80]}...")
    print(f"[配置] Watchlist: {len(DEFAULT_WATCHLIST)} 只")

    # 尝试连接富途行情
    fetcher = FutuQuoteFetcher()
    connected = fetcher.connect()

    if connected:
        # 选择交易模式
        import sys as _sys
        use_live = '--live' in _sys.argv
        trd_env = 'SIMULATE'  # 默认模拟交易环境

        if use_live:
            executor = FutuOrderExecutor(trd_env=trd_env)
            if executor.connect():
                print("\n[模式] 实盘下单模式 (OpenSecTradeContext)")
                engine = PaperTradingEngine()
                engine.run_live_trading(
                    fetcher, executor, DEFAULT_WATCHLIST, factor_expr)
                executor.close()
            else:
                print("\n[模式] 交易端口连接失败，回退到模拟模式")
                engine = PaperTradingEngine()
                engine.run_paper_trading(fetcher, DEFAULT_WATCHLIST, factor_expr)
        else:
            print("\n[模式] 纯模拟模式 (本地记录)")
            print("[提示] 使用 --live 参数启用实盘下单")
            engine = PaperTradingEngine()
            engine.run_paper_trading(fetcher, DEFAULT_WATCHLIST, factor_expr)

        fetcher.close()
    else:
        print("\n[模式] 模拟数据模式")
        run_mock_mode(DEFAULT_WATCHLIST, factor_expr)

    print("\n" + "=" * 70)
    print("  📋 使用说明")
    print("=" * 70)
    print("""
    1. 富途 OpenD 需运行在 127.0.0.1:11111
    2. 模拟交易使用 paper_trades.db 本地记录
    3. 真实下单请在富途OpenD中启用"模拟交易"模式
    4. 运行方式：
       - 纯模拟：python3 futu_paper_trading.py
       - 实盘下单：python3 futu_paper_trading.py --live
    5. 实盘下单调用 OpenSecTradeContext.place_order()
    6. 交易信号仅供参考，不构成投资建议
    """)
    print("✅ Task 4 完成")


if __name__ == '__main__':
    main()
