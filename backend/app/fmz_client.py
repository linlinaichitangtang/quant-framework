import hashlib
import hmac
import time
import json
import requests
from typing import Optional, Dict
from urllib.parse import urlencode

from .config import settings
from app.schemas import FMZExecuteRequest, FMZExecuteResponse
from app.models import TradingSignal

import logging
logger = logging.getLogger(__name__)


class FMZClient:
    """FMZ发明者量化API客户端"""
    
    BASE_URL = "https://api.fmz.com/api/v1"
    
    def __init__(self, api_key: str = None, secret_key: str = None, cid: int = None):
        self.api_key = api_key or settings.fmz_api_key
        self.secret_key = secret_key or settings.fmz_secret_key
        self.cid = cid or settings.fmz_cid
    
    def _generate_signature(self, params: Dict) -> str:
        """生成签名"""
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query_string = urlencode(sorted_params)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """发送请求到FMZ API"""
        if params is None:
            params = {}
        
        params['access_key'] = self.api_key
        params['cid'] = self.cid
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._generate_signature(params)
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        if method == 'GET':
            response = requests.get(url, params=params)
        else:
            response = requests.post(url, json=params)
        
        if response.status_code != 200:
            logger.error(f"FMZ API请求失败: {response.status_code} {response.text}")
            return {
                "code": response.status_code,
                "msg": response.text,
                "data": None
            }
        
        return response.json()
    
    def get_account_info(self) -> Dict:
        """获取账户信息"""
        return self._request('GET', 'get-account-info')
    
    def place_order(
        self, 
        exchange: str, 
        symbol: str, 
        side: str, 
        price: float, 
        amount: float,
        market: str = None
    ) -> Dict:
        """
        下单
        
        参数:
            exchange: 交易所代码，比如 "cn" 是A股，"hk"是港股，"binance"是币安
            symbol: 交易对/股票代码
            side: 方向 1=买, 2=卖
            price: 价格
            amount: 数量
        """
        params = {
            "exchange": exchange,
            "symbol": self._format_symbol(symbol, market),
            "side": side,
            "price": price,
            "amount": amount
        }
        return self._request('POST', 'place-order', params)
    
    def cancel_order(self, exchange: str, order_id: str) -> Dict:
        """撤单"""
        params = {
            "exchange": exchange,
            "order_id": order_id
        }
        return self._request('POST', 'cancel-order', params)
    
    def get_position(self, exchange: str) -> Dict:
        """获取持仓"""
        params = {
            "exchange": exchange
        }
        return self._request('GET', 'get-positions', params)
    
    def _format_symbol(self, symbol: str, market: str) -> str:
        """根据市场格式化交易代码"""
        if market == "A":
            # A股格式: 000001 -> 000001.CN
            return f"{symbol}.CN"
        elif market == "HK":
            # 港股格式: 00001 -> 00001.HK
            return f"{symbol}.HK"
        return symbol
    
    def execute_signal(self, signal: TradingSignal) -> FMZExecuteResponse:
        """执行交易信号"""
        if not self.api_key or not self.secret_key or not self.cid:
            return FMZExecuteResponse(
                success=False,
                message="FMZ API未配置，请检查配置文件"
            )
        
        # 确定交易所
        if signal.market == "A":
            exchange = "cn"
        elif signal.market == "HK":
            exchange = "hk"
        else:  # US
            exchange = "us"
        
        side = 1 if signal.side.upper() == "BUY" else 2
        price = signal.target_price if signal.target_price else signal.stop_loss
        if not price:
            # 如果没有指定价格，使用最新价
            from app.database import SessionLocal
            from app.crud import get_historical_bars
            db = SessionLocal()
            bars = get_historical_bars(db, signal.symbol, limit=1)
            if bars:
                price = bars[0].close
            db.close()
        
        if not price:
            return FMZExecuteResponse(
                success=False,
                message="无法获取价格，请检查数据"
            )
        
        quantity = signal.quantity if signal.quantity else 100
        
        logger.info(f"执行交易信号: {signal.market} {signal.side} {signal.symbol} {quantity}@{price}")
        
        result = self.place_order(
            exchange=exchange,
            symbol=signal.symbol,
            side=side,
            price=price,
            amount=quantity,
            market=signal.market
        )
        
        if result.get("code") == 200 and result.get("data"):
            order_id = result["data"].get("order_id")
            return FMZExecuteResponse(
                success=True,
                message="下单成功",
                order_id=order_id,
                data=result["data"]
            )
        else:
            return FMZExecuteResponse(
                success=False,
                message=f"下单失败: {result.get('msg')}",
                data=result
            )
