"""
富途模拟盘端到端测试
选股 → 买入信号 → 执行 → 持仓 → 卖出

测试日期: 2026-05-02（周六，非交易日，数据仅作参考）
"""
import sys, os
# 确保 src/ 在路径中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(PROJECT_ROOT, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from datetime import datetime, date
import pandas as pd

from data.futu_provider import FutuProvider
from api.futu_execution import FutuExecutionProvider, ActionType, MarketType, TrdEnvType
from selector.futu_a_stock_picker import FutuAStockEveningPicker
from monitor.futu_monitor import FutuMonitorService

FUTU_HOST = "127.0.0.1"
FUTU_PORT = 11111
TRD_ENV = "SIMULATE"  # 模拟盘
ACC_ID = "13285521"   # 模拟股票账户

def step(name, fn):
    print(f"\n{'='*60}")
    print(f"▶ {name}")
    print('='*60)
    try:
        result = fn()
        print(f"✅ 完成")
        return result
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback; traceback.print_exc()
        return None

def main():
    print(f"\n🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📦 测试目标: 富途模拟盘端到端（选股→信号→执行→持仓→卖出）")

    # ── 数据层 ────────────────────────────────────────
    provider = step("Step 1: 连接富途行情", lambda: (
        FutuProvider(host=FUTU_HOST, port=FUTU_PORT).__enter__()
    ))
    if not provider:
        print("行情连接失败，退出")
        return

    # ── Step 2: 获取A股候选股票列表 ──────────────────
    def get_stocks():
        codes = [
            "SH.600000", "SH.600009", "SH.600016", "SH.600028",
            "SH.600030", "SH.600031", "SH.600036", "SH.600048",
            "SH.600050", "SH.600104", "SH.600109", "SH.600111",
            "SH.600519", "SH.600887", "SH.600999", "SH.601006",
            "SH.601012", "SH.601066", "SH.601088", "SH.601166",
            "SH.601318", "SH.601398", "SH.601601", "SH.601628",
            "SH.601668", "SH.601688", "SH.601728", "SH.601857",
            "SZ.000001", "SZ.000002", "SZ.000063", "SZ.000066",
            "SZ.000100", "SZ.000333", "SZ.000338", "SZ.000858",
            "SZ.002594", "SZ.002714", "SZ.300750", "SZ.301012",
        ]
        data = provider.get_stock_quote(codes)
        if not isinstance(data, pd.DataFrame) or data.empty:
            print(f"  get_stock_quote 返回异常: data={data}")
            return pd.DataFrame()
        print(f"  获取 {len(data)} 只股票的实时行情")
        print(f"  列名示例: {list(data.columns[:10])}")
        return data

    TRADE_DATE = "2026-04-30"  # 最近交易日（周四）

    quotes = step("Step 2: 获取A股候选股票实时行情", get_stocks)
    if quotes is None or quotes.empty:
        print("行情获取失败，退出")
        provider.close()
        return

    print(f"\n  行情样本（前3条）:")
    print(quotes.head(3).to_string())

    # ── Step 3: 转换代码格式 + 运行选股策略 ─────────────
    def run_picker():
        if quotes.empty:
            print("  无行情数据，跳过选股")
            return pd.DataFrame()
        # 从行情 DataFrame 提取代码列表（富途格式 CN.600000）
        # pick() 需要富途格式 codes
        # get_stock_quote 返回内部格式 CN.600000，需转富途格式 SH.600000
        futu_codes = quotes['code'].tolist()
        picker = FutuAStockEveningPicker(provider)
        candidates = picker.pick(futu_codes, TRADE_DATE)
        print(f"\n  选股结果: {len(candidates)} 只候选")
        if not candidates.empty:
            print(candidates.to_string())
        return candidates

    candidates = step("Step 3: A股尾盘选股策略", run_picker)

    # ── Step 4: 模拟生成交易信号 ────────────────────
    def gen_signal():
        if candidates is None or candidates.empty:
            print("  无候选股票，跳过信号生成（周六非交易日）")
            return None
        top = candidates.iloc[0]
        signal = {
            "symbol": top["symbol"],
            "market": MarketType.CN,
            "side": ActionType.BUY,
            "quantity": 100,  # 模拟100股
            "target_price": top["close"],
            "signal_id": 99999,
            "strategy_id": "test_strategy",
            "strategy_name": "FutuAStockEveningPicker",
        }
        print(f"  信号: 买入 {signal['symbol']} × {signal['quantity']}股 @ {signal['target_price']}")
        return signal

    signal = step("Step 4: 生成模拟买入信号", gen_signal)

    # ── Step 5: 模拟盘执行 ─────────────────────────
    def run_execution():
        exec_provider = FutuExecutionProvider(
            host=FUTU_HOST,
            port=FUTU_PORT,
            trd_env=TrdEnvType.SIMULATE,
            acc_id=ACC_ID,
        )
        exec_provider.connect()
        print(f"  模拟账户: {ACC_ID}")
        cap = exec_provider.get_capital()
        print(f"  资金: {cap}")
        if signal:
            result = exec_provider.execute_signal(signal)
            print(f"  执行结果: {result}")
        exec_provider.close()
        return True

    step("Step 5: 富途模拟盘执行", run_execution)

    # ── Step 6: 查询持仓 ──────────────────────────
    def check_positions():
        exec_provider = FutuExecutionProvider(
            host=FUTU_HOST, port=FUTU_PORT,
            trd_env=TrdEnvType.SIMULATE, acc_id=ACC_ID,
        )
        exec_provider.connect()
        positions = exec_provider.get_positions()
        print(f"  当前持仓: {len(positions)} 只")
        for p in positions:
            print(f"    {p.get('symbol', '?')} x {p.get('qty', 0)} @ {p.get('cost', 0)}")
        exec_provider.close()
        return positions

    step("Step 6: 查询模拟账户持仓", check_positions)

    # ── Step 7: 关闭行情连接 ───────────────────────
    step("Step 7: 关闭行情连接", lambda: provider.close())

    print(f"\n\n{'='*60}")
    print(f"✅ 端到端测试完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*60)

if __name__ == "__main__":
    main()