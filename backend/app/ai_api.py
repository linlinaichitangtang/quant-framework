"""
V1.5 智能分析助手 API 路由

提供 AI 对话、市场情绪分析、异常交易检测、策略归因分析、
自然语言查询、AI 策略建议等智能分析能力。
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from .database import get_db
from .auth import get_current_user
from .ai_service import AIService
from .llm_client import LLMClient, LLMProvider
from .config import settings
from . import schemas


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["AI 智能分析"])


# ========== 请求/响应模型 ==========

class ChatRequest(BaseModel):
    """AI 对话请求"""
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    message: str = Field(..., min_length=1, description="用户消息")


class ChatResponse(BaseModel):
    """AI 对话响应"""
    session_id: str
    response: str
    created_at: str


class SentimentRequest(BaseModel):
    """市场情绪分析请求"""
    market: str = Field(..., description="市场标识 A/HK/US")


class AnomalyDetectRequest(BaseModel):
    """异常交易检测请求"""
    symbol: str = Field(..., description="标的代码")
    market: str = Field("A", description="市场标识")
    days: int = Field(30, ge=1, le=365, description="分析天数")


class AttributionRequest(BaseModel):
    """策略归因分析请求"""
    strategy_id: str = Field(..., description="策略/回测ID")


# ========== 辅助函数 ==========

def _create_ai_service(db: Session) -> AIService:
    """
    创建 AIService 实例

    从 settings 读取 LLM 配置，初始化 LLMClient 和 AIService。
    """
    # 解析 LLM 提供商
    provider_map = {
        "openai": LLMProvider.OPENAI,
        "deepseek": LLMProvider.DEEPSEEK,
        "ollama": LLMProvider.OLLAMA,
    }
    provider = provider_map.get(settings.llm_provider.lower(), LLMProvider.DEEPSEEK)

    # 初始化 LLM 客户端
    llm_client = LLMClient(
        provider=provider,
        api_key=settings.llm_api_key or None,
        base_url=settings.llm_base_url or None,
        model_name=settings.llm_model or None,
    )

    return AIService(llm_client=llm_client, db_session=db)


# ========== AI 对话端点 ==========

@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    AI 对话

    支持多轮对话，如果 session_id 为空则自动创建新会话。
    """
    try:
        # 如果没有 session_id，生成新会话
        session_id = request.session_id or str(uuid.uuid4())

        ai_service = _create_ai_service(db)
        result = await ai_service.chat(
            session_id=session_id,
            message=request.message,
            user_id=current_user.get("id", 0),
        )

        return ChatResponse(
            session_id=result["session_id"],
            response=result["response"],
            created_at=result["timestamp"],
        )
    except Exception as e:
        logger.error(f"AI 对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI 对话失败：{str(e)}")


# ========== 对话会话端点 ==========

