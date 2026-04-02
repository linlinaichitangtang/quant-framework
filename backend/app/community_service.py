"""
V1.6 社区与协作服务层
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import or_, and_, desc, asc, func
from sqlalchemy.orm import Session

from .models import (
    User, UserProfile, UserFollow, DiscussionPost, PostComment,
    PostLike, TradeShare, PrivateMessage
)

logger = logging.getLogger(__name__)


class CommunityService:
    """社区与协作服务"""

    # ==================== 用户资料 ====================

    @staticmethod
    def get_user_profile(db: Session, user_id: int, current_user_id: Optional[int] = None) -> dict:
        """
        获取用户资料（含统计：关注数/粉丝数/帖子数/胜率）

        Args:
            db: 数据库会话
            user_id: 目标用户ID
            current_user_id: 当前登录用户ID（用于判断是否已关注）

        Returns:
            用户资料字典
        """
        # 查询用户基本信息
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        # 查询或创建用户资料
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            # 自动创建资料
            profile = UserProfile(user_id=user_id)
            db.add(profile)
            db.commit()
            db.refresh(profile)

        # 判断当前用户是否关注了该用户
        is_following = None
        if current_user_id and current_user_id != user_id:
            follow = db.query(UserFollow).filter(
                UserFollow.follower_id == current_user_id,
                UserFollow.following_id == user_id
            ).first()
            is_following = follow is not None

        return {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "avatar_url": profile.avatar_url,
            "bio": profile.bio,
            "expertise": profile.expertise,
            "risk_preference": profile.risk_preference,
            "total_trades": profile.total_trades,
            "win_rate": profile.win_rate,
            "total_pnl": profile.total_pnl,
            "followers_count": profile.followers_count,
            "following_count": profile.following_count,
            "posts_count": profile.posts_count,
            "is_following": is_following,
        }

    @staticmethod
    def update_user_profile(db: Session, user_id: int, data: dict) -> dict:
        """
        更新用户资料（头像/简介/擅长策略/风险偏好）

        Args:
            db: 数据库会话
            user_id: 用户ID
            data: 更新数据字典

        Returns:
            更新后的用户资料字典
        """
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(user_id=user_id)
            db.add(profile)

        # 更新允许的字段
        for field in ["avatar_url", "bio", "expertise", "risk_preference"]:
            if field in data and data[field] is not None:
                setattr(profile, field, data[field])

        db.commit()
        db.refresh(profile)
        return CommunityService.get_user_profile(db, user_id)

    # ==================== 关注系统 ====================

    @staticmethod
    def follow_user(db: Session, follower_id: int, following_id: int) -> bool:
        """
        关注用户

        Args:
            db: 数据库会话
            follower_id: 关注者ID
            following_id: 被关注者ID

        Returns:
            是否关注成功
        """
        if follower_id == following_id:
            raise ValueError("不能关注自己")

        # 检查是否已关注
        existing = db.query(UserFollow).filter(
            UserFollow.follower_id == follower_id,
            UserFollow.following_id == following_id
        ).first()
        if existing:
            return False  # 已关注

        # 创建关注关系
        follow = UserFollow(follower_id=follower_id, following_id=following_id)
        db.add(follow)

        # 更新计数
        follower_profile = db.query(UserProfile).filter(UserProfile.user_id == follower_id).first()
        if follower_profile:
            follower_profile.following_count = (follower_profile.following_count or 0) + 1

        following_profile = db.query(UserProfile).filter(UserProfile.user_id == following_id).first()
        if following_profile:
            following_profile.followers_count = (following_profile.followers_count or 0) + 1

        db.commit()
        return True

    @staticmethod
    def unfollow_user(db: Session, follower_id: int, following_id: int) -> bool:
        """
        取消关注

        Args:
            db: 数据库会话
            follower_id: 关注者ID
            following_id: 被关注者ID

        Returns:
            是否取消成功
        """
        follow = db.query(UserFollow).filter(
            UserFollow.follower_id == follower_id,
            UserFollow.following_id == following_id
        ).first()
        if not follow:
            return False  # 未关注

        db.delete(follow)

        # 更新计数
        follower_profile = db.query(UserProfile).filter(UserProfile.user_id == follower_id).first()
        if follower_profile:
            follower_profile.following_count = max(0, (follower_profile.following_count or 0) - 1)

        following_profile = db.query(UserProfile).filter(UserProfile.user_id == following_id).first()
        if following_profile:
            following_profile.followers_count = max(0, (following_profile.followers_count or 0) - 1)

        db.commit()
        return True

    @staticmethod
    def get_followers(db: Session, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        """
        获取粉丝列表

        Args:
            db: 数据库会话
            user_id: 用户ID
            page: 页码
            page_size: 每页数量

        Returns:
            分页粉丝列表
        """
        query = db.query(UserFollow).filter(UserFollow.following_id == user_id)
        total = query.count()
        follows = query.order_by(desc(UserFollow.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        followers = []
        for f in follows:
            user = db.query(User).filter(User.id == f.follower_id).first()
            if user:
                profile = db.query(UserProfile).filter(UserProfile.user_id == f.follower_id).first()
                followers.append({
                    "user_id": user.id,
                    "username": user.username,
                    "display_name": user.display_name,
                    "avatar_url": profile.avatar_url if profile else None,
                    "followed_at": f.created_at.isoformat() if f.created_at else None,
                })

        return {"total": total, "page": page, "page_size": page_size, "data": followers}

    @staticmethod
    def get_following(db: Session, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        """
        获取关注列表

        Args:
            db: 数据库会话
            user_id: 用户ID
            page: 页码
            page_size: 每页数量

        Returns:
            分页关注列表
        """
        query = db.query(UserFollow).filter(UserFollow.follower_id == user_id)
        total = query.count()
        follows = query.order_by(desc(UserFollow.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        following_list = []
        for f in follows:
            user = db.query(User).filter(User.id == f.following_id).first()
            if user:
                profile = db.query(UserProfile).filter(UserProfile.user_id == f.following_id).first()
                following_list.append({
                    "user_id": user.id,
                    "username": user.username,
                    "display_name": user.display_name,
                    "avatar_url": profile.avatar_url if profile else None,
                    "followed_at": f.created_at.isoformat() if f.created_at else None,
                })

        return {"total": total, "page": page, "page_size": page_size, "data": following_list}

    # ==================== 讨论区 ====================

    @staticmethod
    def create_post(db: Session, user_id: int, data: dict) -> dict:
        """
        创建讨论帖子

        Args:
            db: 数据库会话
            user_id: 作者ID
            data: 帖子数据 {title, content, category, tags}

        Returns:
            创建的帖子字典
        """
        post = DiscussionPost(
            author_id=user_id,
            title=data["title"],
            content=data["content"],
            category=data.get("category", "general"),
            tags=json.dumps(data.get("tags", []), ensure_ascii=False) if data.get("tags") else None,
        )
        db.add(post)

        # 更新用户帖子计数
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if profile:
            profile.posts_count = (profile.posts_count or 0) + 1

        db.commit()
        db.refresh(post)

        # 获取作者信息
        user = db.query(User).filter(User.id == user_id).first()
        author_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

        return {
            "id": post.id,
            "author_id": user_id,
            "author_name": user.username if user else "未知用户",
            "author_avatar": author_profile.avatar_url if author_profile else None,
            "title": post.title,
            "content": post.content,
            "category": post.category,
            "tags": json.loads(post.tags) if post.tags else None,
            "likes_count": 0,
            "comments_count": 0,
            "views_count": 0,
            "is_pinned": False,
            "is_featured": False,
            "created_at": post.created_at.isoformat() if post.created_at else None,
        }

    @staticmethod
    def get_posts(db: Session, category: Optional[str] = None, sort: str = "latest",
                  page: int = 1, page_size: int = 20, current_user_id: Optional[int] = None) -> dict:
        """
        获取帖子列表（支持按热度/最新/精华排序）

        Args:
            db: 数据库会话
            category: 分类筛选
            sort: 排序方式 latest/hot/featured
            page: 页码
            page_size: 每页数量
            current_user_id: 当前用户ID（用于判断是否已点赞）

        Returns:
            分页帖子列表
        """
        query = db.query(DiscussionPost)

        # 分类筛选
        if category and category != "all":
            query = query.filter(DiscussionPost.category == category)

        # 排序
        if sort == "hot":
            # 按热度排序：综合点赞数、评论数、浏览数
            query = query.order_by(
                desc((DiscussionPost.likes_count * 3 + DiscussionPost.comments_count * 2 + DiscussionPost.views_count))
            )
        elif sort == "featured":
            # 精华帖优先，再按时间
            query = query.order_by(desc(DiscussionPost.is_featured), desc(DiscussionPost.created_at))
        else:
            # 最新：置顶帖优先，再按时间
            query = query.order_by(desc(DiscussionPost.is_pinned), desc(DiscussionPost.created_at))

        total = query.count()
        posts = query.offset((page - 1) * page_size).limit(page_size).all()

        result = []
        for post in posts:
            user = db.query(User).filter(User.id == post.author_id).first()
            author_profile = db.query(UserProfile).filter(UserProfile.user_id == post.author_id).first()

            # 判断当前用户是否点赞
            is_liked = None
            if current_user_id:
                like = db.query(PostLike).filter(
                    PostLike.post_id == post.id,
                    PostLike.user_id == current_user_id
                ).first()
                is_liked = like is not None

            result.append({
                "id": post.id,
                "author_id": post.author_id,
                "author_name": user.username if user else "未知用户",
                "author_avatar": author_profile.avatar_url if author_profile else None,
                "title": post.title,
                "content": post.content,
                "category": post.category,
                "tags": json.loads(post.tags) if post.tags else None,
                "likes_count": post.likes_count or 0,
                "comments_count": post.comments_count or 0,
                "views_count": post.views_count or 0,
                "is_pinned": post.is_pinned or False,
                "is_featured": post.is_featured or False,
                "is_liked": is_liked,
                "created_at": post.created_at.isoformat() if post.created_at else None,
            })

        return {"total": total, "page": page, "page_size": page_size, "data": result}

    @staticmethod
    def get_post(db: Session, post_id: int, current_user_id: Optional[int] = None) -> dict:
        """
        获取帖子详情（含评论）

        Args:
            db: 数据库会话
            post_id: 帖子ID
            current_user_id: 当前用户ID

        Returns:
            帖子详情字典
        """
        post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
        if not post:
            return None

        # 增加浏览数
        post.views_count = (post.views_count or 0) + 1
        db.commit()

        # 获取作者信息
        user = db.query(User).filter(User.id == post.author_id).first()
        author_profile = db.query(UserProfile).filter(UserProfile.user_id == post.author_id).first()

        # 判断当前用户是否点赞
        is_liked = None
        if current_user_id:
            like = db.query(PostLike).filter(
                PostLike.post_id == post.id,
                PostLike.user_id == current_user_id
            ).first()
            is_liked = like is not None

        # 获取评论列表
        comments = db.query(PostComment).filter(
            PostComment.post_id == post_id,
            PostComment.parent_id.is_(None)  # 只获取顶级评论
        ).order_by(asc(PostComment.created_at)).all()

        comment_list = []
        for comment in comments:
            comment_user = db.query(User).filter(User.id == comment.author_id).first()
            # 获取子评论
            replies = db.query(PostComment).filter(
                PostComment.parent_id == comment.id
            ).order_by(asc(PostComment.created_at)).all()

            reply_list = []
            for reply in replies:
                reply_user = db.query(User).filter(User.id == reply.author_id).first()
                reply_list.append({
                    "id": reply.id,
                    "author_id": reply.author_id,
                    "author_name": reply_user.username if reply_user else "未知用户",
                    "content": reply.content,
                    "parent_id": reply.parent_id,
                    "likes_count": reply.likes_count or 0,
                    "created_at": reply.created_at.isoformat() if reply.created_at else None,
                })

            comment_list.append({
                "id": comment.id,
                "author_id": comment.author_id,
                "author_name": comment_user.username if comment_user else "未知用户",
                "content": comment.content,
                "parent_id": None,
                "likes_count": comment.likes_count or 0,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
                "replies": reply_list,
            })

        return {
            "id": post.id,
            "author_id": post.author_id,
            "author_name": user.username if user else "未知用户",
            "author_avatar": author_profile.avatar_url if author_profile else None,
            "title": post.title,
            "content": post.content,
            "category": post.category,
            "tags": json.loads(post.tags) if post.tags else None,
            "likes_count": post.likes_count or 0,
            "comments_count": post.comments_count or 0,
            "views_count": post.views_count or 0,
            "is_pinned": post.is_pinned or False,
            "is_featured": post.is_featured or False,
            "is_liked": is_liked,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "comments": comment_list,
        }

    @staticmethod
    def like_post(db: Session, user_id: int, post_id: int) -> bool:
        """
        点赞帖子（再次调用则取消点赞）

        Args:
            db: 数据库会话
            user_id: 用户ID
            post_id: 帖子ID

        Returns:
            点赞后状态（True=已点赞，False=已取消）
        """
        post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
        if not post:
            raise ValueError("帖子不存在")

        # 检查是否已点赞
        existing = db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        ).first()

        if existing:
            # 取消点赞
            db.delete(existing)
            post.likes_count = max(0, (post.likes_count or 0) - 1)
            db.commit()
            return False
        else:
            # 添加点赞
            like = PostLike(post_id=post_id, user_id=user_id)
            db.add(like)
            post.likes_count = (post.likes_count or 0) + 1
            db.commit()
            return True

    @staticmethod
    def create_comment(db: Session, user_id: int, post_id: int, content: str,
                       parent_id: Optional[int] = None) -> dict:
        """
        评论帖子

        Args:
            db: 数据库会话
            user_id: 评论者ID
            post_id: 帖子ID
            content: 评论内容
            parent_id: 父评论ID（回复评论时使用）

        Returns:
            创建的评论字典
        """
        post = db.query(DiscussionPost).filter(DiscussionPost.id == post_id).first()
        if not post:
            raise ValueError("帖子不存在")

        comment = PostComment(
            post_id=post_id,
            author_id=user_id,
            content=content,
            parent_id=parent_id,
        )
        db.add(comment)

        # 更新帖子评论计数
        post.comments_count = (post.comments_count or 0) + 1

        db.commit()
        db.refresh(comment)

        user = db.query(User).filter(User.id == user_id).first()

        return {
            "id": comment.id,
            "author_id": user_id,
            "author_name": user.username if user else "未知用户",
            "content": comment.content,
            "parent_id": comment.parent_id,
            "likes_count": 0,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
        }

    @staticmethod
    def get_comments(db: Session, post_id: int, page: int = 1, page_size: int = 20) -> dict:
        """
        获取帖子评论列表

        Args:
            db: 数据库会话
            post_id: 帖子ID
            page: 页码
            page_size: 每页数量

        Returns:
            分页评论列表
        """
        query = db.query(PostComment).filter(
            PostComment.post_id == post_id,
            PostComment.parent_id.is_(None)
        )
        total = query.count()
        comments = query.order_by(asc(PostComment.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        result = []
        for comment in comments:
            user = db.query(User).filter(User.id == comment.author_id).first()
            result.append({
                "id": comment.id,
                "author_id": comment.author_id,
                "author_name": user.username if user else "未知用户",
                "content": comment.content,
                "parent_id": comment.parent_id,
                "likes_count": comment.likes_count or 0,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
            })

        return {"total": total, "page": page, "page_size": page_size, "data": result}

    # ==================== 交易分享 ====================

    @staticmethod
    def share_trade(db: Session, user_id: int, data: dict) -> dict:
        """
        分享交易（匿名/公开）

        Args:
            db: 数据库会话
            user_id: 分享者ID
            data: 交易数据

        Returns:
            分享记录字典
        """
        share = TradeShare(
            user_id=user_id,
            is_anonymous=data.get("is_anonymous", False),
            symbol=data["symbol"],
            market=data["market"],
            side=data["side"],
            entry_price=data.get("entry_price"),
            exit_price=data.get("exit_price"),
            quantity=data.get("quantity"),
            pnl=data.get("pnl"),
            pnl_pct=data.get("pnl_pct"),
            strategy_name=data.get("strategy_name"),
            reasoning=data.get("reasoning"),
        )
        db.add(share)
        db.commit()
        db.refresh(share)

        user = db.query(User).filter(User.id == user_id).first()

        return {
            "id": share.id,
            "user_id": None if share.is_anonymous else user_id,
            "username": None if share.is_anonymous else (user.username if user else "未知用户"),
            "is_anonymous": share.is_anonymous,
            "symbol": share.symbol,
            "market": share.market,
            "side": share.side,
            "entry_price": share.entry_price,
            "exit_price": share.exit_price,
            "quantity": share.quantity,
            "pnl": share.pnl,
            "pnl_pct": share.pnl_pct,
            "strategy_name": share.strategy_name,
            "reasoning": share.reasoning,
            "likes_count": 0,
            "comments_count": 0,
            "created_at": share.created_at.isoformat() if share.created_at else None,
        }

    @staticmethod
    def get_shared_trades(db: Session, page: int = 1, page_size: int = 20) -> dict:
        """
        获取交易分享列表

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量

        Returns:
            分页交易分享列表
        """
        query = db.query(TradeShare)
        total = query.count()
        shares = query.order_by(desc(TradeShare.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        result = []
        for share in shares:
            user = db.query(User).filter(User.id == share.user_id).first()
            result.append({
                "id": share.id,
                "user_id": None if share.is_anonymous else share.user_id,
                "username": None if share.is_anonymous else (user.username if user else "未知用户"),
                "is_anonymous": share.is_anonymous,
                "symbol": share.symbol,
                "market": share.market,
                "side": share.side,
                "entry_price": share.entry_price,
                "exit_price": share.exit_price,
                "quantity": share.quantity,
                "pnl": share.pnl,
                "pnl_pct": share.pnl_pct,
                "strategy_name": share.strategy_name,
                "reasoning": share.reasoning,
                "likes_count": share.likes_count or 0,
                "comments_count": share.comments_count or 0,
                "created_at": share.created_at.isoformat() if share.created_at else None,
            })

        return {"total": total, "page": page, "page_size": page_size, "data": result}

    # ==================== 排行榜 ====================

    @staticmethod
    def get_leaderboard(db: Session, period: str = "total", metric: str = "total_return",
                        page: int = 1, page_size: int = 20) -> dict:
        """
        获取排行榜（日/周/月/总，按收益率/胜率/交易数）

        Args:
            db: 数据库会话
            period: 时间周期 daily/weekly/monthly/total
            metric: 排行指标 total_return/win_rate/trade_count
            page: 页码
            page_size: 每页数量

        Returns:
            分页排行榜列表
        """
        query = db.query(UserProfile).filter(UserProfile.total_trades > 0)

        # 排序指标
        if metric == "win_rate":
            query = query.order_by(desc(UserProfile.win_rate))
        elif metric == "trade_count":
            query = query.order_by(desc(UserProfile.total_trades))
        else:
            # 默认按收益率（总盈亏）
            query = query.order_by(desc(UserProfile.total_pnl))

        total = query.count()
        profiles = query.offset((page - 1) * page_size).limit(page_size).all()

        result = []
        for idx, profile in enumerate(profiles):
            rank = (page - 1) * page_size + idx + 1
            user = db.query(User).filter(User.id == profile.user_id).first()
            if not user:
                continue

            # 根据指标设置排行值
            if metric == "win_rate":
                value = profile.win_rate or 0
            elif metric == "trade_count":
                value = profile.total_trades or 0
            else:
                value = profile.total_pnl or 0

            result.append({
                "rank": rank,
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "avatar_url": profile.avatar_url,
                "value": value,
                "total_trades": profile.total_trades or 0,
                "win_rate": profile.win_rate or 0,
                "total_pnl": profile.total_pnl or 0,
            })

        return {"total": total, "page": page, "page_size": page_size, "data": result}

    # ==================== 私信 ====================

    @staticmethod
    def send_message(db: Session, sender_id: int, receiver_id: int, content: str) -> dict:
        """
        发送私信

        Args:
            db: 数据库会话
            sender_id: 发送者ID
            receiver_id: 接收者ID
            content: 消息内容

        Returns:
            消息字典
        """
        if sender_id == receiver_id:
            raise ValueError("不能给自己发消息")

        # 验证接收者存在
        receiver = db.query(User).filter(User.id == receiver_id).first()
        if not receiver:
            raise ValueError("接收者不存在")

        message = PrivateMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        return {
            "id": message.id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": message.content,
            "is_read": False,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }

    @staticmethod
    def get_messages(db: Session, user_id: int, other_user_id: int,
                     page: int = 1, page_size: int = 50) -> dict:
        """
        获取与某用户的私信列表

        Args:
            db: 数据库会话
            user_id: 当前用户ID
            other_user_id: 对方用户ID
            page: 页码
            page_size: 每页数量

        Returns:
            分页消息列表
        """
        query = db.query(PrivateMessage).filter(
            or_(
                and_(PrivateMessage.sender_id == user_id, PrivateMessage.receiver_id == other_user_id),
                and_(PrivateMessage.sender_id == other_user_id, PrivateMessage.receiver_id == user_id),
            )
        )

        # 标记对方发来的未读消息为已读
        db.query(PrivateMessage).filter(
            PrivateMessage.sender_id == other_user_id,
            PrivateMessage.receiver_id == user_id,
            PrivateMessage.is_read == False
        ).update({"is_read": True})
        db.commit()

        total = query.count()
        messages = query.order_by(asc(PrivateMessage.created_at)).offset((page - 1) * page_size).limit(page_size).all()

        result = []
        for msg in messages:
            result.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "receiver_id": msg.receiver_id,
                "content": msg.content,
                "is_read": msg.is_read,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        return {"total": total, "page": page, "page_size": page_size, "data": result}

    @staticmethod
    def get_conversations(db: Session, user_id: int) -> list:
        """
        获取会话列表

        Args:
            db: 数据库会话
            user_id: 当前用户ID

        Returns:
            会话列表
        """
        # 获取与该用户相关的所有消息的对方用户ID
        subquery = db.query(
            PrivateMessage.sender_id.label("other_id"),
            func.max(PrivateMessage.created_at).label("last_time"),
        ).filter(
            PrivateMessage.receiver_id == user_id
        ).group_by(PrivateMessage.sender_id).subquery()

        subquery2 = db.query(
            PrivateMessage.receiver_id.label("other_id"),
            func.max(PrivateMessage.created_at).label("last_time"),
        ).filter(
            PrivateMessage.sender_id == user_id
        ).group_by(PrivateMessage.receiver_id).subquery()

        # 合并两个子查询
        from sqlalchemy import union_all
        combined = db.query(
            func.coalesce(subquery.c.other_id, subquery2.c.other_id).label("other_id"),
            func.max(func.coalesce(subquery.c.last_time, subquery2.c.last_time)).label("last_time"),
        ).select_from(
            func.coalesce(subquery.c.other_id, subquery2.c.other_id)
        ).group_by(
            func.coalesce(subquery.c.other_id, subquery2.c.other_id)
        ).all()

        conversations = []
        for row in combined:
            other_id = row.other_id
            other_user = db.query(User).filter(User.id == other_id).first()
            if not other_user:
                continue

            other_profile = db.query(UserProfile).filter(UserProfile.user_id == other_id).first()

            # 获取最后一条消息
            last_msg = db.query(PrivateMessage).filter(
                or_(
                    and_(PrivateMessage.sender_id == user_id, PrivateMessage.receiver_id == other_id),
                    and_(PrivateMessage.sender_id == other_id, PrivateMessage.receiver_id == user_id),
                )
            ).order_by(desc(PrivateMessage.created_at)).first()

            # 获取未读消息数
            unread_count = db.query(PrivateMessage).filter(
                PrivateMessage.sender_id == other_id,
                PrivateMessage.receiver_id == user_id,
                PrivateMessage.is_read == False
            ).count()

            conversations.append({
                "other_user_id": other_id,
                "other_user_name": other_user.username,
                "other_user_avatar": other_profile.avatar_url if other_profile else None,
                "last_message": last_msg.content if last_msg else None,
                "last_message_time": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
                "unread_count": unread_count,
            })

        # 按最后消息时间排序
        conversations.sort(key=lambda x: x["last_message_time"] or "", reverse=True)

        return conversations

    # ==================== 搜索 ====================

    @staticmethod
    def search_users(db: Session, query_str: str, page: int = 1, page_size: int = 20) -> dict:
        """
        搜索用户

        Args:
            db: 数据库会话
            query_str: 搜索关键词
            page: 页码
            page_size: 每页数量

        Returns:
            分页用户列表
        """
        query = db.query(User).filter(
            or_(
                User.username.ilike(f"%{query_str}%"),
                User.display_name.ilike(f"%{query_str}%"),
                User.email.ilike(f"%{query_str}%"),
            )
        )
        total = query.count()
        users = query.offset((page - 1) * page_size).limit(page_size).all()

        result = []
        for user in users:
            profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
            result.append({
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "avatar_url": profile.avatar_url if profile else None,
                "bio": profile.bio if profile else None,
                "expertise": profile.expertise if profile else None,
            })

        return {"total": total, "page": page, "page_size": page_size, "data": result}
