"""
V1.6 社区与协作 API 路由
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .community_service import CommunityService
from .schemas import (
    UserProfileResponse, UserProfileUpdate,
    PostCreate, PostResponse, CommentCreate, CommentResponse,
    TradeShareCreate, TradeShareResponse,
    MessageCreate, MessageResponse, ConversationResponse,
    LeaderboardEntry, CommonResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/community", tags=["社区与协作"])


def _get_user_id(current_user: dict, db: Session) -> int:
    """根据当前用户名获取用户ID"""
    from .models import User
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.id


# ==================== 用户资料 ====================

@router.get("/profile/me", response_model=CommonResponse, summary="获取当前用户资料")
def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前登录用户的资料"""
    user_id = _get_user_id(current_user, db)
    profile = CommunityService.get_user_profile(db, user_id, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="用户资料不存在")
    return CommonResponse(data=profile)


@router.get("/profile/{user_id}", response_model=CommonResponse, summary="获取用户资料")
def get_user_profile(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取指定用户的资料"""
    my_id = _get_user_id(current_user, db)
    profile = CommunityService.get_user_profile(db, user_id, my_id)
    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")
    return CommonResponse(data=profile)


@router.put("/profile", response_model=CommonResponse, summary="更新用户资料")
def update_user_profile(
    data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前用户的资料"""
    user_id = _get_user_id(current_user, db)
    profile = CommunityService.update_user_profile(db, user_id, data.model_dump(exclude_none=True))
    return CommonResponse(data=profile)


# ==================== 关注系统 ====================

@router.post("/follow/{user_id}", response_model=CommonResponse, summary="关注用户")
def follow_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """关注指定用户"""
    my_id = _get_user_id(current_user, db)
    try:
        result = CommunityService.follow_user(db, my_id, user_id)
        return CommonResponse(data={"followed": result})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/follow/{user_id}", response_model=CommonResponse, summary="取消关注")
def unfollow_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消关注指定用户"""
    my_id = _get_user_id(current_user, db)
    result = CommunityService.unfollow_user(db, my_id, user_id)
    return CommonResponse(data={"unfollowed": result})


@router.get("/followers/{user_id}", response_model=CommonResponse, summary="获取粉丝列表")
def get_followers(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取指定用户的粉丝列表"""
    result = CommunityService.get_followers(db, user_id, page, page_size)
    return CommonResponse(data=result)


@router.get("/following/{user_id}", response_model=CommonResponse, summary="获取关注列表")
def get_following(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取指定用户的关注列表"""
    result = CommunityService.get_following(db, user_id, page, page_size)
    return CommonResponse(data=result)


# ==================== 讨论区 ====================

@router.post("/posts", response_model=CommonResponse, summary="创建帖子")
def create_post(
    data: PostCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建讨论帖子"""
    user_id = _get_user_id(current_user, db)
    post = CommunityService.create_post(db, user_id, data.model_dump())
    return CommonResponse(data=post)


@router.get("/posts", response_model=CommonResponse, summary="获取帖子列表")
def get_posts(
    category: Optional[str] = Query(None, description="分类筛选 strategy/market/risk/general/question"),
    sort: str = Query("latest", description="排序方式 latest/hot/featured"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取帖子列表，支持分类筛选和排序"""
    user_id = _get_user_id(current_user, db)
    result = CommunityService.get_posts(db, category, sort, page, page_size, user_id)
    return CommonResponse(data=result)


@router.get("/posts/{post_id}", response_model=CommonResponse, summary="获取帖子详情")
def get_post(
    post_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取帖子详情（含评论）"""
    user_id = _get_user_id(current_user, db)
    post = CommunityService.get_post(db, post_id, user_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return CommonResponse(data=post)


@router.post("/posts/{post_id}/like", response_model=CommonResponse, summary="点赞帖子")
def like_post(
    post_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """点赞/取消点赞帖子"""
    user_id = _get_user_id(current_user, db)
    try:
        is_liked = CommunityService.like_post(db, user_id, post_id)
        return CommonResponse(data={"is_liked": is_liked})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/posts/{post_id}/comments", response_model=CommonResponse, summary="评论帖子")
def create_comment(
    post_id: int,
    data: CommentCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """评论帖子"""
    user_id = _get_user_id(current_user, db)
    try:
        comment = CommunityService.create_comment(
            db, user_id, post_id, data.content, data.parent_id
        )
        return CommonResponse(data=comment)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/posts/{post_id}/comments", response_model=CommonResponse, summary="获取帖子评论")
def get_comments(
    post_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取帖子评论列表"""
    result = CommunityService.get_comments(db, post_id, page, page_size)
    return CommonResponse(data=result)


# ==================== 交易分享 ====================

@router.post("/trades/share", response_model=CommonResponse, summary="分享交易")
def share_trade(
    data: TradeShareCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分享交易记录（支持匿名）"""
    user_id = _get_user_id(current_user, db)
    share = CommunityService.share_trade(db, user_id, data.model_dump())
    return CommonResponse(data=share)


@router.get("/trades/shared", response_model=CommonResponse, summary="获取交易分享列表")
def get_shared_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取交易分享列表"""
    result = CommunityService.get_shared_trades(db, page, page_size)
    return CommonResponse(data=result)


# ==================== 排行榜 ====================

@router.get("/leaderboard", response_model=CommonResponse, summary="获取排行榜")
def get_leaderboard(
    period: str = Query("total", description="时间周期 daily/weekly/monthly/total"),
    metric: str = Query("total_return", description="排行指标 total_return/win_rate/trade_count"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取排行榜"""
    result = CommunityService.get_leaderboard(db, period, metric, page, page_size)
    return CommonResponse(data=result)


# ==================== 私信 ====================

@router.post("/messages", response_model=CommonResponse, summary="发送私信")
def send_message(
    data: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送私信"""
    user_id = _get_user_id(current_user, db)
    try:
        message = CommunityService.send_message(db, user_id, data.receiver_id, data.content)
        return CommonResponse(data=message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/messages/{user_id}", response_model=CommonResponse, summary="获取私信列表")
def get_messages(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取与指定用户的私信列表"""
    my_id = _get_user_id(current_user, db)
    result = CommunityService.get_messages(db, my_id, user_id, page, page_size)
    return CommonResponse(data=result)


@router.get("/conversations", response_model=CommonResponse, summary="获取会话列表")
def get_conversations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的所有会话列表"""
    user_id = _get_user_id(current_user, db)
    conversations = CommunityService.get_conversations(db, user_id)
    return CommonResponse(data=conversations)


# ==================== 搜索 ====================

@router.get("/search/users", response_model=CommonResponse, summary="搜索用户")
def search_users(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """搜索用户（按用户名/显示名/邮箱）"""
    result = CommunityService.search_users(db, q, page, page_size)
    return CommonResponse(data=result)
