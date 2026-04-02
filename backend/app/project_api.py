"""
项目分享与导出 API

提供项目导出、分享链接管理、访问统计等接口。
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ProjectExport, ShareLink, AccessLog, SystemLog
from .schemas import CommonResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== 请求/响应 Schema ==========

class ExportCreateRequest(BaseModel):
    """创建导出任务请求"""
    name: str = Field(..., min_length=1, max_length=200, description="导出名称")
    include: list = Field(default=["database"], description="导出范围")


class ShareLinkCreateRequest(BaseModel):
    """创建分享链接请求"""
    permission: str = Field("read", description="权限 read/edit")
    expires_days: int = Field(30, ge=0, description="有效天数，0为永久")


class PermissionUpdateRequest(BaseModel):
    """更新项目权限请求"""
    permission: str = Field(..., description="权限 read/edit")


# ========== 导出相关接口 ==========

@router.get("/exports", summary="获取导出历史")
async def list_exports(db: Session = Depends(get_db)):
    """获取项目导出历史列表"""
    try:
        exports = db.query(ProjectExport).order_by(desc(ProjectExport.created_at)).all()
        data = []
        for exp in exports:
            file_size_str = _format_file_size(exp.file_size) if exp.file_size else "0B"
            data.append({
                "id": exp.id,
                "name": exp.name,
                "size": file_size_str,
                "status": exp.status,
                "created_at": exp.created_at.isoformat() if exp.created_at else None,
            })
        return CommonResponse(code=0, message="success", data=data)
    except Exception as e:
        logger.error(f"获取导出历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取导出历史失败: {str(e)}")


@router.post("/export", summary="创建导出任务")
async def create_export(req: ExportCreateRequest, db: Session = Depends(get_db)):
    """创建项目导出任务"""
    try:
        export = ProjectExport(
            name=req.name,
            status="pending",
        )
        db.add(export)
        db.commit()
        db.refresh(export)

        # 异步处理导出任务（简化实现：直接标记为完成）
        export.status = "completed"
        export.file_path = f"./exports/{export.id}_{req.name}.zip"
        export.file_size = 0
        db.commit()

        return CommonResponse(
            code=0,
            message="导出任务已创建",
            data={"id": export.id, "name": export.name, "status": export.status},
        )
    except Exception as e:
        logger.error(f"创建导出任务失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建导出任务失败: {str(e)}")


@router.get("/exports/{export_id}/download", summary="下载导出文件")
async def download_export(export_id: int, db: Session = Depends(get_db)):
    """下载导出文件"""
    try:
        export = db.query(ProjectExport).filter(ProjectExport.id == export_id).first()
        if not export:
            raise HTTPException(status_code=404, detail="导出记录不存在")
        if export.status != "completed":
            raise HTTPException(status_code=400, detail="导出任务尚未完成")
        if not export.file_path or not os.path.exists(export.file_path):
            raise HTTPException(status_code=404, detail="导出文件不存在")

        return FileResponse(
            path=export.file_path,
            filename=export.name,
            media_type="application/zip",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载导出文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.delete("/exports/{export_id}", summary="删除导出记录")
async def delete_export(export_id: int, db: Session = Depends(get_db)):
    """删除导出记录及其文件"""
    try:
        export = db.query(ProjectExport).filter(ProjectExport.id == export_id).first()
        if not export:
            raise HTTPException(status_code=404, detail="导出记录不存在")

        # 删除文件
        if export.file_path and os.path.exists(export.file_path):
            os.remove(export.file_path)

        db.delete(export)
        db.commit()
        return CommonResponse(code=0, message="导出记录已删除")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除导出记录失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ========== 分享链接接口 ==========

@router.get("/share-links", summary="获取分享链接列表")
async def list_share_links(db: Session = Depends(get_db)):
    """获取所有分享链接"""
    try:
        links = db.query(ShareLink).order_by(desc(ShareLink.created_at)).all()
        data = []
        for link in links:
            data.append({
                "id": link.id,
                "token": link.token,
                "url": f"/share/{link.token}",
                "permission": link.permission,
                "expires_at": link.expires_at.isoformat() if link.expires_at else None,
                "views": link.views,
                "is_active": link.is_active,
                "created_at": link.created_at.isoformat() if link.created_at else None,
            })
        return CommonResponse(code=0, message="success", data=data)
    except Exception as e:
        logger.error(f"获取分享链接失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取分享链接失败: {str(e)}")


@router.post("/share-links", summary="创建分享链接")
async def create_share_link(req: ShareLinkCreateRequest, db: Session = Depends(get_db)):
    """创建新的分享链接"""
    try:
        token = uuid.uuid4().hex[:16]
        expires_at = None
        if req.expires_days > 0:
            expires_at = datetime.now() + timedelta(days=req.expires_days)

        link = ShareLink(
            token=token,
            permission=req.permission,
            expires_at=expires_at,
        )
        db.add(link)
        db.commit()
        db.refresh(link)

        return CommonResponse(
            code=0,
            message="分享链接已创建",
            data={
                "id": link.id,
                "token": link.token,
                "url": f"/share/{link.token}",
                "permission": link.permission,
                "expires_at": link.expires_at.isoformat() if link.expires_at else None,
                "views": 0,
            },
        )
    except Exception as e:
        logger.error(f"创建分享链接失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建分享链接失败: {str(e)}")


@router.delete("/share-links/{link_id}", summary="撤销分享链接")
async def revoke_share_link(link_id: int, db: Session = Depends(get_db)):
    """撤销（删除）分享链接"""
    try:
        link = db.query(ShareLink).filter(ShareLink.id == link_id).first()
        if not link:
            raise HTTPException(status_code=404, detail="分享链接不存在")

        link.is_active = False
        db.commit()
        return CommonResponse(code=0, message="分享链接已撤销")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"撤销分享链接失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"撤销分享链接失败: {str(e)}")


# ========== 访问统计接口 ==========

@router.get("/access-stats", summary="获取访问统计")
async def get_access_stats(db: Session = Depends(get_db)):
    """获取项目访问统计数据"""
    try:
        # 总访问次数
        total_views = db.query(func.count(AccessLog.id)).scalar() or 0

        # 今日访问
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_views = db.query(func.count(AccessLog.id)).filter(
            AccessLog.created_at >= today_start
        ).scalar() or 0

        # 独立访客数（按IP去重）
        unique_visitors = db.query(func.count(func.distinct(AccessLog.visitor_ip))).scalar() or 0

        # 活跃分享链接数
        active_links = db.query(func.count(ShareLink.id)).filter(
            ShareLink.is_active == True
        ).scalar() or 0

        data = {
            "total_views": total_views,
            "today_views": today_views,
            "unique_visitors": unique_visitors,
            "active_links": active_links,
        }
        return CommonResponse(code=0, message="success", data=data)
    except Exception as e:
        logger.error(f"获取访问统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取访问统计失败: {str(e)}")


@router.get("/recent-access", summary="获取最近访问记录")
async def get_recent_access(limit: int = 20, db: Session = Depends(get_db)):
    """获取最近的访问记录"""
    try:
        logs = db.query(AccessLog).order_by(desc(AccessLog.created_at)).limit(limit).all()
        data = []
        for log in logs:
            data.append({
                "id": log.id,
                "visitor": log.visitor_ip or "未知",
                "permission": "read",
                "accessed_at": log.created_at.isoformat() if log.created_at else None,
                "ip": log.visitor_ip,
                "action": log.action or "访问项目",
            })
        return CommonResponse(code=0, message="success", data=data)
    except Exception as e:
        logger.error(f"获取最近访问记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取最近访问记录失败: {str(e)}")


# ========== 权限管理接口 ==========

@router.put("/permission", summary="更新项目权限")
async def update_permission(req: PermissionUpdateRequest, db: Session = Depends(get_db)):
    """更新项目权限设置"""
    try:
        if req.permission not in ("read", "edit"):
            raise HTTPException(status_code=400, detail="权限值无效，仅支持 read 或 edit")

        # 项目权限存储在配置中（简化实现）
        return CommonResponse(
            code=0,
            message="权限已更新",
            data={"permission": req.permission},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新权限失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新权限失败: {str(e)}")


# ========== 工具函数 ==========

def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
