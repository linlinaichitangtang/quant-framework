"""
策略模板 API 端点
"""
import os
import uuid
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional

from .database import get_db
from . import crud, schemas
from .auth import get_optional_user

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("", response_model=schemas.PaginatedResponse[schemas.TemplateResponse])
def list_my_templates(
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """获取我的模板列表"""
    author_id = current_user.id if current_user else 0
    skip = (page - 1) * page_size
    data = crud.get_my_templates(db, author_id=author_id, category=category, skip=skip, limit=page_size)
    total = crud.count_my_templates(db, author_id=author_id, category=category)
    return schemas.PaginatedResponse(total=total, page=page, page_size=page_size, data=data)


@router.post("", response_model=schemas.TemplateResponse)
def save_template(
    template_in: schemas.TemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """保存为模板"""
    result = crud.create_template(
        db,
        name=template_in.name,
        description=template_in.description,
        category=template_in.category,
        cover_url=template_in.cover_url,
        author_id=current_user.id if current_user else None,
        author_name=current_user.username if current_user else "匿名",
        is_public=template_in.is_public,
        config=template_in.config,
    )
    return result


@router.put("/{template_id}", response_model=schemas.TemplateResponse)
def update_template(
    template_id: int,
    template_in: schemas.TemplateUpdate,
    db: Session = Depends(get_db),
):
    """更新模板"""
    result = crud.update_template(
        db, template_id,
        name=template_in.name,
        description=template_in.description,
        category=template_in.category,
        cover_url=template_in.cover_url,
        is_public=template_in.is_public,
        config=template_in.config,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return result


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    """删除模板（归档）"""
    result = crud.delete_template(db, template_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"message": f"模板 {template_id} 已删除"}


@router.post("/{template_id}/use", response_model=schemas.TemplateResponse)
def use_template(template_id: int, db: Session = Depends(get_db)):
    """使用模板（增加安装计数并返回配置）"""
    result = crud.install_template(db, template_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return result


@router.get("/market", response_model=schemas.PaginatedResponse[schemas.MarketTemplateResponse])
def list_market_templates(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("install_count", description="排序: install_count/rating/newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取模板市场列表"""
    skip = (page - 1) * page_size
    data = crud.get_market_templates(
        db, category=category, search=search, sort_by=sort_by, skip=skip, limit=page_size
    )
    total = crud.count_market_templates(db, category=category, search=search)
    return schemas.PaginatedResponse(total=total, page=page, page_size=page_size, data=data)


@router.post("/market/{template_id}/install", response_model=schemas.MarketTemplateResponse)
def install_market_template(template_id: int, db: Session = Depends(get_db)):
    """安装市场模板"""
    result = crud.install_template(db, template_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return result


@router.post("/market/{template_id}/rate")
def rate_market_template(
    template_id: int,
    rate_in: schemas.TemplateRateRequest,
    db: Session = Depends(get_db),
):
    """评分市场模板"""
    result = crud.rate_template(db, template_id, rate_in.score)
    if not result:
        raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
    return {"message": "评分成功", "rating_avg": result.rating_avg, "rating_count": result.rating_count}


@router.post("/cover")
async def upload_template_cover(file: UploadFile = File(...)):
    """上传模板封面图（简化实现：返回文件名）"""
    # 生产环境应上传到 OSS/S3，这里简化为返回文件名
    ext = os.path.splitext(file.filename)[1] if file.filename else ".png"
    filename = f"covers/{uuid.uuid4().hex}{ext}"
    # 模拟上传成功
    cover_url = f"/static/{filename}"
    return {"cover_url": cover_url}
