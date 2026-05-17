"""
股票池管理
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.data_types import StockScore
from .base import BaseSelector


class StockPool:
    """股票池管理器

    管理当前候选股票池，支持持久化存储
    """

    def __init__(self, storage_path: str = "storage/cache/stock_pool.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.scores: List[StockScore] = []
        self.last_update: Optional[datetime] = None
        self._load()

    def _load(self):
        """从文件加载"""
        if self.storage_path.exists():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.last_update = datetime.fromisoformat(data["last_update"])
                self.scores = [
                    StockScore(
                        symbol=s["symbol"],
                        score=s["score"],
                        factor_scores=s["factor_scores"],
                    )
                    for s in data["scores"]
                ]

    def save(self):
        """保存到文件"""
        data = {
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "scores": [
                {
                    "symbol": s.symbol,
                    "score": s.score,
                    "factor_scores": s.factor_scores,
                }
                for s in self.scores
            ],
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def update(self, selector: BaseSelector, universe: List[str]) -> List[StockScore]:
        """更新股票池

        Args:
            selector: 选股器
            universe: 全量候选股票列表

        Returns:
            筛选后的股票评分列表
        """
        self.scores = selector.filter(universe)
        self.last_update = datetime.now()
        self.save()
        return self.scores

    def get_symbols(self, top_n: Optional[int] = None) -> List[str]:
        """获取股票代码列表

        Args:
            top_n: 返回前n只，None返回全部

        Returns:
            股票代码列表
        """
        if top_n is None:
            return [s.symbol for s in self.scores]
        else:
            return [s.symbol for s in self.scores[:top_n]]

    def size(self) -> int:
        """当前股票池大小"""
        return len(self.scores)
