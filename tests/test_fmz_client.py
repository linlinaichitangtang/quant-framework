"""
FMZ 客户端单元测试

测试 FMZ API 签名生成、命令构建、信号执行等核心逻辑。
不依赖真实 FMZ API，使用 mock。
"""

import json
import hashlib
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.fmz_client import FMZClient, FMZAPIError


class TestFMZSignature:
    """FMZ 签名生成测试"""

    def setup_method(self):
        self.client = FMZClient(
            api_key="test_access_key",
            secret_key="test_secret_key",
            robot_id=12345
        )

    def test_sign_format(self):
        """签名格式：MD5(version|method|args|nonce|secretKey)"""
        method = "CommandRobot"
        args = [12345, "buy:100"]
        nonce = 1700000000000

        sign = self.client._generate_sign(method, args, nonce)

        # 验证签名是32位十六进制字符串
        assert len(sign) == 32
        assert all(c in '0123456789abcdef' for c in sign)

        # 手动计算验证
        args_str = json.dumps(args, separators=(',', ':'))
        expected_str = f"1.0|CommandRobot|{args_str}|{nonce}|test_secret_key"
        expected_sign = hashlib.md5(expected_str.encode('utf-8')).hexdigest()
        assert sign == expected_sign

    def test_sign_empty_args(self):
        """空参数签名"""
        sign = self.client._generate_sign("GetNodeList", [], 1700000000000)
        assert len(sign) == 32

    def test_sign_none_args(self):
        """None 参数签名"""
        sign = self.client._generate_sign("GetNodeList", None, 1700000000000)
        assert len(sign) == 32

    def test_sign_different_methods(self):
        """不同方法产生不同签名"""
        sign1 = self.client._generate_sign("GetNodeList", [], 1700000000000)
        sign2 = self.client._generate_sign("GetRobotList", [], 1700000000000)
        assert sign1 != sign2


class TestFMZClientInit:
    """FMZ 客户端初始化测试"""

    def test_default_init(self):
        """默认初始化"""
        client = FMZClient()
        assert client.api_key == ""
        assert client.secret_key == ""
        assert client.robot_id == 0

    def test_custom_init(self):
        """自定义初始化"""
        client = FMZClient(
            api_key="my_key",
            secret_key="my_secret",
            robot_id=99999,
            timeout=60,
            max_retries=5
        )
        assert client.api_key == "my_key"
        assert client.secret_key == "my_secret"
        assert client.robot_id == 99999
        assert client.timeout == 60
        assert client.max_retries == 5

    def test_check_config_missing(self):
        """配置缺失检查"""
        client = FMZClient()
        assert client._check_config() is False

    def test_check_config_complete(self):
        """配置完整检查"""
        client = FMZClient(api_key="key", secret_key="secret")
        assert client._check_config() is True

    def test_context_manager(self):
        """上下文管理器"""
        with FMZClient(api_key="key", secret_key="secret") as client:
            assert client._session is not None


