"""
缓存模块 — 支持 Redis（生产）和内存缓存（开发）自动降级
"""
import json
import time
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class MemoryCache:
    """内存缓存实现（开发环境降级方案）"""

    def __init__(self):
        self._store: dict = {}

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        if item["expire"] > 0 and time.time() > item["expire"]:
            del self._store[key]
            return None
        return item["value"]

    def set(self, key: str, value: Any, ttl: int = 300):
        expire = time.time() + ttl if ttl > 0 else 0
        self._store[key] = {"value": value, "expire": expire}

    def delete(self, key: str):
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def ping(self) -> bool:
        return True

    def close(self):
        self._store.clear()


class RedisCache:
    """Redis 缓存实现"""

    def __init__(self, redis_url: str):
        try:
            import redis
            self._client = redis.from_url(redis_url, decode_responses=True)
            self._client.ping()
            logger.info(f"Redis 缓存已连接: {redis_url}")
        except Exception as e:
            logger.warning(f"Redis 连接失败，降级为内存缓存: {e}")
            raise  # 抛出异常，由 init_cache 处理降级

    def _ensure_client(self):
        if self._client is None:
            raise RuntimeError("Redis 未连接")
        return self._client

    def get(self, key: str) -> Optional[Any]:
        try:
            client = self._ensure_client()
            val = client.get(key)
            if val is None:
                return None
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 300):
        try:
            client = self._ensure_client()
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            client.setex(key, ttl, str(value))
        except Exception as e:
            logger.debug(f"Redis set 失败: {e}")

    def delete(self, key: str):
        try:
            self._ensure_client().delete(key)
        except Exception:
            pass

    def exists(self, key: str) -> bool:
        try:
            return bool(self._ensure_client().exists(key))
        except Exception:
            return False

    def ping(self) -> bool:
        try:
            return self._ensure_client().ping()
        except Exception:
            return False

    def close(self):
        if self._client:
            self._client.close()


# 全局缓存实例
_cache: Optional[MemoryCache] = None


def init_cache(redis_url: Optional[str] = None):
    """初始化缓存"""
    global _cache
    if redis_url:
        try:
            _cache = RedisCache(redis_url)
        except Exception:
            _cache = MemoryCache()
            logger.info("Redis 不可用，已降级为内存缓存")
    else:
        _cache = MemoryCache()
        logger.info("使用内存缓存（开发模式）")


def get_cache() -> MemoryCache:
    """获取缓存实例"""
    global _cache
    if _cache is None:
        init_cache()
    return _cache
