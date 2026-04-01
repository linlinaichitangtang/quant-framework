"""
认证 API 路由

提供注册、登录、Token 刷新、用户信息管理等接口。
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from . import crud, schemas
from .auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    require_role,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=schemas.UserResponse)
def register(user_data: schemas.UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    if crud.get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 检查邮箱是否已存在
    if crud.get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已注册"
        )

    # 创建用户
    hashed_password = get_password_hash(user_data.password)
    user = crud.create_user(
        db=db,
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        display_name=user_data.display_name,
    )

    return user


@router.post("/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """用户登录，返回 access_token 和 refresh_token"""
    user = crud.get_user_by_username(db, credentials.username)

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已禁用",
        )

    # 更新最后登录时间
    crud.update_user_last_login(db, user.id)

    # 生成 Token
    token_data = {"sub": user.username, "role": user.role.value}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh_token(request: schemas.RefreshTokenRequest):
    """使用 refresh_token 刷新 access_token"""
    payload = decode_token(request.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 类型错误",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
        )

    # 生成新的 access_token
    token_data = {"sub": username, "role": payload.get("role", "user")}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return schemas.TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前登录用户信息"""
    user = crud.get_user_by_username(db, current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/me", response_model=schemas.UserResponse)
def update_current_user(
    user_update: schemas.UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新当前用户信息"""
    user = crud.get_user_by_username(db, current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    updated_user = crud.update_user(db, user.id, **update_data)
    return updated_user


@router.post("/change-password")
def change_password(
    request: schemas.ChangePassword,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    user = crud.get_user_by_username(db, current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(request.old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )

    crud.update_user(db, user.id, hashed_password=get_password_hash(request.new_password))
    return {"message": "密码修改成功"}


# ========== 管理员接口 ==========
@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(current_user: dict = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """获取用户列表（管理员）"""
    return crud.get_users(db)


@router.put("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    current_user: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):
    """启用/禁用用户（管理员）"""
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    crud.update_user(db, user_id, is_active=not user.is_active)
    return {"message": f"用户已{'启用' if not user.is_active else '禁用'}"}
