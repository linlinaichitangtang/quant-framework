"""
V1.5 智能分析助手 + V2.0 平台化 单元测试
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, date
from typing import Any, Dict, List

import sys
import os

# 将 backend 目录加入 sys.path 以便导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm_client import LLMClient, LLMProvider, LLMError
from app.sentiment_analyzer import SentimentAnalyzer
from app.anomaly_detector import AnomalyDetector
from app.strategy_attribution import StrategyAttributor
from app.ai_service import AIService
from app.tenant_service import TenantService
from app.plugin_system import PluginManager
from app.api_key_service import APIKeyService, API_KEY_PREFIX
from app.billing_service import BillingService, DEFAULT_PLANS


# ============================================================================
# 1. TestLLMClient — LLM 客户端测试
# ============================================================================

class TestLLMClient:
    """LLM 客户端单元测试"""

    def test_init_openai(self):
        """测试 OpenAI 客户端初始化"""
        client = LLMClient(
            provider=LLMProvider.OPENAI,
            api_key="sk-test-key",
        )
        assert client.provider == LLMProvider.OPENAI
        assert client.api_key == "sk-test-key"
        assert client.base_url == "https://api.openai.com/v1"
        assert client.model_name == "gpt-4o-mini"

    def test_init_ollama(self):
        """测试 Ollama 客户端初始化（base_url 应为 localhost）"""
        client = LLMClient(provider=LLMProvider.OLLAMA)
        assert client.provider == LLMProvider.OLLAMA
        assert "localhost" in client.base_url
        assert "11434" in client.base_url
        # Ollama 无需 API Key 时应自动设置默认值
        assert client.api_key == "ollama"
        assert client.model_name == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """测试成功聊天（mock aiohttp 响应）"""
        client = LLMClient(
            provider=LLMProvider.DEEPSEEK,
            api_key="test-key",
            max_retries=1,
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Hello, world!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })

        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.return_value = mock_post_cm

        with patch("app.llm_client.aiohttp.ClientSession", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_chat_retry_on_429(self):
        """测试 429 错误重试"""
        client = LLMClient(
            provider=LLMProvider.DEEPSEEK,
            api_key="test-key",
            max_retries=2,
            retry_delay=0.01,
        )

        # 第一次返回 429，第二次返回 200
        mock_response_429 = AsyncMock()
        mock_response_429.status = 429
        mock_response_429.text = AsyncMock(return_value="Rate limited")

        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "Retry success"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        })

        mock_post_cm_429 = MagicMock()
        mock_post_cm_429.__aenter__ = AsyncMock(return_value=mock_response_429)
        mock_post_cm_429.__aexit__ = AsyncMock(return_value=False)

        mock_post_cm_200 = MagicMock()
        mock_post_cm_200.__aenter__ = AsyncMock(return_value=mock_response_200)
        mock_post_cm_200.__aexit__ = AsyncMock(return_value=False)

        call_count = 0

        def mock_post(url, json=None, headers=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_post_cm_429
            return mock_post_cm_200

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.side_effect = mock_post

        with patch("app.llm_client.aiohttp.ClientSession", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "Hi"}])

        assert result == "Retry success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_chat_with_system(self):
        """测试带系统提示词的聊天"""
        client = LLMClient(
            provider=LLMProvider.DEEPSEEK,
            api_key="test-key",
            max_retries=1,
        )

        captured_messages = None

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "System response"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        })

        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=False)

        def mock_post(url, json=None, headers=None):
            nonlocal captured_messages
            captured_messages = json.get("messages")
            return mock_post_cm

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post.side_effect = mock_post

        with patch("app.llm_client.aiohttp.ClientSession", return_value=mock_session):
            result = await client.chat_with_system(
                system_prompt="You are a helpful assistant.",
                user_message="Hello",
            )

        assert result == "System response"
        assert captured_messages is not None
        assert len(captured_messages) == 2
        assert captured_messages[0]["role"] == "system"
        assert captured_messages[0]["content"] == "You are a helpful assistant."
        assert captured_messages[1]["role"] == "user"
        assert captured_messages[1]["content"] == "Hello"


# ============================================================================
# 2. TestSentimentAnalyzer — 情绪分析器测试
# ============================================================================

class TestSentimentAnalyzer:
    """情绪分析器单元测试"""

    def setup_method(self):
        self.analyzer = SentimentAnalyzer()

    def test_analyze_text_positive(self):
        """测试正面文本分析"""
        result = self.analyzer.analyze_text("市场大幅上涨，利好消息不断，资金净流入明显")
        assert result["sentiment"] == "positive"
        assert result["score"] > 0
        assert result["positive_count"] > 0

    def test_analyze_text_negative(self):
        """测试负面文本分析"""
        result = self.analyzer.analyze_text("市场暴跌，利空消息频出，资金大幅流出")
        assert result["sentiment"] == "negative"
        assert result["score"] < 0
        assert result["negative_count"] > 0

    def test_analyze_text_neutral(self):
        """测试中性文本分析"""
        result = self.analyzer.analyze_text("市场震荡整理，分析师预计或将维持稳定")
        assert result["sentiment"] == "neutral"
        assert result["neutral_count"] > 0

    def test_analyze_news_batch(self):
        """测试批量新闻分析"""
        news_list = [
            {"title": "A股大涨创新高", "content": "利好消息推动市场上涨"},
            {"title": "市场震荡调整", "content": "技术性回调正常"},
            {"title": "经济下行压力加大", "content": "多项指标不及预期"},
        ]
        result = self.analyzer.analyze_news_batch(news_list)
        assert result["total"] == 3
        assert "positive" in result["sentiment_distribution"]
        assert "negative" in result["sentiment_distribution"]
        assert "neutral" in result["sentiment_distribution"]
        assert len(result["details"]) == 3
        assert isinstance(result["average_score"], float)

    def test_calculate_market_sentiment(self):
        """测试市场综合情绪"""
        news = [
            {"title": "市场持续上涨", "content": "资金大幅流入"},
            {"title": "利好政策出台", "content": "降息降准刺激经济"},
            {"title": "业绩大增", "content": "多家公司超预期"},
        ]
        result = self.analyzer.calculate_market_sentiment("A", news)
        assert result["market"] == "A"
        assert result["sentiment"] in ("positive", "negative", "neutral")
        assert "score" in result
        assert "confidence" in result
        assert "distribution" in result
        assert "summary" in result
        assert result["market_display"] == "A股"


# ============================================================================
# 3. TestAnomalyDetector — 异常检测器测试
# ============================================================================

class TestAnomalyDetector:
    """异常检测器单元测试"""

    def setup_method(self):
        self.detector = AnomalyDetector(
            z_score_threshold=2.5,
            iqr_multiplier=1.5,
            volume_z_threshold=2.5,
        )

    def test_detect_price_anomaly(self):
        """测试价格异常检测（注入异常值）"""
        import random
        random.seed(42)
        # 生成正常价格序列
        prices = [100.0]
        for _ in range(29):
            prices.append(prices[-1] * (1 + random.gauss(0, 0.01)))
        # 注入一个异常值（暴涨 15%）
        prices[25] = prices[24] * 1.15

        anomalies = self.detector.detect_price_anomaly(prices)
        assert len(anomalies) > 0
        # 检查异常记录结构
        anomaly = anomalies[0]
        assert "index" in anomaly
        assert "price" in anomaly
        assert "z_score" in anomaly
        assert "severity" in anomaly
        assert "type" in anomaly

    def test_detect_volume_anomaly(self):
        """测试成交量异常检测"""
        import random
        random.seed(42)
        # 生成正常成交量序列
        volumes = [1000000.0 + random.gauss(0, 100000) for _ in range(30)]
        # 注入一个异常成交量（10倍于正常）
        volumes[20] = 10000000.0

        anomalies = self.detector.detect_volume_anomaly(volumes)
        assert len(anomalies) > 0
        anomaly = anomalies[0]
        assert "index" in anomaly
        assert "volume" in anomaly
        assert "z_score" in anomaly
        assert "type" in anomaly

    def test_detect_no_anomaly(self):
        """测试正常数据无异常"""
        # 使用完全恒定的数据（无随机性），确保无异常
        prices = [100.0 + i * 0.1 for i in range(30)]

        anomalies = self.detector.detect_price_anomaly(prices)
        # 恒定增长数据不应有异常
        assert len(anomalies) == 0

    def test_detect_pump_dump(self):
        """测试拉高出货检测"""
        # 构造拉高出货模式：先稳定，然后快速拉高，再急剧下跌
        # lookback=5, dump_threshold=0.10
        # 前5天稳定在10.0
        # 第6-10天从10.0涨到12.0（涨幅20% > 10%阈值）
        # 第11天跌到10.5（跌幅12.5%）
        prices = [10.0] * 5 + [10.5, 11.0, 11.5, 12.0, 12.0, 10.5, 10.0, 9.5]
        # 成交量：稳定期 10万，拉高期间放大到 100万+
        # 使用较低的 volume_spike_threshold 以匹配测试数据
        volumes = [100000] * 5 + [800000, 1000000, 1200000, 1500000, 2000000, 300000, 200000, 150000]

        anomalies = self.detector.detect_pump_dump(prices, volumes, volume_spike_threshold=1.5)
        assert len(anomalies) > 0, "应检测到拉高出货模式"
        anomaly = anomalies[0]
        assert anomaly["type"] == "pump_dump"
        assert "pump_gain" in anomaly
        assert "subsequent_drop" in anomaly
        assert "volume_ratio" in anomaly

    def test_generate_anomaly_report(self):
        """测试异常报告生成"""
        anomalies = [
            {"severity": "high", "type": "spike_up", "z_score": 5.0},
            {"severity": "high", "type": "spike_up", "z_score": 4.5},
            {"severity": "high", "type": "spike_down", "z_score": -4.0},
            {"severity": "medium", "type": "volume_spike", "z_score": 3.5},
            {"severity": "low", "type": "volume_spike", "z_score": 3.0},
        ]
        report = self.detector.generate_anomaly_report("600519", anomalies)
        assert report["symbol"] == "600519"
        assert report["total_anomalies"] == 5
        assert report["by_severity"]["high"] == 3
        assert report["by_severity"]["medium"] == 1
        assert report["by_severity"]["low"] == 1
        assert report["risk_level"] == "critical"
        assert "summary" in report


# ============================================================================
# 4. TestStrategyAttributor — 策略归因测试
# ============================================================================

class TestStrategyAttributor:
    """策略归因分析器单元测试"""

    def setup_method(self):
        self.attributor = StrategyAttributor(
            risk_free_rate=0.03,
            benchmark_return=0.10,
        )

    def test_decompose_returns(self):
        """测试收益分解"""
        trades = [
            {"action": "sell", "code": "000001", "pnl": 5000, "pnl_pct": 0.10},
            {"action": "sell", "code": "000002", "pnl": -2000, "pnl_pct": -0.05},
            {"action": "sell", "code": "600519", "pnl": 8000, "pnl_pct": 0.15},
            {"action": "sell", "code": "300750", "pnl": -1000, "pnl_pct": -0.02},
        ]
        result = self.attributor._decompose_returns(trades)
        assert "alpha" in result
        assert "timing" in result
        assert "beta" in result
        assert "total" in result
        assert result["total"] == 10000.0

    def test_analyze_sector_contribution(self):
        """测试行业贡献分析"""
        trades = [
            {"action": "sell", "code": "000001", "pnl": 5000, "pnl_pct": 0.10},
            {"action": "sell", "code": "000001", "pnl": 3000, "pnl_pct": 0.06},
            {"action": "sell", "code": "600519", "pnl": 8000, "pnl_pct": 0.15},
            {"action": "sell", "code": "300750", "pnl": -1000, "pnl_pct": -0.02},
        ]
        result = self.attributor._analyze_sector_contribution(trades)
        assert "by_symbol" in result
        assert "n_symbols" in result
        assert result["n_symbols"] == 3
        assert "concentration" in result
        assert "diversification_score" in result

    def test_analyze_timing(self):
        """测试择时能力分析"""
        trades = [
            {"action": "sell", "pnl": 5000, "pnl_pct": 0.10},
            {"action": "sell", "pnl": 3000, "pnl_pct": 0.06},
            {"action": "sell", "pnl": -2000, "pnl_pct": -0.05},
            {"action": "sell", "pnl": 8000, "pnl_pct": 0.15},
            {"action": "sell", "pnl": -1000, "pnl_pct": -0.02},
            {"action": "sell", "pnl": 4000, "pnl_pct": 0.08},
        ]
        result = self.attributor._analyze_timing(trades)
        assert "timing_score" in result
        assert "win_streak_max" in result
        assert "loss_streak_max" in result
        assert "profit_factor" in result
        assert "win_rate" in result
        assert 0 <= result["timing_score"] <= 100
        assert result["n_wins"] == 4
        assert result["n_losses"] == 2

    def test_generate_report(self):
        """测试报告生成"""
        backtest_result = {
            "total_return": 0.25,
            "annual_return": 0.30,
            "max_drawdown": -0.08,
            "sharpe_ratio": 1.8,
            "win_rate": 0.65,
            "n_trades": 20,
            "initial_capital": 1000000,
            "final_value": 1250000,
        }
        trades = [
            {"action": "sell", "code": "000001", "pnl": 5000, "pnl_pct": 0.10},
            {"action": "sell", "code": "600519", "pnl": 8000, "pnl_pct": 0.15},
            {"action": "sell", "code": "300750", "pnl": -2000, "pnl_pct": -0.05},
        ]
        report = self.attributor.analyze(backtest_result, trades)
        assert "overall_rating" in report
        assert "summary" in report
        assert "return_decomposition" in report
        assert "sector_contribution" in report
        assert "timing_analysis" in report
        assert "risk_contribution" in report
        assert "recommendations" in report


# ============================================================================
# 5. TestAIService — AI 分析服务测试
# ============================================================================

class TestAIService:
    """AI 分析服务单元测试"""

    def _create_mock_ai_service(self):
        """创建 mock 的 AIService"""
        mock_llm = MagicMock(spec=LLMClient)
        mock_db = MagicMock()
        service = AIService(llm_client=mock_llm, db_session=mock_db)
        return service, mock_llm, mock_db

    @pytest.mark.asyncio
    async def test_analyze_market_sentiment(self):
        """测试市场情绪分析（mock LLM）"""
        service, mock_llm, mock_db = self._create_mock_ai_service()

        mock_llm.chat_with_system = AsyncMock(return_value="市场情绪分析结果")

        # Mock 数据库查询返回空列表（触发模拟数据）
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await service.analyze_market_sentiment("A")
        assert result["market"] == "A"
        assert "sentiment" in result
        assert "score" in result
        assert "keyword_analysis" in result
        assert "llm_analysis" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_detect_anomalies(self):
        """测试异常检测"""
        service, mock_llm, mock_db = self._create_mock_ai_service()

        mock_llm.chat_with_system = AsyncMock(return_value="异常分析结果")

        # Mock 数据库查询返回空列表（触发模拟数据）
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = await service.detect_anomalies("600519", "A", days=30)
        assert result["symbol"] == "600519"
        assert result["market"] == "A"
        assert "report" in result
        assert "price_anomalies" in result
        assert "volume_anomalies" in result

    @pytest.mark.asyncio
    async def test_natural_language_query(self):
        """测试自然语言查询"""
        service, mock_llm, mock_db = self._create_mock_ai_service()

        # Mock 意图识别返回 general
        mock_llm.chat_with_system = AsyncMock(return_value='{"intent": "general", "entities": {}}')

        result = await service.natural_language_query("什么是量化交易", user_id=1)
        assert result["query"] == "什么是量化交易"
        assert "intent" in result
        assert "response" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_generate_strategy_advice(self):
        """测试策略建议"""
        service, mock_llm, mock_db = self._create_mock_ai_service()

        mock_llm.chat_with_system = AsyncMock(return_value="1. 当前市场环境良好\n2. 建议配置蓝筹股\n3. 控制仓位在60%")

        # Mock 数据库查询返回空列表
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await service.generate_strategy_advice("A", "medium")
        assert result["market"] == "A"
        assert result["risk_level"] == "medium"
        assert "advice" in result
        assert "suggestions" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_chat(self):
        """测试多轮对话"""
        service, mock_llm, mock_db = self._create_mock_ai_service()

        mock_llm.chat = AsyncMock(return_value="这是AI的回复")

        result = await service.chat("session-001", "你好", user_id=1)
        assert result["session_id"] == "session-001"
        assert result["message"] == "你好"
        assert result["response"] == "这是AI的回复"
        assert result["history_length"] == 2  # user + assistant

        # 第二轮对话，验证上下文
        result2 = await service.chat("session-001", "继续聊", user_id=1)
        assert result2["history_length"] == 4  # 累计 2 轮
        assert mock_llm.chat.call_count == 2


# ============================================================================
# 6. TestTenantService — 租户管理测试
# ============================================================================

class TestTenantService:
    """租户管理服务单元测试"""

    def test_create_tenant(self):
        """测试创建租户"""
        mock_db = MagicMock()
        mock_data = MagicMock()
        mock_data.name = "测试租户"
        mock_data.status = "active"
        mock_data.contact_email = "test@example.com"
        mock_data.phone = None
        mock_data.domain = None
        mock_data.logo_url = None
        mock_data.features = ["basic_signals"]
        mock_data.max_users = 10
        mock_data.max_strategies = 20
        mock_data.max_api_calls = 50000
        mock_data.whitelabel_config = None

        # Mock 数据库查询返回 None（租户ID不冲突）
        mock_db.query.return_value.filter.return_value.first.return_value = None

        tenant = TenantService.create_tenant(mock_db, mock_data)

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    def test_get_tenant(self):
        """测试获取租户"""
        mock_db = MagicMock()
        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t_abc12345"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant

        result = TenantService.get_tenant(mock_db, "t_abc12345")
        assert result is not None
        assert result.tenant_id == "t_abc12345"

    def test_update_tenant(self):
        """测试更新租户"""
        mock_db = MagicMock()
        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t_abc12345"
        mock_tenant.name = "旧名称"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant

        mock_data = MagicMock()
        mock_data.model_dump.return_value = {"name": "新名称"}

        result = TenantService.update_tenant(mock_db, "t_abc12345", mock_data)
        assert result is not None
        assert mock_db.commit.called

    def test_check_tenant_limit(self):
        """测试配额检查"""
        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t_abc12345"
        mock_tenant.max_users = 10
        mock_tenant.max_strategies = 20
        mock_tenant.max_api_calls = 50000

        # Mock SessionLocal 和数据库查询
        with patch("app.tenant_service.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            mock_session.query.return_value.filter.return_value.scalar.return_value = 5

            result = TenantService.check_tenant_limit(mock_tenant, "users")
            assert result is True

    def test_get_usage_stats(self):
        """测试用量统计"""
        mock_db = MagicMock()

        # Mock Tenant 查询
        mock_tenant = MagicMock()
        mock_tenant.max_users = 10
        mock_tenant.max_strategies = 20
        mock_tenant.max_api_calls = 50000
        mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant

        # Mock Usage 查询
        mock_usage_1 = MagicMock()
        mock_usage_1.metric = "api_calls"
        mock_usage_1.value = 1500
        mock_usage_1.period_start = datetime(2026, 4, 1)
        mock_usage_1.period_end = datetime(2026, 5, 1)
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_usage_1]

        result = TenantService.get_usage_stats(mock_db, "t_abc12345", "month")
        assert result["tenant_id"] == "t_abc12345"
        assert result["period"] == "month"
        assert "usage" in result
        assert "limits" in result


# ============================================================================
# 7. TestPluginManager — 插件管理测试
# ============================================================================

class TestPluginManager:
    """插件管理器单元测试"""

    def setup_method(self):
        # 重置单例以确保测试隔离
        PluginManager._instance = None
        self.manager = PluginManager()

    def test_register_plugin(self):
        """测试注册插件"""
        plugin_info = {
            "name": "测试插件",
            "description": "这是一个测试插件",
            "version": "1.0.0",
            "category": "signal",
            "hooks": ["before_signal", "after_signal"],
        }
        result = self.manager.register_plugin(plugin_info)
        assert result["name"] == "测试插件"
        assert result["version"] == "1.0.0"
        assert result["category"] == "signal"
        assert "plugin_id" in result
        assert result["status"] == "active"

        # 验证钩子注册
        assert result["plugin_id"] in self.manager.get_hooks_for_event("before_signal")
        assert result["plugin_id"] in self.manager.get_hooks_for_event("after_signal")

    def test_list_plugins(self):
        """测试列出插件"""
        self.manager.register_plugin({
            "name": "插件A", "category": "signal", "status": "active",
        })
        self.manager.register_plugin({
            "name": "插件B", "category": "risk_control", "status": "active",
        })
        self.manager.register_plugin({
            "name": "插件C", "category": "signal", "status": "inactive",
        })

        # 列出全部
        all_plugins = self.manager.list_plugins()
        assert len(all_plugins) == 3

        # 按分类筛选
        signal_plugins = self.manager.list_plugins(category="signal")
        assert len(signal_plugins) == 2

        # 按状态筛选
        active_plugins = self.manager.list_plugins(status="active")
        assert len(active_plugins) == 2

    def test_install_plugin(self):
        """测试安装插件"""
        plugin_info = {
            "name": "可安装插件",
            "hooks": ["before_signal"],
        }
        plugin = self.manager.register_plugin(plugin_info)
        plugin_id = plugin["plugin_id"]

        # Mock 数据库 — install_plugin 内部使用 SessionLocal() 获取 session
        with patch("app.plugin_system.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            # 第一次调用 first() 检查是否已安装（返回 None 表示未安装）
            # 第二次调用 first() 不存在（因为代码路径中只有一次查询）
            mock_session.query.return_value.filter.return_value.first.return_value = None

            result = self.manager.install_plugin("t_test", plugin_id)
            assert result["status"] in ("installed", "reinstalled")
            assert result["plugin_id"] == plugin_id

    def test_execute_plugin(self):
        """测试执行插件"""
        plugin_info = {
            "name": "可执行插件",
            "status": "active",
        }
        plugin = self.manager.register_plugin(plugin_info)
        plugin_id = plugin["plugin_id"]

        result = self.manager.execute_plugin(
            plugin_id=plugin_id,
            method="run",
            params={"param1": "value1"},
        )
        assert result["success"] is True
        assert result["plugin_id"] == plugin_id
        assert result["method"] == "run"

        # 测试不存在的插件
        result_fail = self.manager.execute_plugin(
            plugin_id="nonexistent",
            method="run",
        )
        assert result_fail["success"] is False
        assert "error" in result_fail


# ============================================================================
# 8. TestAPIKeyService — API Key 管理测试
# ============================================================================

class TestAPIKeyService:
    """API Key 管理服务单元测试"""

    def test_create_api_key(self):
        """测试创建 API Key"""
        mock_db = MagicMock()
        mock_data = MagicMock()
        mock_data.name = "测试Key"
        mock_data.permissions = ["read", "write"]
        mock_data.rate_limit = 60
        mock_data.expires_at = None

        # Mock 查询返回 None（名称不重复）
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = APIKeyService.create_api_key(mock_db, "t_test", 1, mock_data)

        assert "api_key" in result
        assert "api_secret" in result
        assert result["api_key"].startswith(API_KEY_PREFIX)
        assert result["name"] == "测试Key"
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_validate_api_key(self):
        """测试验证 API Key"""
        mock_db = MagicMock()
        mock_key_record = MagicMock()
        mock_key_record.api_key = "oc_abc123"
        mock_key_record.status = "active"
        mock_key_record.expires_at = None

        mock_db.query.return_value.filter.return_value.first.return_value = mock_key_record

        result = APIKeyService.validate_api_key(mock_db, "oc_abc123")
        assert result is not None
        assert result.api_key == "oc_abc123"

    def test_revoke_api_key(self):
        """测试吊销 API Key"""
        mock_db = MagicMock()
        mock_key_record = MagicMock()
        mock_key_record.api_key = "oc_abc123"
        mock_key_record.status = "active"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_key_record

        result = APIKeyService.revoke_api_key(mock_db, 1)
        assert result is True
        assert mock_key_record.status == "revoked"
        assert mock_db.commit.called

    def test_generate_api_key_format(self):
        """测试 API Key 格式（oc_ 前缀）"""
        key1 = APIKeyService._generate_api_key()
        key2 = APIKeyService._generate_api_key()

        # 验证格式
        assert key1.startswith(API_KEY_PREFIX)
        assert key2.startswith(API_KEY_PREFIX)
        assert key1 != key2  # 每次生成应不同

        # 验证长度：oc_ (3) + 32 hex chars = 35
        assert len(key1) == 35

        # 验证 secret 格式
        secret = APIKeyService._generate_api_secret()
        assert len(secret) == 40  # 20 bytes = 40 hex chars


# ============================================================================
# 9. TestBillingService — 计费服务测试
# ============================================================================

class TestBillingService:
    """计费服务单元测试"""

    def test_init_default_plans(self):
        """测试默认计划初始化"""
        mock_db = MagicMock()

        # Mock 查询返回 None（计划不存在）
        mock_db.query.return_value.filter.return_value.first.return_value = None

        BillingService.init_default_plans(mock_db)

        # 应该添加 4 个默认计划
        assert mock_db.add.call_count == len(DEFAULT_PLANS)
        assert mock_db.commit.called

    def test_subscribe(self):
        """测试订阅"""
        mock_db = MagicMock()

        # Mock 计划查询
        mock_plan = MagicMock()
        mock_plan.plan_id = "basic"
        mock_plan.trial_days = 7
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_plan,  # 计划存在
            None,       # 无已有订阅
        ]

        result = BillingService.subscribe(mock_db, "t_test", "basic", "monthly")
        assert result.status == "active"
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_check_subscription(self):
        """测试订阅检查"""
        mock_db = MagicMock()

        # Mock 订阅查询
        mock_subscription = MagicMock()
        mock_subscription.plan_id = "pro"
        mock_subscription.billing_cycle = "monthly"
        mock_subscription.status = "active"
        mock_subscription.current_period_start = datetime(2026, 3, 1)
        mock_subscription.current_period_end = datetime(2026, 5, 1)
        mock_subscription.trial_end = datetime(2026, 4, 15)

        # Mock 计划查询
        mock_plan = MagicMock()
        mock_plan.plan_id = "pro"
        mock_plan.name = "Pro"
        mock_plan.price = 299

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            mock_subscription,
        ]
        # 第二个查询（查 plan）不经过 order_by，直接 filter().first()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_plan

        result = BillingService.check_subscription(mock_db, "t_test")
        assert result["tenant_id"] == "t_test"
        assert result["status"] == "active"
        assert result["plan"]["plan_id"] == "pro"
        assert result["trial"] is True

    def test_process_usage(self):
        """测试用量处理"""
        mock_db = MagicMock()

        # Mock 订阅查询
        mock_subscription = MagicMock()
        mock_subscription.plan_id = "basic"

        # Mock 计划查询
        mock_plan = MagicMock()
        mock_plan.max_api_calls = 10000
        mock_plan.max_strategies = 10
        mock_plan.max_users = 5

        # 每次 process_usage 调用会触发两次 .first()（查 subscription + 查 plan）
        # 两次调用共需要 4 个返回值
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_subscription,  # 第1次调用：查 subscription
            mock_plan,          # 第1次调用：查 plan
            mock_subscription,  # 第2次调用：查 subscription
            mock_plan,          # 第2次调用：查 plan
        ]

        # 未超限
        result = BillingService.process_usage(mock_db, "t_test", "api_calls", 5000)
        assert result["allowed"] is True
        assert result["current"] == 5000
        assert result["limit"] == 10000

        # 超限
        result_over = BillingService.process_usage(mock_db, "t_test", "api_calls", 15000)
        assert result_over["allowed"] is False


# ============================================================================
# 10. TestAPIEndpoints — API 端点测试
# ============================================================================

class TestAPIEndpoints:
    """API 端点集成测试（使用 FastAPI TestClient）"""

    def _create_test_client(self):
        """创建测试用 FastAPI 客户端"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        # Mock 依赖注入
        def override_get_db():
            db = MagicMock()
            yield db

        def override_get_current_user():
            return {"id": 1, "username": "testuser", "role": "admin"}

        def override_require_admin():
            return {"id": 1, "username": "admin", "role": "admin"}

        def override_get_current_tenant():
            tenant = MagicMock()
            tenant.tenant_id = "t_test123"
            return tenant

        # 导入并注册路由
        from app.ai_api import router as ai_router
        from app.tenant_api import router as tenant_router
        from app.plugin_api import router as plugin_router
        from app.billing_api import router as billing_router
        from app.auth import get_current_user, require_role
        from app.database import get_db
        from app.tenant_middleware import get_current_tenant

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_role] = override_require_admin
        app.dependency_overrides[get_current_tenant] = override_get_current_tenant

        app.include_router(ai_router)
        app.include_router(tenant_router)
        app.include_router(plugin_router)
        app.include_router(billing_router)

        return TestClient(app)

    def test_ai_chat_endpoint(self):
        """测试 AI 对话端点"""
        client = self._create_test_client()

        with patch("app.ai_api._create_ai_service") as mock_create:
            mock_service = AsyncMock()
            mock_service.chat = AsyncMock(return_value={
                "session_id": "test-session",
                "response": "AI回复内容",
                "timestamp": "2026-04-01T00:00:00",
            })
            mock_create.return_value = mock_service

            response = client.post("/api/v1/ai/chat", json={
                "message": "你好",
            })

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "response" in data

    def test_ai_sentiment_endpoint(self):
        """测试情绪分析端点"""
        client = self._create_test_client()

        with patch("app.ai_api._create_ai_service") as mock_create:
            mock_service = AsyncMock()
            mock_service.analyze_market_sentiment = AsyncMock(return_value={
                "market": "A",
                "sentiment": "positive",
                "score": 0.5,
                "confidence": 0.8,
                "keyword_analysis": {"news_count": 10, "distribution": {}, "hot_topics": []},
                "summary": "A股市场情绪积极",
                "llm_analysis": "LLM分析结果",
            })
            mock_create.return_value = mock_service

            response = client.post("/api/v1/ai/sentiment", json={
                "market": "A",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["market"] == "A"

    def test_ai_anomaly_endpoint(self):
        """测试异常检测端点"""
        client = self._create_test_client()

        with patch("app.ai_api._create_ai_service") as mock_create:
            mock_service = AsyncMock()
            mock_service.detect_anomalies = AsyncMock(return_value={
                "symbol": "600519",
                "market": "A",
                "days": 30,
                "price_anomalies": [],
                "volume_anomalies": [],
                "pump_dump_events": [],
                "report": {
                    "anomalies": [],
                    "summary": "未检测到异常",
                    "risk_level": "minimal",
                    "total_anomalies": 0,
                    "by_severity": {},
                    "by_type": {},
                },
            })
            mock_create.return_value = mock_service

            response = client.post("/api/v1/ai/anomaly/detect", json={
                "symbol": "600519",
                "market": "A",
                "days": 30,
            })

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "600519"

    def test_tenant_crud(self):
        """测试租户 CRUD"""
        client = self._create_test_client()

        with patch.object(TenantService, "create_tenant") as mock_create:
            mock_tenant = MagicMock()
            mock_tenant.tenant_id = "t_new1234"
            mock_tenant.name = "新租户"
            mock_tenant.status = "active"
            mock_tenant.created_at = datetime(2026, 4, 1)
            mock_create.return_value = mock_tenant

            response = client.post("/api/v1/tenant", json={
                "name": "新租户",
                "contact_email": "new@example.com",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["tenant_id"] == "t_new1234"
            assert data["name"] == "新租户"

        with patch.object(TenantService, "list_tenants") as mock_list:
            mock_list.return_value = {
                "total": 0,
                "page": 1,
                "page_size": 20,
                "data": [],
            }
            response = client.get("/api/v1/tenant")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0

    def test_plugin_list(self):
        """测试插件列表"""
        client = self._create_test_client()

        # 重置单例
        PluginManager._instance = None

        with patch.object(PluginManager, "get_instance") as mock_get:
            mock_manager = MagicMock()
            mock_manager.list_plugins.return_value = [
                {
                    "plugin_id": "p_test_001",
                    "name": "测试插件",
                    "description": "测试用",
                    "version": "1.0.0",
                    "category": "signal",
                    "author": "tester",
                    "hooks": ["before_signal"],
                    "status": "active",
                    "rating_avg": 4.5,
                    "rating_count": 10,
                    "install_count": 100,
                }
            ]
            mock_get.return_value = mock_manager

            response = client.get("/api/v1/plugins")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["data"]) == 1
            assert data["data"][0]["name"] == "测试插件"

    def test_billing_plans(self):
        """测试计费计划列表"""
        client = self._create_test_client()

        with patch.object(BillingService, "list_plans") as mock_list:
            mock_plan = MagicMock()
            mock_plan.plan_id = "free"
            mock_plan.name = "Free"
            mock_plan.description = "免费体验版"
            mock_plan.price = 0
            mock_plan.billing_cycle = "monthly"
            mock_plan.max_users = 1
            mock_plan.max_strategies = 3
            mock_plan.max_api_calls = 1000
            mock_plan.max_api_calls_per_minute = 10
            mock_plan.features = '["basic_signals", "market_data"]'
            mock_plan.trial_days = 0
            mock_list.return_value = [mock_plan]

            response = client.get("/api/v1/billing/plans")
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert len(data["data"]) == 1
            assert data["data"][0]["plan_id"] == "free"
            assert data["data"][0]["price"] == 0
