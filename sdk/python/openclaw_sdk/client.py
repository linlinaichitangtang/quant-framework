"""
OpenClaw 量化交易平台 Python SDK
"""

import hashlib
import hmac
import json
import time
from typing import Optional, Dict, Any, List, Union

import requests
import requests.adapters

from .exceptions import (
    OpenClawError,
    AuthenticationError,
    RateLimitError,
    APIError,
    ConnectionError as SDKConnectionError,
)
from .models import (
    Quote, Kline, StockInfo,
    Signal, Position, Order,
    AccountInfo, AccountBalance,
    BacktestConfig, BacktestResult,
    AIResponse, ChatMessage, MarketSentiment, StrategyAdvice,
    UsageStats,
)

__all__ = ["OpenClawClient"]


class OpenClawClient:
    """OpenClaw 量化交易平台客户端"""

    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    API_VERSION = "v1"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "http://localhost:8000",
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        """
        初始化 OpenClaw 客户端

        Args:
            api_key: API Key
            api_secret: API Secret
            base_url: API 基础地址，默认 http://localhost:8000
            timeout: 请求超时时间（秒），默认 30
            max_retries: 最大重试次数，默认 3
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # 配置 session 和重试策略
        self._session = requests.Session()
        retry_strategy = requests.adapters.Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    # ==================== 认证相关 ====================

    def _generate_signature(self, method: str, path: str, timestamp: int, body: str = "") -> str:
        """
        生成 HMAC-SHA256 签名

        Args:
            method: HTTP 方法（GET/POST/PUT/DELETE）
            path: 请求路径
            timestamp: 时间戳
            body: 请求体字符串

        Returns:
            签名字符串
        """
        message = f"{method.upper()}\n{path}\n{timestamp}\n{body}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _get_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        构建请求头

        Args:
            method: HTTP 方法
            path: 请求路径
            body: 请求体字符串

        Returns:
            请求头字典
        """
        timestamp = int(time.time())
        signature = self._generate_signature(method, path, timestamp, body)
        return {
            "Content-Type": "application/json",
            "X-OC-API-Key": self.api_key,
            "X-OC-Timestamp": str(timestamp),
            "X-OC-Signature": signature,
        }

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        统一请求方法

        Args:
            method: HTTP 方法
            path: API 路径
            params: URL 查询参数
            data: 请求体数据
            **kwargs: 其他请求参数

        Returns:
            响应 JSON 数据

        Raises:
            AuthenticationError: 认证失败
            RateLimitError: 限流
            APIError: API 错误
            SDKConnectionError: 连接错误
        """
        url = f"{self.base_url}{path}"
        body = json.dumps(data, ensure_ascii=False) if data else ""

        headers = self._get_headers(method, path, body)
        headers.update(kwargs.pop("headers", {}))

        try:
            response = self._session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=body if body else None,
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.exceptions.Timeout:
            raise SDKConnectionError(f"请求超时（{self.timeout}秒）")
        except requests.exceptions.ConnectionError:
            raise SDKConnectionError(f"无法连接到 {self.base_url}")
        except requests.exceptions.RequestException as e:
            raise SDKConnectionError(f"请求异常: {e}")

        # 处理响应
        if response.status_code == 401:
            raise AuthenticationError(response.text)
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                response.text,
                retry_after=int(retry_after) if retry_after else None,
            )
        elif response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("detail", error_data.get("message", response.text))
            except (json.JSONDecodeError, ValueError):
                message = response.text
            raise APIError(message, status_code=response.status_code)

        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            return {"raw": response.text}

    # ==================== 市场数据 API ====================

    def get_quotes(self, market: str, symbols: Optional[List[str]] = None) -> List[Quote]:
        """
        获取行情报价

        Args:
            market: 市场标识（cn/us/hk）
            symbols: 股票代码列表，为空则获取全部

        Returns:
            Quote 列表
        """
        params = {"market": market}
        if symbols:
            params["symbols"] = ",".join(symbols)
        data = self._request("GET", f"/api/{self.API_VERSION}/market/quotes", params=params)
        quotes = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(quotes, list):
            return [Quote.from_dict(q) for q in quotes]
        return [Quote.from_dict(quotes)] if isinstance(quotes, dict) else []

    def get_klines(
        self,
        symbol: str,
        market: str,
        period: str = "1d",
        limit: int = 100,
    ) -> List[Kline]:
        """
        获取K线数据

        Args:
            symbol: 股票代码
            market: 市场标识
            period: K线周期（1m/5m/15m/30m/1h/1d/1w/1M）
            limit: 数据条数

        Returns:
            Kline 列表
        """
        params = {"symbol": symbol, "market": market, "period": period, "limit": limit}
        data = self._request("GET", f"/api/{self.API_VERSION}/market/klines", params=params)
        klines = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(klines, list):
            return [Kline.from_dict(k) for k in klines]
        return [Kline.from_dict(klines)] if isinstance(klines, dict) else []

    def get_stock_info(self, symbol: str) -> StockInfo:
        """
        获取股票信息

        Args:
            symbol: 股票代码

        Returns:
            StockInfo 对象
        """
        data = self._request("GET", f"/api/{self.API_VERSION}/market/stocks/{symbol}")
        info = data.get("data", data) if isinstance(data, dict) else data
        return StockInfo.from_dict(info)

    # ==================== 交易 API ====================

    def create_signal(
        self,
        symbol: str,
        market: str,
        side: str,
        strategy_id: Optional[str] = None,
        **kwargs,
    ) -> Signal:
        """
        创建交易信号

        Args:
            symbol: 股票代码
            market: 市场标识
            side: 方向（buy/sell）
            strategy_id: 策略 ID
            **kwargs: 其他参数（price, quantity, confidence, reason 等）

        Returns:
            Signal 对象
        """
        payload = {
            "symbol": symbol,
            "market": market,
            "side": side,
            "strategy_id": strategy_id,
            **kwargs,
        }
        data = self._request("POST", f"/api/{self.API_VERSION}/signals", data=payload)
        signal_data = data.get("data", data) if isinstance(data, dict) else data
        return Signal.from_dict(signal_data)

    def get_signals(
        self,
        market: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Signal]:
        """
        获取信号列表

        Args:
            market: 市场标识
            status: 信号状态
            limit: 返回条数

        Returns:
            Signal 列表
        """
        params = {"limit": limit}
        if market:
            params["market"] = market
        if status:
            params["status"] = status
        data = self._request("GET", f"/api/{self.API_VERSION}/signals", params=params)
        signals = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(signals, list):
            return [Signal.from_dict(s) for s in signals]
        return [Signal.from_dict(signals)] if isinstance(signals, dict) else []

    def get_positions(self, market: Optional[str] = None) -> List[Position]:
        """
        获取持仓列表

        Args:
            market: 市场标识

        Returns:
            Position 列表
        """
        params = {}
        if market:
            params["market"] = market
        data = self._request("GET", f"/api/{self.API_VERSION}/positions", params=params)
        positions = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(positions, list):
            return [Position.from_dict(p) for p in positions]
        return [Position.from_dict(positions)] if isinstance(positions, dict) else []

    def create_order(
        self,
        symbol: str,
        market: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "limit",
    ) -> Order:
        """
        创建订单

        Args:
            symbol: 股票代码
            market: 市场标识
            side: 方向（buy/sell）
            quantity: 数量
            price: 价格（限价单必填）
            order_type: 订单类型（limit/market/stop）

        Returns:
            Order 对象
        """
        payload = {
            "symbol": symbol,
            "market": market,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
        }
        if price is not None:
            payload["price"] = price
        data = self._request("POST", f"/api/{self.API_VERSION}/orders", data=payload)
        order_data = data.get("data", data) if isinstance(data, dict) else data
        return Order.from_dict(order_data)

    def get_order_status(self, order_id: str) -> Order:
        """
        获取订单状态

        Args:
            order_id: 订单 ID

        Returns:
            Order 对象
        """
        data = self._request("GET", f"/api/{self.API_VERSION}/orders/{order_id}")
        order_data = data.get("data", data) if isinstance(data, dict) else data
        return Order.from_dict(order_data)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        取消订单

        Args:
            order_id: 订单 ID

        Returns:
            操作结果
        """
        return self._request("DELETE", f"/api/{self.API_VERSION}/orders/{order_id}")

    # ==================== 账户 API ====================

    def get_account_info(self) -> AccountInfo:
        """
        获取账户信息

        Returns:
            AccountInfo 对象
        """
        data = self._request("GET", f"/api/{self.API_VERSION}/account/info")
        info = data.get("data", data) if isinstance(data, dict) else data
        return AccountInfo.from_dict(info)

    def get_account_balance(self) -> List[AccountBalance]:
        """
        获取账户余额

        Returns:
            AccountBalance 列表
        """
        data = self._request("GET", f"/api/{self.API_VERSION}/account/balance")
        balances = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(balances, list):
            return [AccountBalance.from_dict(b) for b in balances]
        return [AccountBalance.from_dict(balances)] if isinstance(balances, dict) else []

    # ==================== 回测 API ====================

    def run_backtest(self, config: Union[BacktestConfig, Dict[str, Any]]) -> BacktestResult:
        """
        运行回测

        Args:
            config: 回测配置（BacktestConfig 对象或字典）

        Returns:
            BacktestResult 对象
        """
        if isinstance(config, BacktestConfig):
            payload = config.to_dict()
        else:
            payload = config
        data = self._request("POST", f"/api/{self.API_VERSION}/backtest/run", data=payload)
        result = data.get("data", data) if isinstance(data, dict) else data
        return BacktestResult.from_dict(result)

    def get_backtest_results(self, limit: int = 20) -> List[BacktestResult]:
        """
        获取回测结果列表

        Args:
            limit: 返回条数

        Returns:
            BacktestResult 列表
        """
        params = {"limit": limit}
        data = self._request("GET", f"/api/{self.API_VERSION}/backtest/results", params=params)
        results = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(results, list):
            return [BacktestResult.from_dict(r) for r in results]
        return [BacktestResult.from_dict(results)] if isinstance(results, dict) else []

    def get_backtest_detail(self, backtest_id: str) -> BacktestResult:
        """
        获取回测详情

        Args:
            backtest_id: 回测 ID

        Returns:
            BacktestResult 对象
        """
        data = self._request("GET", f"/api/{self.API_VERSION}/backtest/results/{backtest_id}")
        result = data.get("data", data) if isinstance(data, dict) else data
        return BacktestResult.from_dict(result)

    # ==================== AI API ====================

    def ai_query(self, query: str, market: Optional[str] = None) -> AIResponse:
        """
        自然语言查询

        Args:
            query: 查询文本
            market: 市场标识

        Returns:
            AIResponse 对象
        """
        payload = {"query": query}
        if market:
            payload["market"] = market
        data = self._request("POST", f"/api/{self.API_VERSION}/ai/query", data=payload)
        resp = data.get("data", data) if isinstance(data, dict) else data
        return AIResponse.from_dict(resp)

    def ai_chat(self, session_id: str, message: str) -> Dict[str, Any]:
        """
        AI 对话

        Args:
            session_id: 会话 ID
            message: 消息内容

        Returns:
            对话响应
        """
        payload = {"session_id": session_id, "message": message}
        return self._request("POST", f"/api/{self.API_VERSION}/ai/chat", data=payload)

    def get_market_sentiment(self, market: str) -> MarketSentiment:
        """
        获取市场情绪

        Args:
            market: 市场标识

        Returns:
            MarketSentiment 对象
        """
        params = {"market": market}
        data = self._request("GET", f"/api/{self.API_VERSION}/ai/sentiment", params=params)
        sentiment = data.get("data", data) if isinstance(data, dict) else data
        return MarketSentiment.from_dict(sentiment)

    def get_strategy_advice(
        self,
        market: str,
        risk_level: str = "medium",
    ) -> StrategyAdvice:
        """
        获取策略建议

        Args:
            market: 市场标识
            risk_level: 风险等级（low/medium/high）

        Returns:
            StrategyAdvice 对象
        """
        params = {"market": market, "risk_level": risk_level}
        data = self._request("GET", f"/api/{self.API_VERSION}/ai/advice", params=params)
        advice = data.get("data", data) if isinstance(data, dict) else data
        return StrategyAdvice.from_dict(advice)

    # ==================== 使用统计 API ====================

    def get_usage_stats(self) -> UsageStats:
        """
        获取使用统计

        Returns:
            UsageStats 对象
        """
        data = self._request("GET", f"/api/{self.API_VERSION}/usage/stats")
        stats = data.get("data", data) if isinstance(data, dict) else data
        return UsageStats.from_dict(stats)

    # ==================== 工具方法 ====================

    def close(self):
        """关闭客户端会话"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
