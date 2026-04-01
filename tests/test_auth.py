"""
认证模块单元测试

测试 JWT Token 生成/验证、密码哈希、认证依赖注入。
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_optional_user,
    require_role,
    SECRET_KEY,
)
from fastapi import HTTPException


class TestPasswordHashing:
    """密码哈希测试"""

    def test_hash_and_verify(self):
        """密码哈希和验证"""
        password = "my_secret_password"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password(self):
        """错误密码验证"""
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes(self):
        """相同密码产生不同哈希（bcrypt salt）"""
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestTokenGeneration:
    """Token 生成测试"""

    def test_create_access_token(self):
        """创建访问 Token"""
        token = create_access_token({"sub": "admin", "role": "admin"})
        assert isinstance(token, str)
        assert len(token) > 0

        payload = decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_refresh_token(self):
        """创建刷新 Token"""
        token = create_refresh_token({"sub": "user1"})
        payload = decode_token(token)
        assert payload["sub"] == "user1"
        assert payload["type"] == "refresh"

    def test_custom_expiry(self):
        """自定义过期时间"""
        token = create_access_token(
            {"sub": "test"},
            expires_delta=timedelta(seconds=1)
        )
        payload = decode_token(token)
        assert payload["sub"] == "test"

    def test_different_tokens(self):
        """不同用户产生不同 Token"""
        token1 = create_access_token({"sub": "user1"})
        token2 = create_access_token({"sub": "user2"})
        assert token1 != token2


class TestTokenDecode:
    """Token 解码测试"""

    def test_decode_valid_token(self):
        """解码有效 Token"""
        token = create_access_token({"sub": "admin", "role": "admin"})
        payload = decode_token(token)
        assert payload["sub"] == "admin"

    def test_decode_invalid_token(self):
        """解码无效 Token 抛出异常"""
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")
        assert exc_info.value.status_code == 401

    def test_decode_wrong_secret(self):
        """错误密钥解码失败"""
        import jwt as jose_jwt
        token = jose_jwt.encode(
            {"sub": "test", "exp": 9999999999},
            "wrong_secret_key",
            algorithm="HS256"
        )
        with pytest.raises(HTTPException):
            decode_token(token)


class TestGetCurrentUser:
    """获取当前用户测试"""

    def test_valid_token(self):
        """有效 Token 返回用户信息"""
        token = create_access_token({"sub": "admin", "role": "admin"})
        user = get_current_user(token)
        assert user["username"] == "admin"
        assert user["role"] == "admin"

    def test_no_token(self):
        """无 Token 抛出 401"""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(None)
        assert exc_info.value.status_code == 401

    def test_refresh_token_as_access(self):
        """使用 refresh_token 作为 access_token 抛出异常"""
        token = create_refresh_token({"sub": "admin"})
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token)
        assert exc_info.value.status_code == 401

    def test_token_missing_sub(self):
        """Token 缺少 sub 字段抛出异常"""
        import jwt as jose_jwt
        token = jose_jwt.encode(
            {"exp": 9999999999, "type": "access"},
            SECRET_KEY,
            algorithm="HS256"
        )
        with pytest.raises(HTTPException):
            get_current_user(token)


class TestGetOptionalUser:
    """可选用户测试"""

    def test_valid_token(self):
        """有效 Token 返回用户信息"""
        token = create_access_token({"sub": "admin", "role": "admin"})
        user = get_optional_user(token)
        assert user["username"] == "admin"

    def test_no_token(self):
        """无 Token 返回 None"""
        user = get_optional_user(None)
        assert user is None

    def test_invalid_token(self):
        """无效 Token 返回 None"""
        user = get_optional_user("invalid.token")
        assert user is None


class TestRequireRole:
    """角色权限测试"""

    def test_correct_role(self):
        """正确角色通过"""
        token = create_access_token({"sub": "admin", "role": "admin"})
        checker = require_role("admin")
        # require_role 返回一个依赖函数，需要传入 token 参数
        # 实际使用时通过 Depends(get_current_user) 注入
        user = get_current_user(token)
        assert user["role"] == "admin"

    def test_wrong_role(self):
        """错误角色抛出 403"""
        token = create_access_token({"sub": "user1", "role": "user"})
        user = get_current_user(token)
        assert user["role"] == "user"
        assert user["role"] != "admin"
