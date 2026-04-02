"""
市场情绪分析器 — 基于关键词和规则的市场情绪分析

纯算法模块，不依赖外部 LLM API。提供以下能力：
- 单文本情绪分析（基于中文金融情绪词典）
- 批量新闻情绪分析
- 市场综合情绪计算
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """
    市场情绪分析器

    基于内置的中文金融情绪词典和规则引擎，对文本进行情绪分析。
    支持正面/负面/中性三级分类，并输出情绪得分和置信度。
    """

    def __init__(self):
        """初始化情绪分析器，加载内置情绪词典"""
        self._keywords = self._build_sentiment_keywords()
        # 情绪修饰词（增强/减弱）
        self._intensifiers = {
            "非常": 1.5, "极其": 1.8, "特别": 1.5, "十分": 1.5,
            "大幅": 1.6, "显著": 1.5, "明显": 1.3, "严重": 1.7,
            "小幅": 0.6, "略微": 0.5, "轻微": 0.5, "微幅": 0.5,
            "持续": 1.3, "连续": 1.3, "突然": 1.4, "急剧": 1.7,
            "稳步": 1.2, "快速": 1.4, "强劲": 1.6, "疲软": 1.4,
        }
        # 否定词
        self._negations = {
            "不", "没", "没有", "未", "无", "非", "别", "莫",
            "难以", "不再", "并非", "并非", "不会", "不能",
        }

    @staticmethod
    def _build_sentiment_keywords() -> Dict[str, List[str]]:
        """
        构建中文金融情绪关键词库

        Returns:
            包含 positive / negative / neutral 三个分类的词典
        """
        return {
            # ==================== 正面关键词 ====================
            "positive": [
                # 涨幅相关
                "上涨", "涨", "大涨", "暴涨", "飙升", "走高", "上行",
                "攀升", "回升", "反弹", "触底反弹", "止跌回升", "企稳",
                "翻红", "收红", "红盘", "阳线", "大阳线",
                "突破", "新高", "历史新高", "创历史新高", "涨停",
                "连涨", "持续上涨", "稳步上涨", "强势上涨",
                # 盈利相关
                "盈利", "利润", "净利润", "营收", "收入增长",
                "业绩", "业绩大增", "超预期", "大幅增长", "同比增长",
                "扭亏为盈", "盈利超预期", "利润翻倍", "营收创新高",
                # 市场情绪正面
                "利好", "利好消息", "重大利好", "政策利好",
                "看涨", "看多", "牛市", "多头", "做多",
                "抄底", "买入", "增持", "加仓", "建仓",
                "资金流入", "净流入", "主力资金", "北向资金流入",
                "放量上涨", "量价齐升", "底部放量",
                # 公司层面
                "回购", "分红", "派息", "高送转",
                "战略合作", "并购", "收购", "重组",
                "获批", "获批上市", "通过审核",
                "升级", "创新高", "龙头", "行业领先",
                "订单", "中标", "签约", "合作",
                # 宏观正面
                "降息", "降准", "宽松", "刺激", "稳增长",
                "复苏", "回暖", "企稳回升", "经济向好",
                "信心", "乐观", "看好", "前景看好",
                "支撑", "底部", "低估", "价值洼地",
                # 技术面正面
                "金叉", "突破均线", "MACD金叉", "放量突破",
                "多头排列", "趋势向上", "支撑位", "强势",
                "超卖", "技术性反弹", "底部形态",
            ],
            # ==================== 负面关键词 ====================
            "negative": [
                # 跌幅相关
                "下跌", "跌", "大跌", "暴跌", "崩盘", "跳水", "下行",
                "下挫", "回调", "大跌", "阴跌", "暴跌", "闪崩",
                "翻绿", "收绿", "绿盘", "阴线", "大阴线",
                "跌破", "新低", "历史新低", "跌停",
                "连跌", "持续下跌", "加速下跌", "断崖式下跌",
                # 亏损相关
                "亏损", "净亏损", "营收下滑", "利润下降",
                "业绩下滑", "不及预期", "大幅下滑", "同比下降",
                "由盈转亏", "亏损扩大", "商誉减值", "资产减值",
                "财务造假", "虚增利润", "信息披露违规",
                # 市场情绪负面
                "利空", "利空消息", "重大利空", "政策利空",
                "看跌", "看空", "熊市", "空头", "做空",
                "抛售", "卖出", "减持", "清仓", "割肉",
                "资金流出", "净流出", "主力出逃", "北向资金流出",
                "放量下跌", "缩量下跌", "破位下跌",
                # 公司层面
                "退市", "ST", "*ST", "暂停上市",
                "违约", "债务危机", "资金链断裂", "破产",
                "被调查", "被处罚", "被监管", "立案调查",
                "高管离职", "核心人员离职", "内斗",
                "诉讼", "仲裁", "处罚", "警示函",
                # 宏观负面
                "加息", "缩表", "紧缩", "衰退", "滞胀",
                "通胀", "通缩", "经济下行", "放缓",
                "风险", "危机", "恐慌", "悲观", "担忧",
                "泡沫", "过热", "监管收紧", "政策收紧",
                # 技术面负面
                "死叉", "跌破均线", "MACD死叉", "破位",
                "空头排列", "趋势向下", "阻力位", "弱势",
                "超买", "顶背离", "头部形态", "见顶",
            ],
            # ==================== 中性关键词 ====================
            "neutral": [
                "震荡", "横盘", "盘整", "整理", "波动",
                "持平", "持平", "不变", "稳定",
                "观望", "等待", "谨慎", "中性",
                "调整", "技术性调整", "正常回调",
                "维持", "保持", "延续", "继续",
                "预计", "预期", "可能", "或将",
                "据报道", "消息人士", "市场人士",
                "分析师", "机构", "研报", "评级",
                "中性", "持有", "持有", "维持评级",
            ],
        }

    def get_sentiment_keywords(self) -> Dict[str, List[str]]:
        """
        获取情绪关键词库

        Returns:
            包含 positive / negative / neutral 三个分类的词典
        """
        return self._keywords

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        单文本情绪分析

        基于关键词匹配和规则引擎，分析文本的情绪倾向。

        算法流程：
        1. 分词（简单按标点和空格分割）
        2. 关键词匹配，统计正面/负面/中性词出现次数
        3. 考虑修饰词（增强/减弱）和否定词的影响
        4. 计算综合情绪得分

        Args:
            text: 待分析文本

        Returns:
            {
                "sentiment": "positive" / "negative" / "neutral",
                "score": float,           # -1.0 到 1.0
                "confidence": float,      # 0.0 到 1.0
                "positive_count": int,
                "negative_count": int,
                "neutral_count": int,
                "matched_keywords": list,  # 匹配到的关键词
            }
        """
        if not text or not text.strip():
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "matched_keywords": [],
            }

        text = text.strip()

        # 简单分词：按标点、空格分割为词组
        segments = re.split(r'[，。！？、；：\s,\.!?;:\n\r\t]+', text)
        segments = [s for s in segments if s]

        positive_score = 0.0
        negative_score = 0.0
        neutral_count = 0
        matched_keywords: List[Dict[str, Any]] = []

        for segment in segments:
            # 检查否定词
            has_negation = any(neg in segment for neg in self._negations)

            # 检查修饰词
            intensifier = 1.0
            for word, multiplier in self._intensifiers.items():
                if word in segment:
                    intensifier = multiplier
                    break

            # 匹配正面关键词
            for keyword in self._keywords["positive"]:
                if keyword in segment:
                    weight = 1.0 * intensifier
                    if has_negation:
                        # 否定词反转情绪，但权重降低
                        negative_score += weight * 0.7
                        matched_keywords.append({
                            "keyword": keyword,
                            "type": "positive_negated",
                            "weight": -weight * 0.7,
                        })
                    else:
                        positive_score += weight
                        matched_keywords.append({
                            "keyword": keyword,
                            "type": "positive",
                            "weight": weight,
                        })
                    break  # 每个片段只匹配一次

            # 匹配负面关键词
            for keyword in self._keywords["negative"]:
                if keyword in segment:
                    weight = 1.0 * intensifier
                    if has_negation:
                        # 否定负面 = 偏正面
                        positive_score += weight * 0.5
                        matched_keywords.append({
                            "keyword": keyword,
                            "type": "negative_negated",
                            "weight": weight * 0.5,
                        })
                    else:
                        negative_score += weight
                        matched_keywords.append({
                            "keyword": keyword,
                            "type": "negative",
                            "weight": -weight,
                        })
                    break

            # 匹配中性关键词
            for keyword in self._keywords["neutral"]:
                if keyword in segment:
                    neutral_count += 1
                    break

        # 计算综合得分
        total = positive_score + negative_score
        if total == 0:
            score = 0.0
            sentiment = "neutral"
            confidence = 0.3
        else:
            score = (positive_score - negative_score) / total
            # 归一化到 [-1, 1]
            score = max(-1.0, min(1.0, score))

            if score > 0.15:
                sentiment = "positive"
            elif score < -0.15:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            # 置信度基于得分偏离 0 的程度和匹配到的关键词数量
            confidence = min(1.0, abs(score) * 0.8 + len(matched_keywords) * 0.05)

        return {
            "sentiment": sentiment,
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "positive_count": int(positive_score),
            "negative_count": int(negative_score),
            "neutral_count": neutral_count,
            "matched_keywords": matched_keywords[:20],  # 限制返回数量
        }

    def analyze_news_batch(self, news_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量新闻情绪分析

        Args:
            news_list: 新闻列表，每项包含：
                - title: 新闻标题
                - content: 新闻内容（可选）
                - source: 来源（可选）
                - publish_time: 发布时间（可选）

        Returns:
            {
                "total": int,
                "sentiment_distribution": {"positive": int, "negative": int, "neutral": int},
                "average_score": float,
                "details": list,  # 每条新闻的分析结果
            }
        """
        if not news_list:
            return {
                "total": 0,
                "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
                "average_score": 0.0,
                "details": [],
            }

        distribution = {"positive": 0, "negative": 0, "neutral": 0}
        total_score = 0.0
        details: List[Dict[str, Any]] = []

        for idx, news in enumerate(news_list):
            # 优先分析标题，其次分析内容
            text = news.get("title", "")
            content = news.get("content", "")
            if content:
                text = f"{text} {content}"

            result = self.analyze_text(text)
            result["index"] = idx
            result["title"] = news.get("title", "")
            result["source"] = news.get("source", "")
            result["publish_time"] = news.get("publish_time", "")

            distribution[result["sentiment"]] += 1
            total_score += result["score"]
            details.append(result)

        average_score = total_score / len(news_list) if news_list else 0.0

        logger.info(
            f"批量新闻分析完成: 共 {len(news_list)} 条, "
            f"正面={distribution['positive']}, "
            f"负面={distribution['negative']}, "
            f"中性={distribution['neutral']}, "
            f"平均得分={average_score:.4f}"
        )

        return {
            "total": len(news_list),
            "sentiment_distribution": distribution,
            "average_score": round(average_score, 4),
            "details": details,
        }

    def calculate_market_sentiment(
        self,
        market: str,
        news: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        计算市场综合情绪

        综合分析新闻情绪，生成市场级别的情绪报告。

        Args:
            market: 市场标识（如 "A"、"HK"、"US"）
            news: 新闻列表

        Returns:
            {
                "market": str,
                "sentiment": str,          # positive / negative / neutral
                "score": float,            # -1.0 到 1.0
                "confidence": float,       # 0.0 到 1.0
                "distribution": dict,
                "hot_topics": list,        # 热门关键词
                "summary": str,            # 文字摘要
                "news_analysis": dict,     # 批量分析结果
            }
        """
        market_names = {
            "A": "A股", "HK": "港股", "US": "美股",
            "a": "A股", "hk": "港股", "us": "美股",
        }
        market_display = market_names.get(market, market)

        # 批量分析新闻
        batch_result = self.analyze_news_batch(news)

        score = batch_result["average_score"]
        distribution = batch_result["sentiment_distribution"]
        total = batch_result["total"]

        # 判定情绪
        if score > 0.2:
            sentiment = "positive"
        elif score < -0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # 置信度
        confidence = min(1.0, abs(score) + total * 0.01)

        # 提取热门关键词
        keyword_freq: Dict[str, int] = {}
        for detail in batch_result["details"]:
            for kw_info in detail.get("matched_keywords", []):
                kw = kw_info["keyword"]
                keyword_freq[kw] = keyword_freq.get(kw, 0) + 1

        hot_topics = sorted(keyword_freq.items(), key=lambda x: -x[1])[:10]

        # 生成摘要
        summary_parts = [
            f"{market_display}市场综合情绪：{sentiment}（得分：{score:.2f}）。"
        ]
        summary_parts.append(
            f"共分析 {total} 条新闻，"
            f"正面 {distribution['positive']} 条，"
            f"负面 {distribution['negative']} 条，"
            f"中性 {distribution['neutral']} 条。"
        )
        if hot_topics:
            top_kws = "、".join(kw for kw, _ in hot_topics[:5])
            summary_parts.append(f"热门关键词：{top_kws}。")

        result = {
            "market": market,
            "market_display": market_display,
            "sentiment": sentiment,
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "distribution": distribution,
            "hot_topics": [{"keyword": kw, "count": cnt} for kw, cnt in hot_topics],
            "summary": "".join(summary_parts),
            "news_analysis": batch_result,
        }

        logger.info(
            f"市场情绪分析: {market_display} -> {sentiment} "
            f"(score={score:.4f}, news_count={total})"
        )
        return result