class TestFMZCommandBuilding:
    """FMZ 命令构建测试"""

    def setup_method(self):
        self.client = FMZClient(
            api_key="test_key",
            secret_key="test_secret",
            robot_id=12345
        )

    def test_execute_signal_buy(self):
        """买入信号命令构建"""
        signal = MagicMock()
        signal.side = "BUY"
        signal.symbol = "000001"
        signal.target_price = 15.5
        signal.quantity = 100
        signal.stop_loss = 15.0
        signal.take_profit = 16.5
        signal.strategy_name = "A股尾盘策略"
        signal.id = 1
        signal.signal_type = "OPEN"

        with patch.object(self.client, 'command_robot') as mock_cmd:
            mock_cmd.return_value = {"code": 0}
            result = self.client.execute_signal(signal)

            assert result["success"] is True
            cmd = json.loads(result["command"])
            assert cmd["action"] == "buy"
            assert cmd["symbol"] == "000001"
            assert cmd["price"] == 15.5
            assert cmd["amount"] == 100
            assert cmd["stop_loss"] == 15.0
            assert cmd["take_profit"] == 16.5
            assert cmd["strategy"] == "A股尾盘策略"
            assert cmd["signal_id"] == 1

    def test_execute_signal_sell(self):
        """卖出信号命令构建"""
        signal = MagicMock()
        signal.side = "SELL"
        signal.symbol = "600036"
        signal.target_price = 40.0
        signal.quantity = 200
        signal.stop_loss = None
        signal.take_profit = None
        signal.strategy_name = None
        signal.id = 2
        signal.signal_type = "CLOSE"

        result = self.client.execute_signal(signal)

        cmd = json.loads(result["command"])
        assert cmd["action"] == "sell"
        assert cmd["symbol"] == "600036"
        assert cmd["price"] == 40.0
        assert cmd["amount"] == 200
        assert "stop_loss" not in cmd
        assert "take_profit" not in cmd

    def test_execute_signal_option_long(self):
        """期权开多信号"""
        signal = MagicMock()
        signal.side = "BUY"
        signal.symbol = "AAPL"
        signal.target_price = 180.0
        signal.quantity = 1
        signal.stop_loss = None
        signal.take_profit = None
        signal.strategy_name = "期权策略"
        signal.id = 3
        signal.signal_type = "OPTION"

        result = self.client.execute_signal(signal)

        cmd = json.loads(result["command"])
        assert cmd["action"] == "long"

    def test_execute_signal_no_config(self):
        """无配置时返回失败"""
        client = FMZClient()  # 无 API key
        signal = MagicMock()
        signal.side = "BUY"
        signal.symbol = "000001"
        signal.target_price = 15.0
        signal.quantity = 100
        signal.stop_loss = None
        signal.take_profit = None
        signal.strategy_name = None
        signal.id = 1
        signal.signal_type = "OPEN"

        result = client.execute_signal(signal)
        assert result["success"] is False
        assert "未配置" in result["message"]

    def test_execute_signal_simple(self):
        """简化版信号执行"""
        with patch.object(self.client, 'command_robot') as mock_cmd:
            mock_cmd.return_value = {"code": 0}
            result = self.client.execute_signal_simple(
                symbol="000001",
                side="BUY",
                price=15.0,
                quantity=100,
                market="A"
            )
            assert result["success"] is True
            cmd = json.loads(result["command"])
            assert cmd["action"] == "buy"
            assert cmd["market"] == "A"


class TestFMZAPICall:
    """FMZ API 调用测试（mock HTTP）"""

    def setup_method(self):
        self.client = FMZClient(
            api_key="test_key",
            secret_key="test_secret",
            robot_id=12345
        )

    def test_call_api_success(self):
        """API 调用成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "data": {"result": "ok"}}

        with patch.object(self.client._session, 'get', return_value=mock_response):
            result = self.client._call_api("GetNodeList")
            assert result["code"] == 0

    def test_call_api_error_response(self):
        """API 返回错误码"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 1, "msg": "权限不足"}

        with patch.object(self.client._session, 'get', return_value=mock_response):
            with pytest.raises(FMZAPIError) as exc_info:
                self.client._call_api("GetNodeList")
            assert "权限不足" in str(exc_info.value)

    def test_call_api_http_error(self):
        """HTTP 错误"""
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")

        with patch.object(self.client._session, 'get', return_value=mock_response):
            with pytest.raises(FMZAPIError):
                self.client._call_api("GetNodeList")

    def test_call_api_timeout(self):
        """请求超时"""
        import requests
        with patch.object(self.client._session, 'get', side_effect=requests.exceptions.Timeout):
            with pytest.raises(FMZAPIError) as exc_info:
                self.client._call_api("GetNodeList")
            assert "超时" in str(exc_info.value)

    def test_call_api_no_config(self):
        """无配置时抛出异常"""
        client = FMZClient()
        with pytest.raises(FMZAPIError) as exc_info:
            client._call_api("GetNodeList")
        assert "未配置" in str(exc_info.value)


