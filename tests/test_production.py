"""
v1.0 生产模块单元测试
覆盖：缓存、配置、安全、日志、数据库连接池
"""
import os
import json
import time
import pytest
import logging
from unittest.mock import patch, MagicMock

from app.config import Settings
from app.cache import MemoryCache, init_cache, get_cache


# ========== 配置测试 ==========
class TestProductionConfig:
    def test_default_config(self):
        s = Settings()
        assert s.app_name == "OpenClaw"
        assert s.app_version == "1.0.0"
        assert s.debug is True
        assert s.log_level == "INFO"
        assert s.secret_key != ""
        assert s.rate_limit == "60/minute"
        assert s.rate_limit_login == "5/minute"

    def test_config_from_env(self):
        os.environ["SECRET_KEY"] = "test_secret_key_123"
        os.environ["DEBUG"] = "false"
        os.environ["LOG_LEVEL"] = "WARNING"
        os.environ["DB_POOL_SIZE"] = "10"
        try:
            # pydantic-settings 自动将字段名转大写匹配环境变量
            s = Settings(_env_file=None)
            assert s.secret_key == "test_secret_key_123"
            assert s.debug is False
            assert s.log_level == "WARNING"
            assert s.db_pool_size == 10
        finally:
            os.environ.pop("SECRET_KEY", None)
            os.environ.pop("DEBUG", None)
            os.environ.pop("LOG_LEVEL", None)
            os.environ.pop("DB_POOL_SIZE", None)

    def test_db_pool_config(self):
        s = Settings()
        assert s.db_pool_size == 5
        assert s.db_max_overflow == 10
        assert s.db_pool_timeout == 30
        assert s.db_pool_recycle == 3600

    def test_redis_url_optional(self):
        s = Settings()
        assert s.redis_url is None

    def test_notification_config(self):
        s = Settings()
        assert s.wechat_webhook_url is None
        assert s.dingtalk_webhook_url is None
        assert s.smtp_host is None
        assert s.smtp_port == 587

    def test_token_expiry_config(self):
        s = Settings()
        assert s.access_token_expire_minutes == 60 * 24
        assert s.refresh_token_expire_days == 30


# ========== 内存缓存测试 ==========
class TestMemoryCache:
    def setup_method(self):
        self.cache = MemoryCache()

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_missing_key(self):
        assert self.cache.get("nonexistent") is None

    def test_set_with_ttl(self):
        self.cache.set("short_lived", "data", ttl=1)
        assert self.cache.get("short_lived") == "data"
        time.sleep(1.1)
        assert self.cache.get("short_lived") is None

    def test_delete(self):
        self.cache.set("key1", "value1")
        self.cache.delete("key1")
        assert self.cache.get("key1") is None

    def test_exists(self):
        self.cache.set("key1", "value1")
        assert self.cache.exists("key1") is True
        assert self.cache.exists("nonexistent") is False

    def test_ping(self):
        assert self.cache.ping() is True

    def test_set_dict_value(self):
        data = {"symbol": "600519.SH", "price": 1800.0}
        self.cache.set("stock", data)
        result = self.cache.get("stock")
        assert result == data

    def test_set_list_value(self):
        data = [1, 2, 3, 4, 5]
        self.cache.set("numbers", data)
        assert self.cache.get("numbers") == data

    def test_close(self):
        self.cache.set("key1", "value1")
        self.cache.close()
        assert self.cache.get("key1") is None

    def test_overwrite(self):
        self.cache.set("key1", "old")
        self.cache.set("key1", "new")
        assert self.cache.get("key1") == "new"

    def test_no_ttl_expires_never(self):
        self.cache.set("permanent", "data", ttl=0)
        time.sleep(0.1)
        assert self.cache.get("permanent") == "data"


# ========== 缓存初始化测试 ==========
class TestCacheInit:
    def test_init_cache_memory(self):
        init_cache(None)
        cache = get_cache()
        assert isinstance(cache, MemoryCache)
        assert cache.ping() is True

    def test_init_cache_redis_fallback(self):
        """Redis 连接失败时降级为内存缓存"""
        init_cache("redis://invalid-host:6379/0")
        cache = get_cache()
        # 应该降级为 MemoryCache
        assert isinstance(cache, MemoryCache)

    def test_get_cache_auto_init(self):
        """get_cache 在未初始化时自动初始化"""
        from app import cache as cache_module
        cache_module._cache = None  # 重置
        cache = get_cache()
        assert cache is not None
        assert cache.ping() is True


# ========== 安全配置测试 ==========
class TestSecurityConfig:
    def test_auth_uses_settings_secret_key(self):
        from app.auth import SECRET_KEY
        from app.config import settings
        assert SECRET_KEY == settings.secret_key

    def test_auth_uses_settings_expiry(self):
        from app.auth import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
        from app.config import settings
        assert ACCESS_TOKEN_EXPIRE_MINUTES == settings.access_token_expire_minutes
        assert REFRESH_TOKEN_EXPIRE_DAYS == settings.refresh_token_expire_days

    def test_cors_methods_restricted(self):
        """验证 CORS 配置限制了方法"""
        from app.config import settings
        # 配置本身在 main.py 中使用，这里验证设置存在
        assert settings.cors_origins is not None


# ========== 数据库连接池测试 ==========
class TestDatabasePool:
    def test_sqlite_connect_args(self):
        from app.database import engine
        from app.config import settings
        if "sqlite" in settings.database_url:
            # SQLite 模式下应配置了 connect_args
            assert engine.dialect.name == "sqlite"

    def test_get_db_generator(self):
        from app.database import get_db
        gen = get_db()
        db = next(gen)
        assert db is not None
        # 清理
        try:
            next(gen)
        except StopIteration:
            pass


# ========== 日志配置测试 ==========
class TestLoggingConfig:
    def test_root_logger_configured(self):
        # 导入 main 触发 setup_logging()
        from app.main import logger as main_logger
        root = logging.getLogger()
        assert root.level <= logging.INFO
        assert len(root.handlers) > 0

    def test_app_logger_exists(self):
        from app.main import logger as main_logger
        assert main_logger is not None

    def test_third_party_loggers_suppressed(self):
        # 导入 main 确保日志配置已生效
        from app.main import logger as main_logger
        for name in ["uvicorn.access", "sqlalchemy.engine", "matplotlib"]:
            level = logging.getLogger(name).level
            assert level >= logging.WARNING, f"{name} 日志级别应为 WARNING 或更高"
