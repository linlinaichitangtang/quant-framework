"""
V1.7 多市场扩展服务层 — 期货、加密货币、ETF、跨市场套利、全球时区
"""
import math
import random
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

try:
    import pytz
except ImportError:
    pytz = None


class MultiMarketService:
    """多市场服务 — 期货/加密货币/ETF/跨市场套利/全球时区"""

    # ==================== 期货相关 ====================

    # 模拟期货合约数据（中金所/上期所/大商所/郑商所）
    _FUTURES_DATA = {
        "CFFE": {  # 中金所
            "IF": {"name": "沪深300指数期货", "multiplier": 300, "margin_rate": 0.12, "tick_size": 0.2},
            "IC": {"name": "中证500指数期货", "multiplier": 200, "margin_rate": 0.14, "tick_size": 0.2},
            "IH": {"name": "上证50指数期货", "multiplier": 300, "margin_rate": 0.12, "tick_size": 0.2},
            "IM": {"name": "中证1000指数期货", "multiplier": 200, "margin_rate": 0.15, "tick_size": 0.2},
            "T": {"name": "10年期国债期货", "multiplier": 10000, "margin_rate": 0.03, "tick_size": 0.005},
            "TF": {"name": "5年期国债期货", "multiplier": 10000, "margin_rate": 0.02, "tick_size": 0.005},
            "TS": {"name": "2年期国债期货", "multiplier": 20000, "margin_rate": 0.02, "tick_size": 0.005},
        },
        "SHFE": {  # 上期所
            "AU": {"name": "黄金期货", "multiplier": 1000, "margin_rate": 0.08, "tick_size": 0.02},
            "AG": {"name": "白银期货", "multiplier": 15, "margin_rate": 0.09, "tick_size": 1},
            "CU": {"name": "沪铜期货", "multiplier": 5, "margin_rate": 0.10, "tick_size": 10},
            "AL": {"name": "沪铝期货", "multiplier": 5, "margin_rate": 0.08, "tick_size": 5},
            "ZN": {"name": "沪锌期货", "multiplier": 5, "margin_rate": 0.09, "tick_size": 5},
            "RB": {"name": "螺纹钢期货", "multiplier": 10, "margin_rate": 0.08, "tick_size": 1},
            "HC": {"name": "热轧卷板期货", "multiplier": 10, "margin_rate": 0.08, "tick_size": 1},
            "NI": {"name": "沪镍期货", "multiplier": 1, "margin_rate": 0.11, "tick_size": 10},
            "SN": {"name": "沪锡期货", "multiplier": 1, "margin_rate": 0.10, "tick_size": 10},
            "RU": {"name": "天然橡胶期货", "multiplier": 10, "margin_rate": 0.09, "tick_size": 5},
            "FU": {"name": "燃料油期货", "multiplier": 10, "margin_rate": 0.10, "tick_size": 1},
            "SC": {"name": "原油期货", "multiplier": 1000, "margin_rate": 0.10, "tick_size": 0.1},
        },
        "DCE": {  # 大商所
            "I": {"name": "铁矿石期货", "multiplier": 100, "margin_rate": 0.10, "tick_size": 0.5},
            "J": {"name": "焦炭期货", "multiplier": 100, "margin_rate": 0.09, "tick_size": 0.5},
            "JM": {"name": "焦煤期货", "multiplier": 60, "margin_rate": 0.09, "tick_size": 0.5},
            "C": {"name": "玉米期货", "multiplier": 10, "margin_rate": 0.07, "tick_size": 1},
            "M": {"name": "豆粕期货", "multiplier": 10, "margin_rate": 0.07, "tick_size": 1},
            "A": {"name": "豆一期货", "multiplier": 10, "margin_rate": 0.07, "tick_size": 1},
            "Y": {"name": "豆油期货", "multiplier": 10, "margin_rate": 0.07, "tick_size": 2},
            "P": {"name": "棕榈油期货", "multiplier": 10, "margin_rate": 0.08, "tick_size": 2},
            "PP": {"name": "聚丙烯期货", "multiplier": 5, "margin_rate": 0.07, "tick_size": 1},
            "L": {"name": "塑料期货", "multiplier": 5, "margin_rate": 0.07, "tick_size": 5},
            "V": {"name": "PVC期货", "multiplier": 5, "margin_rate": 0.07, "tick_size": 5},
            "EG": {"name": "乙二醇期货", "multiplier": 10, "margin_rate": 0.08, "tick_size": 1},
            "EB": {"name": "苯乙烯期货", "multiplier": 5, "margin_rate": 0.08, "tick_size": 1},
        },
        "CZCE": {  # 郑商所
            "CF": {"name": "棉花期货", "multiplier": 5, "margin_rate": 0.07, "tick_size": 5},
            "SR": {"name": "白糖期货", "multiplier": 10, "margin_rate": 0.07, "tick_size": 1},
            "OI": {"name": "菜籽油期货", "multiplier": 10, "margin_rate": 0.07, "tick_size": 2},
            "RM": {"name": "菜籽粕期货", "multiplier": 10, "margin_rate": 0.07, "tick_size": 1},
            "TA": {"name": "PTA期货", "multiplier": 5, "margin_rate": 0.07, "tick_size": 2},
            "MA": {"name": "甲醇期货", "multiplier": 10, "margin_rate": 0.08, "tick_size": 1},
            "FG": {"name": "玻璃期货", "multiplier": 20, "margin_rate": 0.07, "tick_size": 1},
            "SA": {"name": "纯碱期货", "multiplier": 20, "margin_rate": 0.08, "tick_size": 1},
            "SF": {"name": "硅铁期货", "multiplier": 5, "margin_rate": 0.09, "tick_size": 2},
            "ZC": {"name": "动力煤期货", "multiplier": 100, "margin_rate": 0.10, "tick_size": 0.2},
            "AP": {"name": "苹果期货", "multiplier": 10, "margin_rate": 0.09, "tick_size": 1},
            "CJ": {"name": "红枣期货", "multiplier": 5, "margin_rate": 0.09, "tick_size": 5},
        },
    }

    # 期货基础价格模拟（用于生成随机行情）
    _FUTURES_BASE_PRICES = {
        "IF": 3800, "IC": 5200, "IH": 2600, "IM": 6200,
        "T": 102.5, "TF": 102.0, "TS": 101.5,
        "AU": 560, "AG": 7200, "CU": 78000, "AL": 20500,
        "ZN": 23000, "RB": 3650, "HC": 3750, "NI": 175000,
        "SN": 250000, "RU": 13500, "FU": 3200, "SC": 580,
        "I": 850, "J": 2200, "JM": 1500, "C": 2650,
        "M": 3200, "A": 5200, "Y": 8200, "P": 7800,
        "PP": 7300, "L": 8100, "V": 6200, "EG": 4200, "EB": 8500,
        "CF": 16000, "SR": 6800, "OI": 8500, "RM": 2500,
        "TA": 5800, "MA": 2550, "FG": 1700, "SA": 1900,
        "SF": 7200, "ZC": 800, "AP": 8500, "CJ": 12000,
    }

    @classmethod
    def get_futures_contracts(cls, db, exchange: Optional[str] = None, underlying: Optional[str] = None) -> list:
        """获取期货合约列表"""
        contracts = []
        now = datetime.now()
        # 生成当季、下季、远季合约月份
        months = []
        for i in range(4):
            m = now.month + i * 3
            y = now.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            months.append(f"{y}{m:02d}")

        exchanges = [exchange] if exchange else list(cls._FUTURES_DATA.keys())
        for ex in exchanges:
            if ex not in cls._FUTURES_DATA:
                continue
            for code, info in cls._FUTURES_DATA[ex].items():
                if underlying and code != underlying:
                    continue
                base_price = cls._FUTURES_BASE_PRICES.get(code, 5000)
                for month in months:
                    # 生成随机行情
                    change_pct = round(random.uniform(-3.0, 3.0), 2)
                    last_price = round(base_price * (1 + change_pct / 100 + random.uniform(-0.01, 0.01)), 2)
                    contracts.append({
                        "symbol": f"{code}{month}",
                        "name": f"{info['name']}{month}",
                        "exchange": ex,
                        "underlying": code,
                        "contract_month": month,
                        "multiplier": info["multiplier"],
                        "margin_rate": info["margin_rate"],
                        "tick_size": info["tick_size"],
                        "last_price": last_price,
                        "change_pct": change_pct,
                        "volume": round(random.uniform(10000, 500000)),
                        "open_interest": round(random.uniform(50000, 800000)),
                    })
        return contracts

    @classmethod
    def get_futures_quote(cls, symbol: str, exchange: Optional[str] = None) -> dict:
        """获取期货行情"""
        # 解析合约代码（如 IF202606 -> IF, 202606）
        code = ""
        for ex_data in cls._FUTURES_DATA.values():
            for c in ex_data:
                if symbol.startswith(c):
                    code = c
                    break
            if code:
                break

        if not code:
            return {"symbol": symbol, "error": "合约代码不存在"}

        info = None
        ex = None
        for e, ex_data in cls._FUTURES_DATA.items():
            if code in ex_data:
                info = ex_data[code]
                ex = e
                break

        if not info:
            return {"symbol": symbol, "error": "合约信息不存在"}

        base_price = cls._FUTURES_BASE_PRICES.get(code, 5000)
        change_pct = round(random.uniform(-3.0, 3.0), 2)
        last_price = round(base_price * (1 + random.uniform(-0.02, 0.02)), 2)
        open_price = round(last_price * (1 + random.uniform(-0.01, 0.01)), 2)
        high_price = round(max(last_price, open_price) * (1 + random.uniform(0, 0.015)), 2)
        low_price = round(min(last_price, open_price) * (1 - random.uniform(0, 0.015)), 2)
        settlement_price = round(last_price * (1 + random.uniform(-0.005, 0.005)), 2)

        return {
            "symbol": symbol,
            "name": info["name"],
            "exchange": ex,
            "last_price": last_price,
            "change_pct": change_pct,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "settlement_price": settlement_price,
            "volume": round(random.uniform(50000, 500000)),
            "open_interest": round(random.uniform(100000, 1000000)),
            "multiplier": info["multiplier"],
            "margin_rate": info["margin_rate"],
            "tick_size": info["tick_size"],
            "bid_price": round(last_price - info["tick_size"], 2),
            "ask_price": round(last_price + info["tick_size"], 2),
            "pre_settlement": round(base_price, 2),
        }

    @classmethod
    def calculate_futures_margin(cls, symbol: str, quantity: float, price: float, leverage: float = 1.0) -> dict:
        """计算期货保证金"""
        # 解析合约代码获取保证金率
        code = ""
        for ex_data in cls._FUTURES_DATA.values():
            for c in ex_data:
                if symbol.startswith(c):
                    code = c
                    break
            if code:
                break

        margin_rate = 0.10  # 默认保证金率
        multiplier = 1
        if code:
            for ex_data in cls._FUTURES_DATA.values():
                if code in ex_data:
                    margin_rate = ex_data[code]["margin_rate"]
                    multiplier = ex_data[code]["multiplier"]
                    break

        # 名义价值 = 价格 * 合约乘数 * 手数
        notional_value = price * multiplier * quantity
        # 保证金 = 名义价值 * 保证金率 / 杠杆
        margin_required = notional_value * margin_rate / max(leverage, 1.0)

        return {
            "symbol": symbol,
            "notional_value": round(notional_value, 2),
            "margin_required": round(margin_required, 2),
            "leverage": leverage,
            "margin_rate": margin_rate,
            "multiplier": multiplier,
            "quantity": quantity,
            "price": price,
        }

    # ==================== 加密货币相关 ====================

    # 模拟加密货币数据
    _CRYPTO_DATA = {
        "BTC/USDT": {"name": "比特币", "base_currency": "BTC", "quote_currency": "USDT",
                      "price": 67500, "market_cap": 1320000000000, "circulating_supply": 19600000},
        "ETH/USDT": {"name": "以太坊", "base_currency": "ETH", "quote_currency": "USDT",
                      "price": 3450, "market_cap": 415000000000, "circulating_supply": 120000000},
        "BNB/USDT": {"name": "币安币", "base_currency": "BNB", "quote_currency": "USDT",
                      "price": 580, "market_cap": 88000000000, "circulating_supply": 153000000},
        "SOL/USDT": {"name": "Solana", "base_currency": "SOL", "quote_currency": "USDT",
                      "price": 178, "market_cap": 78000000000, "circulating_supply": 438000000},
        "XRP/USDT": {"name": "瑞波币", "base_currency": "XRP", "quote_currency": "USDT",
                      "price": 0.62, "market_cap": 34000000000, "circulating_supply": 54800000000},
        "ADA/USDT": {"name": "艾达币", "base_currency": "ADA", "quote_currency": "USDT",
                      "price": 0.48, "market_cap": 17000000000, "circulating_supply": 35400000000},
        "DOGE/USDT": {"name": "狗狗币", "base_currency": "DOGE", "quote_currency": "USDT",
                      "price": 0.165, "market_cap": 23500000000, "circulating_supply": 143000000000},
        "DOT/USDT": {"name": "波卡", "base_currency": "DOT", "quote_currency": "USDT",
                      "price": 7.85, "market_cap": 10500000000, "circulating_supply": 1340000000},
        "AVAX/USDT": {"name": "雪崩协议", "base_currency": "AVAX", "quote_currency": "USDT",
                      "price": 38.5, "market_cap": 14500000000, "circulating_supply": 377000000},
        "LINK/USDT": {"name": "Chainlink", "base_currency": "LINK", "quote_currency": "USDT",
                      "price": 18.2, "market_cap": 10800000000, "circulating_supply": 594000000},
        "MATIC/USDT": {"name": "Polygon", "base_currency": "MATIC", "quote_currency": "USDT",
                      "price": 0.72, "market_cap": 7100000000, "circulating_supply": 9900000000},
        "UNI/USDT": {"name": "Uniswap", "base_currency": "UNI", "quote_currency": "USDT",
                      "price": 11.5, "market_cap": 6900000000, "circulating_supply": 600000000},
        "LTC/USDT": {"name": "莱特币", "base_currency": "LTC", "quote_currency": "USDT",
                      "price": 85.5, "market_cap": 6400000000, "circulating_supply": 74800000},
        "EOS/USDT": {"name": "EOS", "base_currency": "EOS", "quote_currency": "USDT",
                      "price": 0.92, "market_cap": 1050000000, "circulating_supply": 1140000000},
        "ATOM/USDT": {"name": "Cosmos", "base_currency": "ATOM", "quote_currency": "USDT",
                      "price": 9.8, "market_cap": 3700000000, "circulating_supply": 378000000},
    }

    @classmethod
    def get_crypto_markets(cls) -> list:
        """获取加密货币市场列表"""
        markets = []
        for symbol, data in cls._CRYPTO_DATA.items():
            change_24h = round(random.uniform(-8.0, 8.0), 2)
            price = round(data["price"] * (1 + random.uniform(-0.03, 0.03)), data["price"] < 1 and 4 or 2)
            markets.append({
                "symbol": symbol,
                "name": data["name"],
                "base_currency": data["base_currency"],
                "quote_currency": data["quote_currency"],
                "last_price": price,
                "change_24h": change_24h,
                "high_24h": round(price * (1 + abs(random.uniform(0.01, 0.05))), data["price"] < 1 and 4 or 2),
                "low_24h": round(price * (1 - abs(random.uniform(0.01, 0.05))), data["price"] < 1 and 4 or 2),
                "volume_24h": round(random.uniform(100000000, 50000000000), 2),
                "market_cap": data["market_cap"],
                "circulating_supply": data["circulating_supply"],
            })
        # 按市值降序排列
        markets.sort(key=lambda x: x["market_cap"], reverse=True)
        return markets

    @classmethod
    def get_crypto_quote(cls, symbol: str) -> dict:
        """获取加密货币行情"""
        data = cls._CRYPTO_DATA.get(symbol)
        if not data:
            return {"symbol": symbol, "error": "交易对不存在"}

        change_24h = round(random.uniform(-8.0, 8.0), 2)
        price = round(data["price"] * (1 + random.uniform(-0.03, 0.03)), data["price"] < 1 and 4 or 2)
        decimals = 4 if data["price"] < 1 else 2

        return {
            "symbol": symbol,
            "name": data["name"],
            "base_currency": data["base_currency"],
            "quote_currency": data["quote_currency"],
            "last_price": price,
            "change_24h": change_24h,
            "high_24h": round(price * (1 + abs(random.uniform(0.01, 0.05))), decimals),
            "low_24h": round(price * (1 - abs(random.uniform(0.01, 0.05))), decimals),
            "volume_24h": round(random.uniform(100000000, 50000000000), 2),
            "market_cap": data["market_cap"],
            "circulating_supply": data["circulating_supply"],
            "bid": round(price * 0.9999, decimals),
            "ask": round(price * 1.0001, decimals),
        }

    @classmethod
    def get_crypto_klines(cls, symbol: str, interval: str = "1h", limit: int = 100) -> list:
        """获取加密货币K线数据"""
        data = cls._CRYPTO_DATA.get(symbol)
        if not data:
            return []

        klines = []
        base_price = data["price"]
        now = datetime.now()

        # 根据时间间隔确定时间增量
        interval_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        delta_seconds = interval_map.get(interval, 3600)

        # 生成模拟K线
        price = base_price
        for i in range(limit):
            ts = now - timedelta(seconds=delta_seconds * (limit - i))
            change = random.uniform(-0.02, 0.02)
            open_p = price
            close_p = price * (1 + change)
            high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.01))
            low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.01))
            volume = random.uniform(100, 10000)

            decimals = 4 if base_price < 1 else 2
            klines.append({
                "timestamp": int(ts.timestamp() * 1000),
                "datetime": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "open": round(open_p, decimals),
                "high": round(high_p, decimals),
                "low": round(low_p, decimals),
                "close": round(close_p, decimals),
                "volume": round(volume, 2),
            })
            price = close_p

        return klines

    # ==================== ETF 相关 ====================

    # 模拟 ETF 数据
    _ETF_DATA = {
        "A": [
            {"symbol": "510300", "name": "沪深300ETF", "nav": 4.12, "price": 4.15, "total_assets": 2100,
             "expense_ratio": 0.50, "tracking_index": "沪深300指数",
             "top_holdings": [{"name": "贵州茅台", "weight": 5.2}, {"name": "宁德时代", "weight": 3.8},
                              {"name": "中国平安", "weight": 3.1}, {"name": "招商银行", "weight": 2.8},
                              {"name": "隆基绿能", "weight": 2.1}],
             "sector_allocation": {"金融": 22.5, "消费": 18.3, "医药": 12.1, "科技": 15.6, "新能源": 10.2, "其他": 21.3}},
            {"symbol": "510500", "name": "中证500ETF", "nav": 6.85, "price": 6.88, "total_assets": 850,
             "expense_ratio": 0.60, "tracking_index": "中证500指数",
             "top_holdings": [{"name": "药明康德", "weight": 1.2}, {"name": "智飞生物", "weight": 0.9},
                              {"name": "东方财富", "weight": 0.8}, {"name": "天齐锂业", "weight": 0.7},
                              {"name": "韦尔股份", "weight": 0.6}],
             "sector_allocation": {"工业": 20.1, "材料": 18.5, "医药": 14.2, "科技": 13.8, "消费": 12.3, "其他": 21.1}},
            {"symbol": "159915", "name": "创业板ETF", "nav": 2.35, "price": 2.38, "total_assets": 420,
             "expense_ratio": 0.60, "tracking_index": "创业板指数",
             "top_holdings": [{"name": "宁德时代", "weight": 8.5}, {"name": "东方财富", "weight": 6.2},
                              {"name": "迈瑞医疗", "weight": 4.1}, {"name": "汇川技术", "weight": 3.5},
                              {"name": "阳光电源", "weight": 2.8}],
             "sector_allocation": {"新能源": 28.5, "医药": 15.2, "科技": 18.3, "工业": 10.5, "消费": 8.2, "其他": 19.3}},
            {"symbol": "510050", "name": "上证50ETF", "nav": 2.82, "price": 2.84, "total_assets": 680,
             "expense_ratio": 0.50, "tracking_index": "上证50指数",
             "top_holdings": [{"name": "贵州茅台", "weight": 12.5}, {"name": "中国平安", "weight": 8.2},
                              {"name": "招商银行", "weight": 6.8}, {"name": "恒瑞医药", "weight": 4.5},
                              {"name": "长江电力", "weight": 3.8}],
             "sector_allocation": {"金融": 35.2, "消费": 22.1, "医药": 8.5, "能源": 6.3, "科技": 5.2, "其他": 22.7}},
            {"symbol": "510880", "name": "红利ETF", "nav": 3.15, "price": 3.18, "total_assets": 520,
             "expense_ratio": 0.50, "tracking_index": "上证红利指数",
             "top_holdings": [{"name": "中国神华", "weight": 5.8}, {"name": "唐山港", "weight": 4.2},
                              {"name": "中国石化", "weight": 3.9}, {"name": "宝钢股份", "weight": 3.5},
                              {"name": "建设银行", "weight": 3.2}],
             "sector_allocation": {"能源": 22.1, "金融": 20.5, "材料": 15.8, "工业": 12.3, "公用事业": 10.5, "其他": 18.8}},
            {"symbol": "512100", "name": "中证1000ETF", "nav": 1.95, "price": 1.97, "total_assets": 380,
             "expense_ratio": 0.50, "tracking_index": "中证1000指数",
             "top_holdings": [{"name": "思瑞浦", "weight": 0.5}, {"name": "华海诚科", "weight": 0.4},
                              {"name": "诺思格", "weight": 0.3}, {"name": "科前生物", "weight": 0.3},
                              {"name": "安路科技", "weight": 0.3}],
             "sector_allocation": {"工业": 18.5, "科技": 16.2, "材料": 14.8, "医药": 12.1, "消费": 10.5, "其他": 27.9}},
        ],
        "HK": [
            {"symbol": "2822.HK", "name": "盈富基金", "nav": 18.5, "price": 18.6, "total_assets": 1200,
             "expense_ratio": 0.08, "tracking_index": "恒生指数",
             "top_holdings": [{"name": "腾讯控股", "weight": 10.5}, {"name": "汇丰控股", "weight": 8.2},
                              {"name": "阿里巴巴", "weight": 7.8}, {"name": "友邦保险", "weight": 6.5},
                              {"name": "美团", "weight": 4.2}],
             "sector_allocation": {"金融": 32.5, "科技": 28.3, "消费": 12.1, "地产": 8.5, "能源": 5.2, "其他": 13.4}},
            {"symbol": "3188.HK", "name": "恒生科技ETF", "nav": 5.2, "price": 5.25, "total_assets": 680,
             "expense_ratio": 0.22, "tracking_index": "恒生科技指数",
             "top_holdings": [{"name": "腾讯控股", "weight": 12.8}, {"name": "阿里巴巴", "weight": 10.2},
                              {"name": "美团", "weight": 8.5}, {"name": "小米集团", "weight": 7.2},
                              {"name": "京东集团", "weight": 6.8}],
             "sector_allocation": {"科技": 45.2, "消费": 22.5, "金融": 10.3, "医药": 5.8, "工业": 3.2, "其他": 13.0}},
            {"symbol": "7500.HK", "name": "南方恒生科技", "nav": 1.85, "price": 1.87, "total_assets": 320,
             "expense_ratio": 0.22, "tracking_index": "恒生科技指数",
             "top_holdings": [{"name": "腾讯控股", "weight": 12.5}, {"name": "阿里巴巴", "weight": 10.0},
                              {"name": "美团", "weight": 8.3}, {"name": "小米集团", "weight": 7.0},
                              {"name": "京东集团", "weight": 6.5}],
             "sector_allocation": {"科技": 44.8, "消费": 23.1, "金融": 10.5, "医药": 5.5, "工业": 3.5, "其他": 12.6}},
        ],
        "US": [
            {"symbol": "SPY", "name": "SPDR标普500ETF", "nav": 520.5, "price": 522.3, "total_assets": 5200,
             "expense_ratio": 0.09, "tracking_index": "S&P 500",
             "top_holdings": [{"name": "Apple", "weight": 7.1}, {"name": "Microsoft", "weight": 6.8},
                              {"name": "NVIDIA", "weight": 5.2}, {"name": "Amazon", "weight": 3.8},
                              {"name": "Meta", "weight": 2.5}],
             "sector_allocation": {"科技": 31.2, "医疗": 12.5, "金融": 13.1, "消费": 10.8, "工业": 8.5, "其他": 23.9}},
            {"symbol": "QQQ", "name": "Invesco QQQ", "nav": 450.2, "price": 453.8, "total_assets": 2800,
             "expense_ratio": 0.20, "tracking_index": "纳斯达克100",
             "top_holdings": [{"name": "Apple", "weight": 11.2}, {"name": "Microsoft", "weight": 10.5},
                              {"name": "NVIDIA", "weight": 8.2}, {"name": "Amazon", "weight": 5.8},
                              {"name": "Meta", "weight": 4.2}],
             "sector_allocation": {"科技": 52.3, "消费": 16.5, "医疗": 6.8, "工业": 5.2, "通信": 3.8, "其他": 15.4}},
            {"symbol": "IWM", "name": "iShares罗素2000", "nav": 215.8, "price": 217.2, "total_assets": 650,
             "expense_ratio": 0.19, "tracking_index": "罗素2000指数",
             "top_holdings": [{"name": "Super Micro Computer", "weight": 0.6}, {"name": "Tenet Healthcare", "weight": 0.5},
                              {"name": "e.l.f. Beauty", "weight": 0.4}, {"name": "First Solar", "weight": 0.4},
                              {"name": "Insulet", "weight": 0.4}],
             "sector_allocation": {"科技": 15.2, "医疗": 14.8, "金融": 16.5, "工业": 14.2, "消费": 12.1, "其他": 27.2}},
            {"symbol": "VTI", "name": "Vanguard全市场ETF", "nav": 268.5, "price": 270.1, "total_assets": 4200,
             "expense_ratio": 0.03, "tracking_index": "CRSP US Total Market",
             "top_holdings": [{"name": "Apple", "weight": 5.8}, {"name": "Microsoft", "weight": 5.5},
                              {"name": "NVIDIA", "weight": 4.2}, {"name": "Amazon", "weight": 3.1},
                              {"name": "Meta", "weight": 2.1}],
             "sector_allocation": {"科技": 28.5, "医疗": 11.8, "金融": 12.5, "消费": 10.2, "工业": 8.8, "其他": 28.2}},
            {"symbol": "ARKK", "name": "ARK Innovation", "nav": 52.8, "price": 53.5, "total_assets": 85,
             "expense_ratio": 0.75, "tracking_index": "主动管理",
             "top_holdings": [{"name": "Tesla", "weight": 12.5}, {"name": "Roku", "weight": 8.2},
                              {"name": "Block", "weight": 7.5}, {"name": "CRISPR Therapeutics", "weight": 6.8},
                              {"name": "Zoom", "weight": 5.5}],
             "sector_allocation": {"科技": 42.5, "医疗": 18.2, "消费": 15.8, "金融": 5.2, "工业": 3.5, "其他": 14.8}},
        ],
    }

    @classmethod
    def get_etf_list(cls, market: Optional[str] = None) -> list:
        """获取 ETF 基金列表"""
        etfs = []
        markets = [market] if market else list(cls._ETF_DATA.keys())
        for m in markets:
            if m not in cls._ETF_DATA:
                continue
            for etf in cls._ETF_DATA[m]:
                price = round(etf["price"] * (1 + random.uniform(-0.01, 0.01)), 3)
                nav = etf["nav"]
                premium_rate = round((price - nav) / nav * 100, 2)
                etfs.append({
                    "symbol": etf["symbol"],
                    "name": etf["name"],
                    "market": m,
                    "nav": nav,
                    "price": price,
                    "premium_rate": premium_rate,
                    "total_assets": etf["total_assets"],
                    "expense_ratio": etf["expense_ratio"],
                    "tracking_index": etf["tracking_index"],
                })
        return etfs

    @classmethod
    def get_etf_detail(cls, symbol: str, market: Optional[str] = None) -> dict:
        """获取 ETF 详情（含净值/溢价率/持仓）"""
        for m, etf_list in cls._ETF_DATA.items():
            if market and m != market:
                continue
            for etf in etf_list:
                if etf["symbol"] == symbol:
                    price = round(etf["price"] * (1 + random.uniform(-0.01, 0.01)), 3)
                    nav = etf["nav"]
                    premium_rate = round((price - nav) / nav * 100, 2)
                    return {
                        "symbol": etf["symbol"],
                        "name": etf["name"],
                        "market": m,
                        "nav": nav,
                        "price": price,
                        "premium_rate": premium_rate,
                        "total_assets": etf["total_assets"],
                        "expense_ratio": etf["expense_ratio"],
                        "tracking_index": etf["tracking_index"],
                        "top_holdings": etf["top_holdings"],
                        "sector_allocation": etf["sector_allocation"],
                    }
        return {"symbol": symbol, "error": "ETF不存在"}

    # ==================== 全球市场时区 ====================

    # 各市场交易时间配置
    _MARKET_HOURS = {
        "A": {  # A股
            "timezone": "Asia/Shanghai",
            "open_time": "09:30",
            "close_time": "15:00",
            "morning_open": "09:30",
            "morning_close": "11:30",
            "afternoon_open": "13:00",
            "afternoon_close": "15:00",
            "pre_market_start": "09:15",
            "pre_market_end": "09:25",
        },
        "HK": {  # 港股
            "timezone": "Asia/Hong_Kong",
            "open_time": "09:30",
            "close_time": "16:00",
            "morning_open": "09:30",
            "morning_close": "12:00",
            "afternoon_open": "13:00",
            "afternoon_close": "16:00",
            "pre_market_start": "09:00",
            "pre_market_end": "09:30",
        },
        "US": {  # 美股
            "timezone": "America/New_York",
            "open_time": "09:30",
            "close_time": "16:00",
            "pre_market_start": "04:00",
            "pre_market_end": "09:30",
            "after_hours_start": "16:00",
            "after_hours_end": "20:00",
        },
        "UK": {  # 伦敦
            "timezone": "Europe/London",
            "open_time": "08:00",
            "close_time": "16:30",
        },
        "JP": {  # 日本
            "timezone": "Asia/Tokyo",
            "open_time": "09:00",
            "close_time": "15:00",
            "morning_open": "09:00",
            "morning_close": "11:30",
            "afternoon_open": "12:30",
            "afternoon_close": "15:00",
        },
        "DE": {  # 德国
            "timezone": "Europe/Berlin",
            "open_time": "09:00",
            "close_time": "17:30",
        },
        "CRYPTO": {  # 加密货币（24/7）
            "timezone": "UTC",
            "open_time": "00:00",
            "close_time": "23:59",
            "is_24h": True,
        },
    }

    @classmethod
    def _get_market_status(cls, market: str) -> str:
        """判断市场当前状态"""
        if market not in cls._MARKET_HOURS:
            return "unknown"

        config = cls._MARKET_HOURS[market]
        if config.get("is_24h"):
            return "open"

        tz_name = config["timezone"]
        if pytz:
            try:
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)
            except Exception:
                now = datetime.now()
        else:
            now = datetime.now()

        current_time = now.strftime("%H:%M")
        weekday = now.weekday()  # 0=周一, 6=周日

        # 周末休市
        if weekday >= 5:
            return "closed"

        open_time = config["open_time"]
        close_time = config["close_time"]

        # 盘前
        if "pre_market_start" in config and "pre_market_end" in config:
            if config["pre_market_start"] <= current_time < config["pre_market_end"]:
                return "pre_market"

        # 盘后
        if "after_hours_start" in config and "after_hours_end" in config:
            if config["after_hours_start"] <= current_time < config["after_hours_end"]:
                return "after_hours"

        # 交易时段
        if open_time <= current_time <= close_time:
            return "open"

        return "closed"

    @classmethod
    def get_market_hours(cls, market: str, date: Optional[str] = None) -> dict:
        """获取市场交易时间"""
        if market not in cls._MARKET_HOURS:
            return {"market": market, "error": "市场不存在"}

        config = cls._MARKET_HOURS[market]
        tz_name = config["timezone"]

        if pytz:
            try:
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)
            except Exception:
                now = datetime.now()
        else:
            now = datetime.now()

        status = cls._get_market_status(market)

        # 计算下次开盘时间
        next_open = None
        if status == "closed":
            next_open = now.strftime("%Y-%m-%d") + " " + config["open_time"]
            # 如果今天是周末，下次开盘是周一
            if now.weekday() >= 5:
                days_until_monday = 7 - now.weekday()
                next_dt = now + timedelta(days=days_until_monday)
                next_open = next_dt.strftime("%Y-%m-%d") + " " + config["open_time"]

        return {
            "market": market,
            "timezone": tz_name,
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "open_time": config["open_time"],
            "close_time": config["close_time"],
            "next_open": next_open,
            "is_24h": config.get("is_24h", False),
        }

    @classmethod
    def get_all_market_status(cls) -> list:
        """获取所有市场当前状态"""
        result = []
        for market in cls._MARKET_HOURS:
            hours = cls.get_market_hours(market)
            result.append(hours)
        return result

    # ==================== 跨市场套利 ====================

    # 模拟跨市场标的对
    _CROSS_MARKET_PAIRS = [
        {"symbol_a": "510300", "market_a": "A", "symbol_b": "2822.HK", "market_b": "HK", "name": "沪深300 A/H"},
        {"symbol_a": "510050", "market_a": "A", "symbol_b": "2822.HK", "market_b": "HK", "name": "上证50 A/H"},
        {"symbol_a": "SPY", "market_a": "US", "symbol_b": "2822.HK", "market_b": "HK", "name": "标普500/恒指"},
        {"symbol_a": "QQQ", "market_a": "US", "symbol_b": "3188.HK", "market_b": "HK", "name": "纳指100/恒生科技"},
        {"symbol_a": "IF", "market_a": "A", "symbol_b": "SPY", "market_b": "US", "name": "沪深300期货/标普500"},
        {"symbol_a": "AU", "market_a": "A", "symbol_b": "GLD", "market_b": "US", "name": "黄金期货/黄金ETF"},
        {"symbol_a": "BTC/USDT", "market_a": "CRYPTO", "symbol_b": "COIN", "market_b": "US", "name": "BTC/Coinbase"},
        {"symbol_a": "510300", "market_a": "A", "symbol_b": "SPY", "market_b": "US", "name": "沪深300/标普500"},
        {"symbol_a": "T", "market_a": "A", "symbol_b": "TLT", "market_b": "US", "name": "国债期货/美债ETF"},
        {"symbol_a": "CU", "market_a": "A", "symbol_b": "CPER", "market_b": "US", "name": "沪铜/铜ETF"},
    ]

    @classmethod
    def detect_arbitrage_opportunity(cls, symbol_a: str, market_a: str,
                                      symbol_b: str, market_b: str) -> dict:
        """检测跨市场套利机会"""
        # 模拟价差分析
        spread = round(random.uniform(-5.0, 5.0), 3)
        spread_pct = round(random.uniform(-2.0, 2.0), 3)
        z_score = round(random.gauss(0, 1), 3)
        is_profitable = abs(z_score) > 1.5 and abs(spread_pct) > 0.5
        estimated_pnl = round(random.uniform(-500, 1500), 2) if is_profitable else round(random.uniform(-200, 200), 2)
        confidence = round(min(abs(z_score) / 3.0 * 100, 95), 1) if is_profitable else round(random.uniform(10, 40), 1)

        return {
            "symbol_a": symbol_a,
            "market_a": market_a,
            "symbol_b": symbol_b,
            "market_b": market_b,
            "spread": spread,
            "spread_pct": spread_pct,
            "historical_avg_spread": round(random.uniform(-1.0, 1.0), 3),
            "z_score": z_score,
            "is_profitable": is_profitable,
            "estimated_pnl": estimated_pnl,
            "confidence": confidence,
        }

    @classmethod
    def calculate_arbitrage_pnl(cls, data: dict) -> dict:
        """计算套利盈亏"""
        quantity_a = data.get("quantity_a", 1)
        quantity_b = data.get("quantity_b", 1)
        price_a = data.get("price_a", 0)
        price_b = data.get("price_b", 0)
        commission_rate = data.get("commission_rate", 0.001)

        # 计算双边成本
        cost_a = price_a * quantity_a
        cost_b = price_b * quantity_b
        total_commission = (cost_a + cost_b) * commission_rate

        # 模拟套利盈亏
        spread = abs(cost_a - cost_b)
        pnl = spread - total_commission * 2  # 开平仓各一次手续费
        pnl_pct = round(pnl / max(cost_a + cost_b, 1) * 100, 4)

        return {
            "cost_a": round(cost_a, 2),
            "cost_b": round(cost_b, 2),
            "total_commission": round(total_commission, 2),
            "spread": round(spread, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": pnl_pct,
            "is_profitable": pnl > 0,
            "risk_level": "low" if abs(pnl_pct) < 1 else "medium" if abs(pnl_pct) < 3 else "high",
        }

    @classmethod
    def get_cross_market_correlation(cls, symbols: Optional[List[str]] = None,
                                      period: str = "30d") -> dict:
        """获取跨市场相关性矩阵"""
        # 默认标的列表
        default_symbols = ["上证指数", "深证成指", "恒生指数", "纳斯达克", "标普500",
                           "日经225", "富时100", "BTC", "黄金", "原油"]
        if not symbols:
            symbols = default_symbols

        n = len(symbols)
        # 生成模拟相关性矩阵
        matrix = []
        for i in range(n):
            row = []
            for j in range(n):
                if i == j:
                    row.append(1.0)
                else:
                    # 生成合理的随机相关性
                    corr = round(random.uniform(0.1, 0.85), 3)
                    row.append(corr)
            matrix.append(row)

        return {
            "symbols": symbols,
            "period": period,
            "matrix": matrix,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def get_global_market_overview(cls) -> dict:
        """全球市场概览（各市场主要指数）"""
        # 各市场主要指数
        indices = [
            {"symbol": "000001.SH", "name": "上证指数", "market": "A", "price": 3150.5,
             "change_pct": round(random.uniform(-2, 2), 2)},
            {"symbol": "399001.SZ", "name": "深证成指", "market": "A", "price": 10250.8,
             "change_pct": round(random.uniform(-2.5, 2.5), 2)},
            {"symbol": "399006.SZ", "name": "创业板指", "market": "A", "price": 2050.3,
             "change_pct": round(random.uniform(-3, 3), 2)},
            {"symbol": "HSI", "name": "恒生指数", "market": "HK", "price": 18250.5,
             "change_pct": round(random.uniform(-2, 2), 2)},
            {"symbol": "HSCEI", "name": "国企指数", "market": "HK", "price": 6350.2,
             "change_pct": round(random.uniform(-2, 2), 2)},
            {"symbol": "IXIC", "name": "纳斯达克指数", "market": "US", "price": 16850.3,
             "change_pct": round(random.uniform(-2, 2), 2)},
            {"symbol": "SPX", "name": "标普500指数", "market": "US", "price": 5350.8,
             "change_pct": round(random.uniform(-1.5, 1.5), 2)},
            {"symbol": "DJI", "name": "道琼斯指数", "market": "US", "price": 39850.5,
             "change_pct": round(random.uniform(-1.5, 1.5), 2)},
            {"symbol": "N225", "name": "日经225指数", "market": "JP", "price": 40250.8,
             "change_pct": round(random.uniform(-2, 2), 2)},
            {"symbol": "FTSE", "name": "富时100指数", "market": "UK", "price": 8250.5,
             "change_pct": round(random.uniform(-1.5, 1.5), 2)},
            {"symbol": "GDAXI", "name": "德国DAX指数", "market": "DE", "price": 18550.2,
             "change_pct": round(random.uniform(-1.5, 1.5), 2)},
            {"symbol": "BTC", "name": "比特币", "market": "CRYPTO", "price": 67500,
             "change_pct": round(random.uniform(-5, 5), 2)},
        ]

        # 添加随机波动
        for idx in indices:
            idx["price"] = round(idx["price"] * (1 + random.uniform(-0.005, 0.005)), 2)

        # 获取各市场状态
        market_status = cls.get_all_market_status()

        # 获取套利机会
        arbitrage_opportunities = []
        for pair in cls._CROSS_MARKET_PAIRS[:5]:
            opp = cls.detect_arbitrage_opportunity(
                pair["symbol_a"], pair["market_a"],
                pair["symbol_b"], pair["market_b"]
            )
            opp["name"] = pair["name"]
            arbitrage_opportunities.append(opp)

        # 获取相关性矩阵
        correlation = cls.get_cross_market_correlation(period="7d")

        return {
            "indices": indices,
            "market_status": market_status,
            "arbitrage_opportunities": arbitrage_opportunities,
            "correlations": correlation,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