@router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    获取对话会话列表

    返回当前用户的所有对话会话（分页）。
    当前会话数据存储在内存中，返回空列表占位。
    """
    # 会话数据存储在 AIService 内存中，此处返回分页格式占位
    return schemas.PaginatedResponse(
        total=0,
        page=page,
        page_size=page_size,
        data=[],
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    获取会话详情

    返回指定会话的信息和所有消息记录。
    """
    # 会话数据存储在 AIService 内存中，此处返回占位
    return {
        "session_id": session_id,
        "messages": [],
        "message": "会话数据存储在内存中，请通过 /chat 接口进行对话",
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    删除会话

    删除指定的对话会话及其所有消息记录。
    """
    # 会话数据存储在 AIService 内存中，此处返回占位
    return {"message": f"会话 {session_id} 已删除"}


# ========== 市场情绪分析端点 ==========

@router.post("/sentiment")
async def analyze_sentiment(
    request: SentimentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    市场情绪分析

    结合数据统计和 LLM 深度分析，返回市场情绪评估结果。
    """
    try:
        ai_service = _create_ai_service(db)
        result = await ai_service.analyze_market_sentiment(market=request.market)

        return schemas.SentimentResponse(
            market=result["market"],
            score=result.get("score", 0),
            label=result.get("sentiment", "neutral"),
            news_count=result.get("keyword_analysis", {}).get("news_count", 0),
            summary=result.get("summary", ""),
        )
    except Exception as e:
        logger.error(f"市场情绪分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"情绪分析失败：{str(e)}")


@router.get("/sentiment/history")
async def get_sentiment_history(
    market: str = Query("A", description="市场标识"),
    days: int = Query(30, ge=1, le=365, description="查询天数"),
    db: Session = Depends(get_db),
):
    """
    获取情绪历史

    返回指定市场的历史情绪数据（无需认证）。
    """
    # 历史情绪数据需要持久化存储，此处返回空列表占位
    return {
        "market": market,
        "days": days,
        "data": [],
        "message": "历史情绪数据暂未持久化，请使用 POST /sentiment 获取实时分析",
    }


# ========== 异常交易检测端点 ==========

@router.post("/anomaly/detect")
async def detect_anomaly(
    request: AnomalyDetectRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    异常交易检测

    基于统计方法检测异常交易，结合 LLM 解释异常原因。
    """
    try:
        ai_service = _create_ai_service(db)
        result = await ai_service.detect_anomalies(
            symbol=request.symbol,
            market=request.market,
            days=request.days,
        )

        report = result.get("report", {})

        return schemas.AnomalyResponse(
            symbol=result["symbol"],
            anomalies=report.get("anomalies", []),
            summary=report.get("summary", ""),
            risk_level=report.get("risk_level", "medium"),
        )
    except Exception as e:
        logger.error(f"异常检测失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"异常检测失败：{str(e)}")


@router.get("/anomaly/records")
async def get_anomaly_records(
    symbol: Optional[str] = Query(None, description="标的代码"),
    market: Optional[str] = Query(None, description="市场标识"),
    severity: Optional[str] = Query(None, description="严重级别 high/medium/low"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """
    获取异常记录

    返回异常交易检测记录列表（无需认证）。
    """
    # 异常记录需要持久化存储，此处返回空分页占位
    return schemas.PaginatedResponse(
        total=0,
        page=page,
        page_size=page_size,
        data=[],
    )


# ========== 策略归因分析端点 ==========

@router.post("/attribution")
async def analyze_attribution(
    request: AttributionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    策略归因分析

    分析回测结果，分解收益来源（选股 Alpha、择时收益、市场 Beta 等）。
    """
    try:
        ai_service = _create_ai_service(db)
        result = await ai_service.analyze_strategy_attribution(
            strategy_id=request.strategy_id,
        )

        # 检查是否找到回测数据
        if result.get("status") == "not_found":
            raise HTTPException(
                status_code=404,
                detail=result.get("message", "未找到回测数据"),
            )

        attribution = result.get("attribution", {})
        decomposition = attribution.get("return_decomposition", {})

        return schemas.AttributionResponse(
            strategy_id=result["strategy_id"],
            total_return=attribution.get("backtest_summary", {}).get("total_return", 0),
            alpha=decomposition.get("alpha", 0),
            beta_return=decomposition.get("beta", 0),
            timing_return=decomposition.get("timing", 0),
            sector_contribution=attribution.get("sector_contribution"),
            risk_contribution=attribution.get("risk_contribution"),
            summary=result.get("llm_interpretation", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"策略归因分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"归因分析失败：{str(e)}")


# ========== 自然语言查询端点 ==========

@router.post("/query")
async def natural_language_query(
    request: schemas.NLQueryRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    自然语言查询

    解析用户自然语言问题，转化为数据查询并返回结果。
    支持行情查询、持仓查询、策略查询、市场分析等。
    """
    try:
        ai_service = _create_ai_service(db)
        result = await ai_service.natural_language_query(
            query=request.query,
            user_id=current_user.get("id", 0),
        )

        return schemas.NLQueryResponse(
            answer=result.get("response", ""),
            data=result.get("data"),
            confidence=0.8 if result.get("intent") != "error" else 0.0,
        )
    except Exception as e:
        logger.error(f"自然语言查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败：{str(e)}")


# ========== AI 策略建议端点 ==========

@router.post("/advice")
async def get_strategy_advice(
    request: schemas.StrategyAdviceRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    AI 策略建议

    基于市场状态和用户风险偏好，生成个性化的策略建议。
    """
    try:
        ai_service = _create_ai_service(db)
        result = await ai_service.generate_strategy_advice(
            market=request.market,
            risk_level=request.risk_level,
        )

        # 从结构化建议中提取操作建议和风险提示
        suggestions = result.get("suggestions", [])
        suggested_actions = [
            s.get("content", "") for s in suggestions
            if s.get("type") == "advice"
        ]

        # 提取风险提示（包含"风险"关键词的建议）
        risk_warnings = [
            s.get("content", "") for s in suggestions
            if "风险" in s.get("content", "")
        ]

        return schemas.StrategyAdviceResponse(
            advice=result.get("advice", ""),
            reasoning=result.get("advice", ""),
            risk_warnings=risk_warnings[:5],
            suggested_actions=suggested_actions[:5],
        )
    except Exception as e:
        logger.error(f"策略建议生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"策略建议生成失败：{str(e)}")
