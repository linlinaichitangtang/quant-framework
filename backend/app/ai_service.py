"""
AI 分析服务 — 整合所有 AI 能力的核心服务

提供以下能力：
- 市场情绪分析
- 异常交易检测
- 策略归因分析
- 自然语言查询
- AI 策略建议
- 多轮对话
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .llm_client import LLMClient, LLMError
from .anomaly_detector import AnomalyDetector
from .sentiment_analyzer import SentimentAnalyzer
from .strategy_attribution import StrategyAttributor

logger = logging.getLogger(__name__)


class AIService:
    """
    AI 分析服务 — 整合 LLM、异常检测、情绪分析、归因分析等能力

    作为 V1.5 智能分析助手的后端核心，统一对外提供 AI 分析接口。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        db_session: Session,
    ):
        """
        初始化 AI 分析服务

        Args:
            llm_client: LLM 客户端实例
            db_session: SQLAlchemy 数据库会话
        """
        self.llm = llm_client
        self.db = db_session

        # 初始化子模块
        self.anomaly_detector = AnomalyDetector()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.strategy_attributor = StrategyAttributor()

        # 对话历史存储（内存字典，session_id -> messages）
        self._chat_sessions: Dict[str, List[Dict[str, str]]] = {}

        # 系统提示词
        self._system_prompt = (
            "你是一个专业的量化交易 AI 助手，擅长市场分析、策略评估和投资建议。"
            "请基于提供的数据给出专业、客观的分析。"
            "回答时请使用中文，结构清晰，包含关键数据和结论。"
            "如果数据不足，请明确指出。"
            "注意：你的分析仅供参考，不构成投资建议。"
        )

        logger.info("AI 分析服务初始化完成")

    # ==================== 市场情绪分析 ====================

    async def analyze_market_sentiment(self, market: str) -> Dict[str, Any]:
        """
        市场情绪分析 — 结合数据统计和 LLM 分析

        流程：
        1. 从数据库获取近期新闻/公告数据
        2. 使用 SentimentAnalyzer 进行关键词情绪分析
        3. 构建 prompt，调用 LLM 进行深度分析
        4. 整合结果返回

        Args:
            market: 市场标识（A / HK / US）

        Returns:
            {
                "market": str,
                "sentiment": str,
                "score": float,
                "confidence": float,
                "keyword_analysis": dict,     # 关键词分析结果
                "llm_analysis": str,          # LLM 深度分析
                "summary": str,
                "timestamp": str,
            }
        """
        logger.info(f"开始市场情绪分析: market={market}")

        try:
            # 1. 尝试从数据库获取新闻数据
            news = self._fetch_recent_news(market, days=7)

            # 2. 关键词情绪分析
            if news:
                sentiment_result = self.sentiment_analyzer.calculate_market_sentiment(
                    market=market,
                    news=news,
                )
            else:
                # 无新闻数据时，使用模拟数据
                logger.warning(f"未获取到 {market} 市场新闻数据，使用模拟数据")
                sentiment_result = self._generate_mock_sentiment(market)

            # 3. 构建 LLM 分析 prompt
            prompt = self._build_sentiment_prompt(market, sentiment_result)

            # 4. 调用 LLM 深度分析
            llm_analysis = ""
            try:
                llm_analysis = await self.llm.chat_with_system(
                    system_prompt=self._system_prompt,
                    user_message=prompt,
                    temperature=0.5,
                    max_tokens=1500,
                )
            except LLMError as e:
                logger.error(f"LLM 情绪分析调用失败: {e}")
                llm_analysis = f"LLM 分析暂不可用（{e.message}），请参考关键词分析结果。"

            result = {
                "market": market,
                "sentiment": sentiment_result.get("sentiment", "neutral"),
                "score": sentiment_result.get("score", 0),
                "confidence": sentiment_result.get("confidence", 0),
                "keyword_analysis": {
                    "distribution": sentiment_result.get("distribution", {}),
                    "hot_topics": sentiment_result.get("hot_topics", []),
                    "news_count": sentiment_result.get("news_analysis", {}).get("total", 0),
                },
                "llm_analysis": llm_analysis,
                "summary": sentiment_result.get("summary", ""),
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"市场情绪分析完成: market={market}, "
                f"sentiment={result['sentiment']}, score={result['score']:.4f}"
            )
            return result

        except Exception as e:
            logger.error(f"市场情绪分析失败: market={market}, error={e}", exc_info=True)
            return {
                "market": market,
                "sentiment": "neutral",
                "score": 0,
                "confidence": 0,
                "keyword_analysis": {},
                "llm_analysis": f"分析失败：{str(e)}",
                "summary": f"市场情绪分析失败：{str(e)}",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    # ==================== 异常交易检测 ====================

    async def detect_anomalies(
        self,
        symbol: str,
        market: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        异常交易检测 — 基于统计方法检测异常，结合 LLM 解释

        流程：
        1. 从数据库获取近期行情数据
        2. 使用 AnomalyDetector 进行统计检测
        3. 构建 prompt，调用 LLM 解释异常原因
        4. 生成综合报告

        Args:
            symbol: 标的代码
            market: 市场标识
            days: 分析天数

        Returns:
            异常检测综合报告
        """
        logger.info(f"开始异常检测: symbol={symbol}, market={market}, days={days}")

        try:
            # 1. 获取行情数据
            price_data = self._fetch_price_data(symbol, market, days)

            if not price_data:
                logger.warning(f"未获取到 {symbol} 行情数据，使用模拟数据")
                price_data = self._generate_mock_price_data(days)

            prices = [d["close"] for d in price_data]
            volumes = [d["volume"] for d in price_data]

            # 2. 统计异常检测
            price_anomalies = self.anomaly_detector.detect_price_anomaly(prices)
            volume_anomalies = self.anomaly_detector.detect_volume_anomaly(volumes)
            pump_dump = self.anomaly_detector.detect_pump_dump(prices, volumes)

            all_anomalies = price_anomalies + volume_anomalies + pump_dump

            # 3. 生成异常报告
            report = self.anomaly_detector.generate_anomaly_report(symbol, all_anomalies)

            # 4. 调用 LLM 解释异常
            llm_explanation = ""
            if all_anomalies:
                prompt = self._build_anomaly_prompt(symbol, market, report)
                try:
                    llm_explanation = await self.llm.chat_with_system(
                        system_prompt=self._system_prompt,
                        user_message=prompt,
                        temperature=0.3,
                        max_tokens=1500,
                    )
                except LLMError as e:
                    logger.error(f"LLM 异常解释调用失败: {e}")
                    llm_explanation = f"LLM 解释暂不可用（{e.message}）。"

            result = {
                "symbol": symbol,
                "market": market,
                "days": days,
                "price_anomalies": price_anomalies,
                "volume_anomalies": volume_anomalies,
                "pump_dump_events": pump_dump,
                "report": report,
                "llm_explanation": llm_explanation,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"异常检测完成: symbol={symbol}, "
                f"total_anomalies={report['total_anomalies']}, "
                f"risk_level={report['risk_level']}"
            )
            return result

        except Exception as e:
            logger.error(f"异常检测失败: symbol={symbol}, error={e}", exc_info=True)
            return {
                "symbol": symbol,
                "market": market,
                "days": days,
                "price_anomalies": [],
                "volume_anomalies": [],
                "pump_dump_events": [],
                "report": {
                    "symbol": symbol,
                    "total_anomalies": 0,
                    "by_severity": {},
                    "by_type": {},
                    "risk_level": "unknown",
                    "summary": f"异常检测失败：{str(e)}",
                    "anomalies": [],
                },
                "llm_explanation": "",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    # ==================== 策略归因分析 ====================

    async def analyze_strategy_attribution(self, strategy_id: str) -> Dict[str, Any]:
        """
        策略归因分析 — 分析回测结果，分解收益来源

        流程：
        1. 从数据库获取回测结果和交易记录
        2. 使用 StrategyAttributor 进行归因分析
        3. 调用 LLM 生成归因解读和建议

        Args:
            strategy_id: 策略/回测 ID

        Returns:
            归因分析报告
        """
        logger.info(f"开始策略归因分析: strategy_id={strategy_id}")

        try:
            # 1. 获取回测数据
            backtest_result, trades = self._fetch_backtest_data(strategy_id)

            if not backtest_result:
                logger.warning(f"未找到策略 {strategy_id} 的回测数据")
                return {
                    "strategy_id": strategy_id,
                    "status": "not_found",
                    "message": f"未找到策略 {strategy_id} 的回测数据",
                    "timestamp": datetime.now().isoformat(),
                }

            # 2. 归因分析
            attribution = self.strategy_attributor.analyze(backtest_result, trades)

            # 3. 调用 LLM 生成解读
            llm_interpretation = ""
            try:
                prompt = self._build_attribution_prompt(strategy_id, attribution)
                llm_interpretation = await self.llm.chat_with_system(
                    system_prompt=self._system_prompt,
                    user_message=prompt,
                    temperature=0.5,
                    max_tokens=2000,
                )
            except LLMError as e:
                logger.error(f"LLM 归因解读调用失败: {e}")
                llm_interpretation = f"LLM 解读暂不可用（{e.message}）。"

            result = {
                "strategy_id": strategy_id,
                "attribution": attribution,
                "llm_interpretation": llm_interpretation,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"策略归因分析完成: strategy_id={strategy_id}, "
                f"rating={attribution.get('overall_rating', 'unknown')}"
            )
            return result

        except Exception as e:
            logger.error(f"策略归因分析失败: strategy_id={strategy_id}, error={e}", exc_info=True)
            return {
                "strategy_id": strategy_id,
                "status": "error",
                "message": f"归因分析失败：{str(e)}",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    # ==================== 自然语言查询 ====================

    async def natural_language_query(
        self,
        query: str,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        自然语言查询 — 解析用户意图，转化为数据查询或 API 调用

        支持的查询类型：
        - 行情查询："茅台最近涨了多少"
        - 持仓查询："我现在的持仓情况"
        - 策略查询："我的策略表现怎么样"
        - 市场分析："A股今天行情如何"
        - 回测查询："最近一次回测结果"

        Args:
            query: 用户自然语言查询
            user_id: 用户 ID

        Returns:
            {
                "query": str,
                "intent": str,
                "response": str,
                "data": dict,
                "timestamp": str,
            }
        """
        logger.info(f"自然语言查询: user_id={user_id}, query={query[:50]}")

        try:
            # 1. 意图识别（通过 LLM）
            intent_result = await self._recognize_intent(query)

            intent = intent_result.get("intent", "general")
            entities = intent_result.get("entities", {})

            # 2. 根据意图执行对应操作
            data: Dict[str, Any] = {}
            response = ""

            if intent == "market_overview":
                data = await self._handle_market_overview(entities)
            elif intent == "stock_query":
                data = await self._handle_stock_query(entities)
            elif intent == "portfolio_query":
                data = self._handle_portfolio_query(user_id)
            elif intent == "strategy_query":
                data = self._handle_strategy_query(user_id)
            elif intent == "backtest_query":
                data = self._handle_backtest_query(user_id)
            elif intent == "sentiment_query":
                market = entities.get("market", "A")
                data = await self.analyze_market_sentiment(market)
            else:
                # 通用问答，直接调用 LLM
                response = await self.llm.chat_with_system(
                    system_prompt=self._system_prompt,
                    user_message=query,
                    temperature=0.7,
                    max_tokens=1500,
                )

            # 3. 如果有数据但没有 LLM 回复，生成自然语言回复
            if data and not response:
                response = await self._generate_natural_response(query, data)

            result = {
                "query": query,
                "intent": intent,
                "entities": entities,
                "response": response,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"自然语言查询完成: intent={intent}")
            return result

        except Exception as e:
            logger.error(f"自然语言查询失败: query={query[:50]}, error={e}", exc_info=True)
            return {
                "query": query,
                "intent": "error",
                "entities": {},
                "response": f"查询处理失败：{str(e)}",
                "data": {},
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    # ==================== AI 策略建议 ====================

    async def generate_strategy_advice(
        self,
        market: str,
        risk_level: str = "medium",
    ) -> Dict[str, Any]:
        """
        AI 策略建议 — 基于市场状态和用户风险偏好生成策略建议

        Args:
            market: 市场标识（A / HK / US）
            risk_level: 风险偏好（low / medium / high）

        Returns:
            {
                "market": str,
                "risk_level": str,
                "advice": str,           # LLM 生成的策略建议
                "sentiment_context": dict,
                "suggestions": list,     # 结构化建议列表
                "timestamp": str,
            }
        """
        logger.info(f"生成策略建议: market={market}, risk_level={risk_level}")

        try:
            # 1. 获取市场情绪作为上下文
            sentiment = await self.analyze_market_sentiment(market)

            # 2. 获取市场概览数据
            market_data = await self._handle_market_overview({"market": market})

            # 3. 构建 prompt
            prompt = self._build_strategy_advice_prompt(
                market=market,
                risk_level=risk_level,
                sentiment=sentiment,
                market_data=market_data,
            )

            # 4. 调用 LLM 生成建议
            advice = await self.llm.chat_with_system(
                system_prompt=self._system_prompt,
                user_message=prompt,
                temperature=0.6,
                max_tokens=2000,
            )

            # 5. 生成结构化建议
            suggestions = self._extract_suggestions(advice)

            result = {
                "market": market,
                "risk_level": risk_level,
                "advice": advice,
                "sentiment_context": {
                    "sentiment": sentiment.get("sentiment", "neutral"),
                    "score": sentiment.get("score", 0),
                },
                "market_context": {
                    "trend": market_data.get("trend", "unknown"),
                },
                "suggestions": suggestions,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"策略建议生成完成: market={market}, risk_level={risk_level}")
            return result

        except Exception as e:
            logger.error(f"策略建议生成失败: market={market}, error={e}", exc_info=True)
            return {
                "market": market,
                "risk_level": risk_level,
                "advice": f"策略建议生成失败：{str(e)}",
                "sentiment_context": {},
                "market_context": {},
                "suggestions": [],
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    # ==================== 多轮对话 ====================

    async def chat(
        self,
        session_id: str,
        message: str,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        多轮对话 — 支持上下文连续对话

        对话历史存储在内存字典中（session_id -> messages）。

        Args:
            session_id: 会话 ID
            message: 用户消息
            user_id: 用户 ID

        Returns:
            {
                "session_id": str,
                "message": str,
                "response": str,
                "history_length": int,
                "timestamp": str,
            }
        """
        logger.info(f"多轮对话: session_id={session_id}, user_id={user_id}")

        try:
            # 1. 获取或创建会话历史
            if session_id not in self._chat_sessions:
                self._chat_sessions[session_id] = [
                    {"role": "system", "content": self._system_prompt}
                ]
                logger.info(f"创建新对话会话: session_id={session_id}")

            history = self._chat_sessions[session_id]

            # 2. 添加用户消息
            history.append({"role": "user", "content": message})

            # 3. 限制历史长度（保留最近 20 条消息 + system prompt）
            max_history = 22  # 1 system + 21 messages
            if len(history) > max_history:
                system_msg = history[0]
                history = [system_msg] + history[-(max_history - 1):]
                self._chat_sessions[session_id] = history

            # 4. 调用 LLM
            response = await self.llm.chat(
                messages=history,
                temperature=0.7,
                max_tokens=2000,
            )

            # 5. 添加助手回复到历史
            history.append({"role": "assistant", "content": response})

            result = {
                "session_id": session_id,
                "message": message,
                "response": response,
                "history_length": len(history) - 1,  # 不计 system prompt
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"对话完成: session_id={session_id}, "
                f"history_length={result['history_length']}"
            )
            return result

        except LLMError as e:
            logger.error(f"对话 LLM 调用失败: session_id={session_id}, error={e}")
            return {
                "session_id": session_id,
                "message": message,
                "response": f"AI 助手暂时不可用：{e.message}",
                "history_length": 0,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"对话处理失败: session_id={session_id}, error={e}", exc_info=True)
            return {
                "session_id": session_id,
                "message": message,
                "response": f"对话处理失败：{str(e)}",
                "history_length": 0,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }

    # ==================== 数据获取辅助方法 ====================

    def _fetch_recent_news(self, market: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        从数据库获取近期新闻数据

        Args:
            market: 市场标识
            days: 获取天数

        Returns:
            新闻列表
        """
        try:
            from .models import NotificationHistory

            cutoff = datetime.now() - timedelta(days=days)
            query = (
                self.db.query(NotificationHistory)
                .filter(NotificationHistory.created_at >= cutoff)
                .order_by(NotificationHistory.created_at.desc())
                .limit(50)
                .all()
            )

            news_list = []
            for item in query:
                news_list.append({
                    "title": item.title,
                    "content": item.content[:500] if item.content else "",
                    "source": "system",
                    "publish_time": item.created_at.isoformat() if item.created_at else "",
                })

            logger.info(f"获取到 {len(news_list)} 条新闻记录")
            return news_list

        except Exception as e:
            logger.error(f"获取新闻数据失败: {e}")
            return []

    def _fetch_price_data(
        self,
        symbol: str,
        market: str,
        days: int,
    ) -> List[Dict[str, Any]]:
        """
        从数据库获取行情数据

        Args:
            symbol: 标的代码
            market: 市场标识
            days: 获取天数

        Returns:
            行情数据列表
        """
        try:
            from .models import HistoricalBar, MarketType

            market_map = {
                "A": MarketType.A,
                "HK": MarketType.HK,
                "US": MarketType.US,
            }
            market_type = market_map.get(market.upper(), MarketType.A)

            cutoff = datetime.now() - timedelta(days=days)
            bars = (
                self.db.query(HistoricalBar)
                .filter(
                    HistoricalBar.symbol == symbol,
                    HistoricalBar.market == market_type,
                    HistoricalBar.timestamp >= cutoff,
                )
                .order_by(HistoricalBar.timestamp.asc())
                .all()
            )

            result = []
            for bar in bars:
                result.append({
                    "date": bar.timestamp.strftime("%Y-%m-%d") if bar.timestamp else "",
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume or 0,
                })

            logger.info(f"获取到 {len(result)} 条行情数据: {symbol}")
            return result

        except Exception as e:
            logger.error(f"获取行情数据失败: symbol={symbol}, error={e}")
            return []

    def _fetch_backtest_data(
        self,
        strategy_id: str,
    ) -> tuple:
        """
        从数据库获取回测结果和交易记录

        Args:
            strategy_id: 策略/回测 ID

        Returns:
            (backtest_result_dict, trades_list) 元组
        """
        try:
            from .models import BacktestResult, BacktestTrade

            # 查询回测结果（支持数字 ID 或策略名称）
            try:
                backtest_id = int(strategy_id)
                result = self.db.query(BacktestResult).filter(
                    BacktestResult.id == backtest_id
                ).first()
            except (ValueError, TypeError):
                result = self.db.query(BacktestResult).filter(
                    BacktestResult.name == strategy_id
                ).first()

            if not result:
                return None, []

            # 获取交易记录
            trades = (
                self.db.query(BacktestTrade)
                .filter(BacktestTrade.backtest_id == result.id)
                .order_by(BacktestTrade.date.asc())
                .all()
            )

            # 转换为字典
            backtest_dict = {
                "total_return": result.total_return or 0,
                "annual_return": result.annual_return or 0,
                "max_drawdown": result.max_drawdown or 0,
                "sharpe_ratio": result.sharpe_ratio or 0,
                "win_rate": result.win_rate or 0,
                "n_trades": result.n_trades or 0,
                "initial_capital": result.initial_capital or 1_000_000,
                "final_value": result.final_value or 0,
                "name": result.name,
                "strategy_type": result.strategy_type,
            }

            trades_list = []
            for t in trades:
                trades_list.append({
                    "action": t.action,
                    "code": t.code,
                    "price": t.price,
                    "shares": t.shares,
                    "pnl": t.pnl or 0,
                    "pnl_pct": t.pnl_pct or 0,
                    "date": t.date,
                    "commission": t.commission or 0,
                })

            logger.info(
                f"获取回测数据: id={result.id}, name={result.name}, "
                f"trades={len(trades_list)}"
            )
            return backtest_dict, trades_list

        except Exception as e:
            logger.error(f"获取回测数据失败: strategy_id={strategy_id}, error={e}")
            return None, []

    # ==================== Prompt 构建方法 ====================

    def _build_sentiment_prompt(
        self,
        market: str,
        sentiment_result: Dict[str, Any],
    ) -> str:
        """构建市场情绪分析的 LLM prompt"""
        market_names = {"A": "A股", "HK": "港股", "US": "美股"}
        market_display = market_names.get(market, market)

        distribution = sentiment_result.get("distribution", {})
        hot_topics = sentiment_result.get("hot_topics", [])

        prompt = (
            f"请对{market_display}市场进行情绪分析。\n\n"
            f"## 关键词分析结果\n"
            f"- 综合情绪：{sentiment_result.get('sentiment', 'neutral')}\n"
            f"- 情绪得分：{sentiment_result.get('score', 0):.2f}\n"
            f"- 正面新闻：{distribution.get('positive', 0)} 条\n"
            f"- 负面新闻：{distribution.get('negative', 0)} 条\n"
            f"- 中性新闻：{distribution.get('neutral', 0)} 条\n"
        )

        if hot_topics:
            topics_str = "、".join(
                f"{t['keyword']}({t['count']}次)" for t in hot_topics[:8]
            )
            prompt += f"- 热门关键词：{topics_str}\n"

        prompt += (
            f"\n请基于以上数据，分析{market_display}市场的整体情绪，"
            f"并给出短期（1周）和中期（1个月）的市场展望。"
            f"请用结构化的方式回答，包含：\n"
            f"1. 当前市场情绪总结\n"
            f"2. 主要驱动因素\n"
            f"3. 短期展望\n"
            f"4. 中期展望\n"
            f"5. 需要关注的风险点"
        )
        return prompt

    def _build_anomaly_prompt(
        self,
        symbol: str,
        market: str,
        report: Dict[str, Any],
    ) -> str:
        """构建异常检测的 LLM prompt"""
        prompt = (
            f"请分析 {symbol}（{market}市场）的异常交易情况。\n\n"
            f"## 异常检测报告\n"
            f"- 异常总数：{report['total_anomalies']}\n"
            f"- 风险等级：{report['risk_level']}\n"
            f"- 按严重程度：高风险 {report['by_severity'].get('high', 0)} 个，"
            f"中风险 {report['by_severity'].get('medium', 0)} 个，"
            f"低风险 {report['by_severity'].get('low', 0)} 个\n"
        )

        if report["by_type"]:
            type_desc = "\n".join(
                f"  - {t}: {c} 次" for t, c in report["by_type"].items()
            )
            prompt += f"- 按类型：\n{type_desc}\n"

        # 包含关键异常详情
        high_anomalies = [a for a in report["anomalies"] if a.get("severity") == "high"]
        if high_anomalies:
            prompt += "\n## 高风险异常详情\n"
            for a in high_anomalies[:5]:
                prompt += f"- 类型：{a.get('type', 'unknown')}，"
                if "z_score" in a:
                    prompt += f"Z-score：{a['z_score']}，"
                if "pump_gain" in a:
                    prompt += f"涨幅：{a['pump_gain']:.2%}，"
                    prompt += f"成交量倍数：{a.get('volume_ratio', 0):.1f}x，"
                prompt += "\n"

        prompt += (
            "\n请分析这些异常的可能原因，评估其对投资者的风险，"
            "并给出操作建议。"
        )
        return prompt

    def _build_attribution_prompt(
        self,
        strategy_id: str,
        attribution: Dict[str, Any],
    ) -> str:
        """构建策略归因分析的 LLM prompt"""
        summary = attribution.get("backtest_summary", {})
        decomposition = attribution.get("return_decomposition", {})
        timing = attribution.get("timing_analysis", {})
        risk = attribution.get("risk_contribution", {})

        prompt = f"请对策略（ID: {strategy_id}）的归因分析结果进行解读。\n\n"

        prompt += "## 回测概要\n"
        prompt += f"- 总收益率：{summary.get('total_return', 0):.2%}\n"
        prompt += f"- 年化收益率：{summary.get('annual_return', 0):.2%}\n"
        prompt += f"- 最大回撤：{summary.get('max_drawdown', 0):.2%}\n"
        prompt += f"- 夏普比率：{summary.get('sharpe_ratio', 0):.2f}\n"
        prompt += f"- 胜率：{summary.get('win_rate', 0):.2%}\n"
        prompt += f"- 交易次数：{summary.get('n_trades', 0)}\n\n"

        if decomposition:
            prompt += "## 收益分解\n"
            prompt += f"- 选股 Alpha：{decomposition.get('alpha', 0):.2f} "
            prompt += f"（占比 {decomposition.get('alpha_pct', 0):.1%}）\n"
            prompt += f"- 择时收益：{decomposition.get('timing', 0):.2f} "
            prompt += f"（占比 {decomposition.get('timing_pct', 0):.1%}）\n"
            prompt += f"- 市场 Beta：{decomposition.get('beta', 0):.2f} "
            prompt += f"（占比 {decomposition.get('beta_pct', 0):.1%}）\n\n"

        if timing:
            prompt += "## 择时分析\n"
            prompt += f"- 择时评分：{timing.get('timing_score', 0):.1f}/100\n"
            prompt += f"- 盈亏比：{timing.get('profit_factor', 0):.2f}\n"
            prompt += f"- 最大连胜：{timing.get('win_streak_max', 0)} 次\n"
            prompt += f"- 最大连亏：{timing.get('loss_streak_max', 0)} 次\n\n"

        if risk:
            prompt += "## 风险分析\n"
            prompt += f"- 风险等级：{risk.get('risk_level', 'unknown')}\n"
            prompt += f"- 波动率：{risk.get('volatility', 0):.2%}\n"
            prompt += f"- Sortino 比率：{risk.get('sortino_ratio', 0):.2f}\n"
            prompt += f"- Calmar 比率：{risk.get('calmar_ratio', 0):.2f}\n\n"

        prompt += (
            "请基于以上归因数据，给出：\n"
            "1. 策略优势分析\n"
            "2. 策略劣势和风险\n"
            "3. 具体改进建议\n"
            "4. 适用场景和注意事项"
        )
        return prompt

    def _build_strategy_advice_prompt(
        self,
        market: str,
        risk_level: str,
        sentiment: Dict[str, Any],
        market_data: Dict[str, Any],
    ) -> str:
        """构建策略建议的 LLM prompt"""
        market_names = {"A": "A股", "HK": "港股", "US": "美股"}
        risk_names = {"low": "保守", "medium": "稳健", "high": "激进"}

        prompt = (
            f"请为{market_names.get(market, market)}市场生成投资策略建议。\n\n"
            f"## 投资者偏好\n"
            f"- 风险偏好：{risk_names.get(risk_level, risk_level)}\n\n"
            f"## 市场情绪\n"
            f"- 情绪倾向：{sentiment.get('sentiment', 'neutral')}\n"
            f"- 情绪得分：{sentiment.get('score', 0):.2f}\n\n"
        )

        prompt += (
            "请给出具体的策略建议，包括：\n"
            "1. 当前市场环境评估\n"
            "2. 推荐的策略类型（至少 2-3 种）\n"
            "3. 建议的仓位配置\n"
            "4. 风险控制措施\n"
            "5. 需要关注的关键指标或事件\n\n"
            "请确保建议与投资者的风险偏好相匹配。"
        )
        return prompt

    # ==================== 意图识别与处理 ====================

    async def _recognize_intent(self, query: str) -> Dict[str, Any]:
        """
        意图识别 — 通过 LLM 识别用户查询意图

        Args:
            query: 用户查询

        Returns:
            {"intent": str, "entities": dict}
        """
        intent_prompt = (
            '请识别以下用户查询的意图，并以 JSON 格式返回。\n\n'
            '支持的意图类型：\n'
            '- market_overview: 市场行情概览（如"今天A股怎么样"）\n'
            '- stock_query: 个股查询（如"茅台最近涨了多少"）\n'
            '- portfolio_query: 持仓查询（如"我现在的持仓"）\n'
            '- strategy_query: 策略查询（如"我的策略表现"）\n'
            '- backtest_query: 回测查询（如"最近回测结果"）\n'
            '- sentiment_query: 情绪查询（如"市场情绪如何"）\n'
            '- general: 通用问答\n\n'
            '请提取关键实体（如市场、股票代码、日期等）。\n\n'
            f'用户查询：{query}\n\n'
            '请返回 JSON 格式：{"intent": "...", "entities": {...}}'
        )

        try:
            response = await self.llm.chat_with_system(
                system_prompt="你是一个意图识别引擎，只返回 JSON 格式结果。",
                user_message=intent_prompt,
                temperature=0.1,
                max_tokens=200,
            )
            # 尝试解析 JSON
            # 清理可能的 markdown 代码块标记
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[-1]
                if response.endswith("```"):
                    response = response[:-3]

            result = json.loads(response)
            return {
                "intent": result.get("intent", "general"),
                "entities": result.get("entities", {}),
            }
        except (json.JSONDecodeError, LLMError, KeyError) as e:
            logger.warning(f"意图识别失败，使用默认: {e}")
            return {"intent": "general", "entities": {}}

    async def _handle_market_overview(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """处理市场概览查询"""
        market = entities.get("market", "A")
        market_names = {"A": "A股", "HK": "港股", "US": "美股"}

        # 尝试获取实际数据
        try:
            from .models import HistoricalBar, MarketType

            market_map = {"A": MarketType.A, "HK": MarketType.HK, "US": MarketType.US}
            market_type = market_map.get(market.upper(), MarketType.A)

            # 获取最近的数据
            cutoff = datetime.now() - timedelta(days=7)
            bars = (
                self.db.query(HistoricalBar)
                .filter(
                    HistoricalBar.market == market_type,
                    HistoricalBar.timestamp >= cutoff,
                )
                .order_by(HistoricalBar.timestamp.desc())
                .limit(10)
                .all()
            )

            if bars:
                return {
                    "market": market,
                    "market_display": market_names.get(market, market),
                    "trend": "data_available",
                    "recent_data_count": len(bars),
                    "data_available": True,
                }
        except Exception as e:
            logger.error(f"获取市场概览数据失败: {e}")

        return {
            "market": market,
            "market_display": market_names.get(market, market),
            "trend": "unknown",
            "data_available": False,
        }

    async def _handle_stock_query(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """处理个股查询"""
        symbol = entities.get("symbol", entities.get("stock_code", ""))
        if not symbol:
            return {"message": "未识别到具体股票代码，请提供股票名称或代码。"}

        # 尝试从数据库查询
        try:
            from .models import StockInfo

            stock = self.db.query(StockInfo).filter(
                StockInfo.symbol == symbol
            ).first()

            if stock:
                return {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market.value if stock.market else "unknown",
                    "industry": stock.industry,
                    "data_available": True,
                }
        except Exception as e:
            logger.error(f"查询股票信息失败: symbol={symbol}, error={e}")

        return {
            "symbol": symbol,
            "message": f"未找到 {symbol} 的详细信息。",
            "data_available": False,
        }

    def _handle_portfolio_query(self, user_id: int) -> Dict[str, Any]:
        """处理持仓查询"""
        try:
            from .models import Position

            positions = self.db.query(Position).all()
            position_list = []
            total_value = 0
            total_pnl = 0

            for pos in positions:
                mv = pos.market_value or 0
                pnl = pos.profit_amount or 0
                total_value += mv
                total_pnl += pnl
                position_list.append({
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                    "current_price": pos.current_price,
                    "market_value": mv,
                    "profit_pct": pos.profit_pct,
                    "profit_amount": pnl,
                })

            return {
                "total_positions": len(position_list),
                "total_value": round(total_value, 2),
                "total_pnl": round(total_pnl, 2),
                "positions": position_list,
                "data_available": True,
            }
        except Exception as e:
            logger.error(f"查询持仓失败: user_id={user_id}, error={e}")
            return {
                "total_positions": 0,
                "total_value": 0,
                "total_pnl": 0,
                "positions": [],
                "data_available": False,
            }

    def _handle_strategy_query(self, user_id: int) -> Dict[str, Any]:
        """处理策略查询"""
        try:
            from .models import StrategyConfig

            strategies = self.db.query(StrategyConfig).filter(
                StrategyConfig.enabled == True
            ).all()

            strategy_list = []
            for s in strategies:
                strategy_list.append({
                    "strategy_id": s.strategy_id,
                    "strategy_name": s.strategy_name,
                    "market": s.market.value if s.market else "unknown",
                    "max_position": s.max_position,
                    "stop_loss_pct": s.stop_loss_pct,
                    "take_profit_pct": s.take_profit_pct,
                })

            return {
                "total_strategies": len(strategy_list),
                "strategies": strategy_list,
                "data_available": True,
            }
        except Exception as e:
            logger.error(f"查询策略失败: user_id={user_id}, error={e}")
            return {
                "total_strategies": 0,
                "strategies": [],
                "data_available": False,
            }

    def _handle_backtest_query(self, user_id: int) -> Dict[str, Any]:
        """处理回测查询"""
        try:
            from .models import BacktestResult

            results = (
                self.db.query(BacktestResult)
                .filter(BacktestResult.status == "completed")
                .order_by(BacktestResult.created_at.desc())
                .limit(5)
                .all()
            )

            backtest_list = []
            for r in results:
                backtest_list.append({
                    "id": r.id,
                    "name": r.name,
                    "strategy_type": r.strategy_type,
                    "total_return": r.total_return,
                    "sharpe_ratio": r.sharpe_ratio,
                    "max_drawdown": r.max_drawdown,
                    "win_rate": r.win_rate,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                })

            return {
                "total_backtests": len(backtest_list),
                "recent_backtests": backtest_list,
                "data_available": True,
            }
        except Exception as e:
            logger.error(f"查询回测结果失败: user_id={user_id}, error={e}")
            return {
                "total_backtests": 0,
                "recent_backtests": [],
                "data_available": False,
            }

    async def _generate_natural_response(
        self,
        query: str,
        data: Dict[str, Any],
    ) -> str:
        """将结构化数据转化为自然语言回复"""
        prompt = (
            f"用户问题：{query}\n\n"
            f"查询结果数据：\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n\n"
            f"请基于以上数据，用自然、专业的语言回答用户的问题。"
            f"请突出关键数据，结构清晰。"
        )

        try:
            return await self.llm.chat_with_system(
                system_prompt=self._system_prompt,
                user_message=prompt,
                temperature=0.7,
                max_tokens=1000,
            )
        except LLMError as e:
            logger.error(f"生成自然回复失败: {e}")
            return f"查询已完成，但 AI 回复暂不可用。原始数据：{json.dumps(data, ensure_ascii=False)}"

    @staticmethod
    def _extract_suggestions(advice: str) -> List[Dict[str, str]]:
        """从 LLM 建议文本中提取结构化建议"""
        suggestions: List[Dict[str, str]] = []

        # 按编号或项目符号分割
        import re
        # 匹配编号列表（1. 2. 3. 或 - 或 * 开头）
        items = re.split(r'\n\s*(?:\d+[.、)）]|[-*])\s*', advice)

        for item in items:
            item = item.strip()
            if len(item) > 10 and len(item) < 200:
                suggestions.append({
                    "content": item,
                    "type": "advice",
                })

        # 如果没有提取到结构化建议，返回整体建议
        if not suggestions and advice:
            suggestions.append({
                "content": advice[:500],
                "type": "general",
            })

        return suggestions[:10]  # 最多返回 10 条建议

    # ==================== 模拟数据方法 ====================

    @staticmethod
    def _generate_mock_sentiment(market: str) -> Dict[str, Any]:
        """生成模拟情绪数据（用于数据库无数据时的降级）"""
        import random
        random.seed(hash(market) % 10000)

        score = random.uniform(-0.3, 0.3)
        if score > 0.1:
            sentiment = "positive"
        elif score < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "market": market,
            "sentiment": sentiment,
            "score": round(score, 4),
            "confidence": 0.3,
            "distribution": {
                "positive": random.randint(3, 10),
                "negative": random.randint(2, 8),
                "neutral": random.randint(5, 15),
            },
            "hot_topics": [
                {"keyword": "市场走势", "count": random.randint(3, 8)},
                {"keyword": "政策变化", "count": random.randint(2, 5)},
            ],
            "summary": f"{market}市场模拟情绪分析（数据库暂无新闻数据）。",
            "news_analysis": {"total": 0, "details": []},
        }

    @staticmethod
    def _generate_mock_price_data(days: int) -> List[Dict[str, Any]]:
        """生成模拟行情数据"""
        import random
        random.seed(42)

        data = []
        price = 100.0
        for i in range(days):
            change = random.gauss(0, 0.02)
            price *= (1 + change)
            volume = random.gauss(1000000, 300000)
            data.append({
                "date": f"2024-{(i // 30 + 1):02d}-{(i % 30 + 1):02d}",
                "open": round(price * (1 + random.gauss(0, 0.005)), 2),
                "high": round(price * (1 + abs(random.gauss(0, 0.01))), 2),
                "low": round(price * (1 - abs(random.gauss(0, 0.01))), 2),
                "close": round(price, 2),
                "volume": max(0, round(volume)),
            })
        return data
