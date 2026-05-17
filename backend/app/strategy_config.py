"""
策略参数热更新服务

支持运行时动态修改策略参数，无需重启服务。
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """策略配置"""
    strategy_id: str
    strategy_name: str
    strategy_type: str  # a_stock_short_term, us_hk_options_event
    params: Dict[str, Any]
    version: int = 1
    updated_at: str = ""
    updated_by: str = "system"

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


@dataclass
class ConfigChange:
    """配置变更记录"""
    strategy_id: str
    param_name: str
    old_value: Any
    new_value: Any
    changed_at: str
    changed_by: str


class StrategyConfigManager:
    """
    策略参数管理器

    功能：
    - 存储策略参数
    - 验证参数合法性
    - 热更新参数
    - 记录参数变更历史
    """

    def __init__(self):
        # 策略配置存储: strategy_id -> StrategyConfig
        self._configs: Dict[str, StrategyConfig] = {}
        # 参数变更历史
        self._change_history: List[ConfigChange] = []
        # 参数验证器
        self._validators: Dict[str, Dict[str, tuple]] = {}

    def register_validator(self, strategy_type: str, param_rules: Dict[str, tuple]):
        """
        注册参数验证器

        Args:
            strategy_type: 策略类型
            param_rules: 参数规则 {param_name: (min, max, type)}
        """
        self._validators[strategy_type] = param_rules

    def set_config(self, config: StrategyConfig, updated_by: str = "system") -> bool:
        """
        设置策略配置（热更新）

        Returns:
            True 成功，False 失败（参数校验失败）
        """
        # 参数校验
        if not self._validate_params(config.strategy_type, config.params):
            return False

        # 获取旧配置
        old_config = self._configs.get(config.strategy_id)

        # 记录变更
        if old_config:
            for key, new_val in config.params.items():
                old_val = old_config.params.get(key)
                if old_val != new_val:
                    self._change_history.append(ConfigChange(
                        strategy_id=config.strategy_id,
                        param_name=key,
                        old_value=old_val,
                        new_value=new_val,
                        changed_at=datetime.now().isoformat(),
                        changed_by=updated_by
                    ))

        # 更新配置
        config.version = (old_config.version + 1) if old_config else 1
        config.updated_at = datetime.now().isoformat()
        config.updated_by = updated_by
        self._configs[config.strategy_id] = config

        logger.info(f"策略参数已更新: {config.strategy_id}, 版本: {config.version}")
        return True

    def get_config(self, strategy_id: str) -> Optional[StrategyConfig]:
        """获取策略配置"""
        return self._configs.get(strategy_id)

    def get_configs_by_type(self, strategy_type: str) -> List[StrategyConfig]:
        """获取指定类型的所有配置"""
        return [c for c in self._configs.values() if c.strategy_type == strategy_type]

    def get_all_configs(self) -> List[StrategyConfig]:
        """获取所有配置"""
        return list(self._configs.values())

    def _validate_params(self, strategy_type: str, params: Dict[str, Any]) -> bool:
        """验证参数"""
        if strategy_type not in self._validators:
            # 没有验证器，放行
            return True

        rules = self._validators[strategy_type]
        for param_name, value in params.items():
            if param_name not in rules:
                continue

            min_val, max_val, param_type = rules[param_name]

            # 类型检查
            if param_type == int:
                if not isinstance(value, int):
                    logger.error(f"参数 {param_name} 需要 int 类型")
                    return False
            elif param_type == float:
                if not isinstance(value, (int, float)):
                    logger.error(f"参数 {param_name} 需要 float 类型")
                    return False

            # 范围检查
            if min_val is not None and value < min_val:
                logger.error(f"参数 {param_name} 值 {value} 小于最小值 {min_val}")
                return False
            if max_val is not None and value > max_val:
                logger.error(f"参数 {param_name} 值 {value} 大于最大值 {max_val}")
                return False

        return True

    def get_change_history(self, strategy_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """获取参数变更历史"""
        history = self._change_history
        if strategy_id:
            history = [h for h in history if h.strategy_id == strategy_id]
        return [
            {
                "strategy_id": h.strategy_id,
                "param_name": h.param_name,
                "old_value": h.old_value,
                "new_value": h.new_value,
                "changed_at": h.changed_at,
                "changed_by": h.changed_by
            }
            for h in history[-limit:]
        ]

    def rollback(self, strategy_id: str, version: int) -> bool:
        """
        回滚到指定版本

        Note: 当前实现是简化版，完整实现需要版本存储
        """
        config = self._configs.get(strategy_id)
        if not config:
            return False

        logger.warning(f"参数回滚功能需要版本存储支持，当前仅记录回滚请求: {strategy_id} -> v{version}")
        return True


# 全局策略配置管理器
strategy_config_manager = StrategyConfigManager()


# ========== 默认验证规则 ==========

strategy_config_manager.register_validator("a_stock_short_term", {
    "min_daily_change": (0.0, 10.0, float),
    "max_daily_change": (0.0, 20.0, float),
    "volume_ratio_5d": (0.5, 5.0, float),
    "min_turnover": (0.0, 50.0, float),
    "max_turnover": (0.0, 100.0, float),
    "min_cap": (1e6, 1e12, float),
    "max_cap": (1e6, 1e12, float),
    "max_daily_select": (1, 20, int),
})

strategy_config_manager.register_validator("us_hk_options_event", {
    "max_premium_pct": (0.0, 50.0, float),
    "max_loss_pct": (0.0, 10.0, float),
    "min_iv_rank": (0.0, 100.0, float),
    "max_loss_per_strategy": (0.0, 5.0, float),
})