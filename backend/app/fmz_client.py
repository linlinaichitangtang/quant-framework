"""
FMZ 发明者量化平台 API 客户端

基于 FMZ 扩展 API（Extended API）实现，核心机制：
- 通过 CommandRobot(robotId, cmd) 向 FMZ 机器人发送交易命令
- 机器人端通过 GetCommand() 接收命令并执行实际交易
- 通过 GetRobotDetail(robotId) 获取机器人状态和持仓信息

签名方式：MD5(version|method|args|nonce|secretKey)
API 地址：https://www.fmz.com/api/v1

参考文档：https://www.fmz.com/api
"""

import hashlib
import time
import json
import logging
from typing import Optional, Dict, List, Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import settings

logger = logging.getLogger(__name__)


class FMZAPIError(Exception):
    """FMZ API 异常"""
    def __init__(self, message: str, code: int = -1, data: Any = None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(self.message)


class FMZClient:
    """FMZ 发明者量化平台 API 客户端"""

    BASE_URL = "https://www.fmz.com/api/v1"
    VERSION = "1.0"

    # FMZ 机器人状态码
    ROBOT_STATUS = {
        0: "空闲",
        1: "运行中",
        2: "已停止",
        3: "错误",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        robot_id: Optional[int] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        初始化 FMZ 客户端

        Args:
            api_key: FMZ API Access Key
            secret_key: FMZ API Secret Key
            robot_id: FMZ 机器人 ID（用于 CommandRobot）
            timeout: 请求超时秒数
            max_retries: 最大重试次数
        """
        self.api_key = api_key or settings.fmz_api_key
        self.secret_key = secret_key or settings.fmz_secret_key
        self.robot_id = robot_id or settings.fmz_cid
        self.timeout = timeout
        self.max_retries = max_retries

        # 创建带重试的 HTTP session
        self._session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _check_config(self) -> bool:
        """检查 FMZ 配置是否完整"""
        if not self.api_key or not self.secret_key:
            return False
        return True

    def _generate_sign(self, method: str, args: Any, nonce: int) -> str:
        """
        生成 FMZ API 签名

        签名规则：MD5(version + "|" + method + "|" + args + "|" + nonce + "|" + secretKey)

        Args:
            method: API 方法名
            args: 方法参数（会被 JSON 序列化）
            nonce: 时间戳（毫秒）

        Returns:
            MD5 签名字符串
        """
        args_str = json.dumps(args, separators=(',', ':')) if args is not None else ""
        sign_str = f"{self.VERSION}|{method}|{args_str}|{nonce}|{self.secret_key}"
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    def _call_api(self, method: str, args: Optional[List] = None) -> Dict:
        """
        调用 FMZ 扩展 API

        Args:
            method: API 方法名（如 CommandRobot, GetRobotList, GetRobotDetail）
            args: 方法参数列表

        Returns:
            API 响应字典

        Raises:
            FMZAPIError: API 调用失败
        """
        if not self._check_config():
            raise FMZAPIError("FMZ API 未配置，请检查 fmz_api_key 和 fmz_secret_key")

        nonce = int(time.time() * 1000)
        args = args or []
        sign = self._generate_sign(method, args, nonce)

        params = {
            "access_key": self.api_key,
            "nonce": nonce,
            "args": json.dumps(args, separators=(',', ':')),
            "sign": sign,
            "version": self.VERSION,
            "method": method,
        }

        try:
            response = self._session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                error_msg = result.get("msg", "未知错误")
                logger.error(f"FMZ API 错误: method={method}, code={result.get('code')}, msg={error_msg}")
                raise FMZAPIError(error_msg, code=result.get("code"), data=result)

            return result

        except requests.exceptions.Timeout:
            logger.error(f"FMZ API 超时: method={method}")
            raise FMZAPIError(f"请求超时 ({self.timeout}s)")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"FMZ API 连接失败: {e}")
            raise FMZAPIError(f"连接失败: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"FMZ API 请求异常: {e}")
            raise FMZAPIError(f"请求异常: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"FMZ API 响应解析失败: {e}")
            raise FMZAPIError(f"响应解析失败: {e}")

    # ========== 机器人管理 ==========

    def get_node_list(self) -> List[Dict]:
        """获取托管者节点列表"""
        result = self._call_api("GetNodeList")
        return result.get("data", {}).get("result", [])

    def get_robot_list(
        self,
        offset: int = 0,
        length: int = 50,
        robot_status: int = -1,
        label: Optional[str] = None
    ) -> List[Dict]:
        """
        获取机器人列表

        Args:
            offset: 页码偏移
            length: 每页数量
            robot_status: 机器人状态（-1=全部, 0=空闲, 1=运行中, 2=已停止, 3=错误）
            label: 标签过滤
        """
        args = [offset, length, robot_status]
        if label:
            args.append(label)
        result = self._call_api("GetRobotList", args)
        robots = result.get("data", {}).get("result", {}).get("robots", [])
        return robots

    def get_robot_detail(self, robot_id: Optional[int] = None) -> Dict:
        """
        获取机器人详细信息

        Args:
            robot_id: 机器人 ID（默认使用初始化时的 robot_id）
        """
        rid = robot_id or self.robot_id
        if not rid:
            raise FMZAPIError("未指定 robot_id")
        result = self._call_api("GetRobotDetail", [rid])
        return result.get("data", {}).get("result", {}).get("robot", {})

    def get_all_running_robots(self) -> List[Dict]:
        """获取所有运行中的机器人"""
        return self.get_robot_list(robot_status=1)

    # ========== 机器人控制 ==========

    def command_robot(
        self,
        cmd: str,
        robot_id: Optional[int] = None
    ) -> Dict:
        """
        向机器人发送交互命令

        这是 FMZ 对接的核心方法。通过此方法向机器人发送命令字符串，
        机器人端通过 GetCommand() 接收并执行。

        命令格式约定（与 FMZ 机器人端协议一致）：
        - 买入: "buy:price:amount"
        - 卖出: "sell:price:amount"
        - 平多: "cover_long:price:amount"
        - 平空: "cover_short:price:amount"
        - 查询持仓: "query_position"
        - 查询账户: "query_account"

        Args:
            cmd: 命令字符串
            robot_id: 机器人 ID

        Returns:
            API 响应
        """
        rid = robot_id or self.robot_id
        if not rid:
            raise FMZAPIError("未指定 robot_id，无法发送命令")

        logger.info(f"FMZ CommandRobot: robot_id={rid}, cmd={cmd}")
        return self._call_api("CommandRobot", [rid, cmd])

    def restart_robot(self, robot_id: Optional[int] = None) -> Dict:
        """重启机器人"""
        rid = robot_id or self.robot_id
        if not rid:
            raise FMZAPIError("未指定 robot_id")
        return self._call_api("RestartRobot", [rid])

    def stop_robot(self, robot_id: Optional[int] = None) -> Dict:
        """停止机器人"""
        rid = robot_id or self.robot_id
        if not rid:
            raise FMZAPIError("未指定 robot_id")
        return self._call_api("StopRobot", [rid])

    # ========== 信号执行（核心链路）==========

    def execute_signal(self, signal) -> Dict:
        """
        执行交易信号 — 将信号转化为 FMZ 命令并发送

        这是 OpenClaw → FMZ 的核心链路入口。
        将 TradingSignal 对象转化为 FMZ 机器人可识别的命令字符串。

        命令协议：
        {
            "action": "buy|sell|cover_long|cover_short",
            "symbol": "股票代码",
            "price": 目标价格,
            "amount": 数量,
            "stop_loss": 止损价,
            "take_profit": 止盈价,
            "signal_id": 信号ID,
            "strategy": 策略名称
        }

        Args:
            signal: TradingSignal 数据库模型实例

        Returns:
            执行结果字典 {
                "success": bool,
                "message": str,
                "command": str,
                "robot_id": int,
                "fmz_response": dict
            }
        """
        if not self._check_config():
            return {
                "success": False,
                "message": "FMZ API 未配置",
                "command": "",
                "robot_id": None,
                "fmz_response": None
            }

        # 构建命令对象
        side = signal.side.upper()
        action = "buy" if side == "BUY" else "sell"

        # 如果是期权相关，使用期货方向
        if hasattr(signal, 'signal_type') and signal.signal_type == "OPTION":
            if side == "BUY":
                action = "long"
            else:
                action = "cover_long"

        price = signal.target_price or 0
        quantity = signal.quantity or 100

        cmd_obj = {
            "action": action,
            "symbol": signal.symbol,
            "price": price,
            "amount": quantity,
        }

        # 可选字段
        if signal.stop_loss:
            cmd_obj["stop_loss"] = signal.stop_loss
        if signal.take_profit:
            cmd_obj["take_profit"] = signal.take_profit
        if signal.strategy_name:
            cmd_obj["strategy"] = signal.strategy_name
        if signal.id:
            cmd_obj["signal_id"] = signal.id

        cmd_str = json.dumps(cmd_obj, ensure_ascii=False)

        try:
            fmz_response = self.command_robot(cmd_str)
            return {
                "success": True,
                "message": f"命令已发送到机器人 {self.robot_id}",
                "command": cmd_str,
                "robot_id": self.robot_id,
                "fmz_response": fmz_response
            }
        except FMZAPIError as e:
            return {
                "success": False,
                "message": f"FMZ 命令发送失败: {e.message}",
                "command": cmd_str,
                "robot_id": self.robot_id,
                "fmz_response": None
            }

    def execute_signal_simple(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        market: str = "A",
        robot_id: Optional[int] = None
    ) -> Dict:
        """
        简化版信号执行（无需数据库信号对象）

        Args:
            symbol: 股票代码
            side: BUY/SELL
            price: 目标价格
            quantity: 数量
            market: 市场标识
            robot_id: 机器人 ID
        """
        action = "buy" if side.upper() == "BUY" else "sell"
        cmd_obj = {
            "action": action,
            "symbol": symbol,
            "price": price,
            "amount": quantity,
            "market": market
        }
        cmd_str = json.dumps(cmd_obj, ensure_ascii=False)

        try:
            fmz_response = self.command_robot(cmd_str, robot_id=robot_id)
            return {
                "success": True,
                "message": "命令已发送",
                "command": cmd_str,
                "fmz_response": fmz_response
            }
        except FMZAPIError as e:
            return {
                "success": False,
                "message": str(e),
                "command": cmd_str,
                "fmz_response": None
            }

    # ========== 持仓与账户同步 ==========

    def sync_robot_status(self, robot_id: Optional[int] = None) -> Dict:
        """
        获取机器人运行状态

        Returns:
            {
                "robot_id": int,
                "name": str,
                "status": int,
                "status_text": str,
                "strategy_name": str,
                "refresh": datetime_str,
                "charged": float,
                "consumed": float
            }
        """
        detail = self.get_robot_detail(robot_id)
        status = detail.get("status", -1)
        return {
            "robot_id": detail.get("id"),
            "name": detail.get("name"),
            "status": status,
            "status_text": self.ROBOT_STATUS.get(status, "未知"),
            "strategy_name": detail.get("strategy_name"),
            "refresh": detail.get("refresh"),
            "charged": detail.get("charged"),
            "consumed": detail.get("consumed"),
        }

    def query_position(self, robot_id: Optional[int] = None) -> Dict:
        """
        查询机器人持仓（通过发送查询命令）

        机器人端需要支持 "query_position" 命令并返回持仓 JSON。
        """
        cmd_obj = {"action": "query_position"}
        cmd_str = json.dumps(cmd_obj)
        try:
            return self.command_robot(cmd_str, robot_id=robot_id)
        except FMZAPIError as e:
            return {"success": False, "message": str(e)}

    def query_account(self, robot_id: Optional[int] = None) -> Dict:
        """
        查询机器人账户信息（通过发送查询命令）

        机器人端需要支持 "query_account" 命令并返回账户 JSON。
        """
        cmd_obj = {"action": "query_account"}
        cmd_str = json.dumps(cmd_obj)
        try:
            return self.command_robot(cmd_str, robot_id=robot_id)
        except FMZAPIError as e:
            return {"success": False, "message": str(e)}

    # ========== 批量操作 ==========

    def batch_execute_signals(self, signals: List, robot_id: Optional[int] = None) -> List[Dict]:
        """
        批量执行交易信号

        Args:
            signals: TradingSignal 列表
            robot_id: 机器人 ID

        Returns:
            执行结果列表
        """
        results = []
        for signal in signals:
            result = self.execute_signal(signal)
            results.append(result)
            # 避免频率限制，间隔 500ms
            time.sleep(0.5)
        return results

    def get_robots_by_market(self, market: str) -> List[Dict]:
        """
        获取指定市场的运行中机器人

        通过机器人名称标签匹配市场（约定：机器人名称包含市场标识）
        """
        robots = self.get_all_running_robots()
        market_map = {
            "A": ["A股", "CN", "cn", "china"],
            "HK": ["港股", "HK", "hk", "hongkong"],
            "US": ["美股", "US", "us", "usa"],
        }
        keywords = market_map.get(market, [market])
        matched = []
        for robot in robots:
            name = robot.get("name", "").lower()
            label = robot.get("label", "").lower()
            if any(kw.lower() in name or kw.lower() in label for kw in keywords):
                matched.append(robot)
        return matched

    def close(self):
        """关闭 HTTP session"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