class TestFMZRobotManagement:
    """FMZ 机器人管理测试"""

    def setup_method(self):
        self.client = FMZClient(
            api_key="test_key",
            secret_key="test_secret",
            robot_id=12345
        )

    def test_get_node_list(self):
        """获取节点列表"""
        with patch.object(self.client, '_call_api') as mock_api:
            mock_api.return_value = {"code": 0, "data": {"result": [{"id": 1}]}}
            nodes = self.client.get_node_list()
            assert len(nodes) == 1

    def test_get_robot_list(self):
        """获取机器人列表"""
        with patch.object(self.client, '_call_api') as mock_api:
            mock_api.return_value = {
                "code": 0,
                "data": {"result": {"robots": [{"id": 100, "name": "test"}]}}
            }
            robots = self.client.get_robot_list(offset=0, length=10, robot_status=1)
            assert len(robots) == 1
            mock_api.assert_called_once_with("GetRobotList", [0, 10, 1])

    def test_get_robot_detail(self):
        """获取机器人详情"""
        with patch.object(self.client, '_call_api') as mock_api:
            mock_api.return_value = {
                "code": 0,
                "data": {"result": {"robot": {"id": 12345, "status": 1}}}
            }
            detail = self.client.get_robot_detail()
            assert detail["id"] == 12345
            mock_api.assert_called_once_with("GetRobotDetail", [12345])

    def test_get_robot_detail_no_id(self):
        """无 robot_id 时抛出异常"""
        client = FMZClient(api_key="key", secret_key="secret")
        with pytest.raises(FMZAPIError):
            client.get_robot_detail()

    def test_command_robot(self):
        """发送命令到机器人"""
        with patch.object(self.client, '_call_api') as mock_api:
            mock_api.return_value = {"code": 0}
            result = self.client.command_robot("buy:100")
            mock_api.assert_called_once_with("CommandRobot", [12345, "buy:100"])

    def test_command_robot_no_id(self):
        """无 robot_id 时抛出异常"""
        client = FMZClient(api_key="key", secret_key="secret")
        with pytest.raises(FMZAPIError):
            client.command_robot("test")

    def test_sync_robot_status(self):
        """同步机器人状态"""
        with patch.object(self.client, 'get_robot_detail') as mock_detail:
            mock_detail.return_value = {
                "id": 12345,
                "name": "A股策略机器人",
                "status": 1,
                "strategy_name": "尾盘策略",
                "refresh": "2026-04-01 15:30:00"
            }
            status = self.client.sync_robot_status()
            assert status["status_text"] == "运行中"
            assert status["name"] == "A股策略机器人"

    def test_restart_robot(self):
        """重启机器人"""
        with patch.object(self.client, '_call_api') as mock_api:
            mock_api.return_value = {"code": 0}
            self.client.restart_robot()
            mock_api.assert_called_once_with("RestartRobot", [12345])

    def test_stop_robot(self):
        """停止机器人"""
        with patch.object(self.client, '_call_api') as mock_api:
            mock_api.return_value = {"code": 0}
            self.client.stop_robot()
            mock_api.assert_called_once_with("StopRobot", [12345])


class TestFMZBatchOperations:
    """FMZ 批量操作测试"""

    def setup_method(self):
        self.client = FMZClient(
            api_key="test_key",
            secret_key="test_secret",
            robot_id=12345
        )

    def test_batch_execute_signals(self):
        """批量执行信号"""
        signals = []
        for i in range(3):
            signal = MagicMock()
            signal.side = "BUY"
            signal.symbol = f"00000{i+1}"
            signal.target_price = 10.0 + i
            signal.quantity = 100
            signal.stop_loss = None
            signal.take_profit = None
            signal.strategy_name = None
            signal.id = i + 1
            signal.signal_type = "OPEN"
            signals.append(signal)

        with patch.object(self.client, 'command_robot') as mock_cmd:
            mock_cmd.return_value = {"code": 0}
            results = self.client.batch_execute_signals(signals)
            assert len(results) == 3
            assert all(r["success"] for r in results)
            assert mock_cmd.call_count == 3

    def test_get_robots_by_market(self):
        """按市场筛选机器人"""
        with patch.object(self.client, 'get_all_running_robots') as mock_list:
            mock_list.return_value = [
                {"id": 1, "name": "A股策略", "label": "CN"},
                {"id": 2, "name": "港股策略", "label": "HK"},
                {"id": 3, "name": "美股策略", "label": "US"},
            ]
            cn_robots = self.client.get_robots_by_market("A")
            assert len(cn_robots) == 1
            assert cn_robots[0]["name"] == "A股策略"

            hk_robots = self.client.get_robots_by_market("HK")
            assert len(hk_robots) == 1
