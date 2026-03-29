"""
数据缓存模块
把获取到的数据缓存到本地磁盘，避免重复调用API浪费积分
"""
import os
import pickle
from typing import Any, Optional
from pathlib import Path
import pandas as pd


class DataCache:
    """磁盘数据缓存"""
    
    def __init__(self, cache_dir: str):
        """
        初始化
        
        Args:
            cache_dir: 缓存目录
        """
        self.cache_dir = Path(cache_dir).expanduser().absolute()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        # 用key作为文件名，替换不合法字符
        safe_key = key.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.pkl"
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
        
        Returns:
            缓存的数据，如果不存在返回None
        """
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"读取缓存失败 {key}: {e}")
            return None
    
    def set(self, key: str, value: Any) -> None:
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 要缓存的数据
        """
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            print(f"写入缓存失败 {key}: {e}")
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            return True
        return False
    
    def clear_all(self) -> None:
        """清空所有缓存"""
        for f in self.cache_dir.glob("*.pkl"):
            f.unlink()
