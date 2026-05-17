"""
策略 DSL 引擎

支持通过 YAML/JSON 配置文件定义自定义策略。
"""

import logging
import yaml
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConditionOperator(Enum):
    """条件运算符"""
    GT = ">"   # 大于
    GTE = ">=" # 大于等于
    LT = "<"   # 小于
    LTE = "<=" # 小于等于
    EQ = "=="  # 等于
    NE = "!="  # 不等于
    IN = "in"  # 在列表中
    NOT_IN = "not_in"  # 不在列表中
    BETWEEN = "between"  # 在范围内


@dataclass
class Condition:
    """选股条件"""
    field: str  # 字段名
    operator: str  # 运算符
    value: Any  # 比较值
    description: str = ""  # 条件描述

    def evaluate(self, data: Dict[str, Any]) -> bool:
        """评估条件是否满足"""
        field_value = data.get(self.field)
        if field_value is None:
            return False

        op = ConditionOperator(self.operator) if self.operator in [e.value for e in ConditionOperator] else None

        if op is None:
            logger.warning(f"未知运算符: {self.operator}")
            return False

        try:
            if op == ConditionOperator.GT:
                return field_value > self.value
            elif op == ConditionOperator.GTE:
                return field_value >= self.value
            elif op == ConditionOperator.LT:
                return field_value < self.value
            elif op == ConditionOperator.LTE:
                return field_value <= self.value
            elif op == ConditionOperator.EQ:
                return field_value == self.value
            elif op == ConditionOperator.NE:
                return field_value != self.value
            elif op == ConditionOperator.IN:
                return field_value in self.value
            elif op == ConditionOperator.NOT_IN:
                return field_value not in self.value
            elif op == ConditionOperator.BETWEEN:
                # value 应该是 [min, max]
                if isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                    return self.value[0] <= field_value <= self.value[1]
                return False
        except Exception as e:
            logger.error(f"条件评估异常: {self}, error: {e}")
            return False

        return False


@dataclass
class CompositeCondition:
    """复合条件（AND/OR）"""
    conditions: List  # 条件列表
    logic: str = "AND"  # AND / OR

    def evaluate(self, data: Dict[str, Any]) -> bool:
        if self.logic == "AND":
            return all(c.evaluate(data) if hasattr(c, 'evaluate') else True for c in self.conditions)
        elif self.logic == "OR":
            return any(c.evaluate(data) if hasattr(c, 'evaluate') else False for c in self.conditions)
        return False


@dataclass
class SignalAction:
    """信号动作"""
    action: str  # buy / sell
    quantity_type: str = "all"  # all / fixed / percent
    quantity_value: Any = None  # 数量（根据 quantity_type 含义不同）


@dataclass
class StrategyDSL:
    """策略 DSL 定义"""
    name: str
    version: str
    description: str
    market: str  # A / HK / US
    selection: CompositeCondition  # 选股条件
    risk: Dict[str, Any]  # 风控参数
    actions: List[SignalAction]  # 信号动作


class DSLEvaluator:
    """
    DSL 评估器

    将 DSL 配置转换为可执行的策略逻辑。
    """

    def __init__(self):
        self._strategy_cache: Dict[str, StrategyDSL] = {}

    def load_from_yaml(self, yaml_str: str) -> StrategyDSL:
        """从 YAML 字符串加载策略"""
        config = yaml.safe_load(yaml_str)
        return self._parse_config(config)

    def load_from_json(self, json_str: str) -> StrategyDSL:
        """从 JSON 字符串加载策略"""
        config = json.loads(json_str)
        return self._parse_config(config)

    def load_from_dict(self, config: Dict) -> StrategyDSL:
        """从字典加载策略"""
        return self._parse_config(config)

    def _parse_config(self, config: Dict) -> StrategyDSL:
        """解析配置字典"""
        # 解析选股条件
        selection_config = config.get("selection", {})
        conditions = []

        for cond_def in selection_config.get("conditions", []):
            condition = self._parse_condition(cond_def)
            if condition:
                conditions.append(condition)

        selection = CompositeCondition(
            conditions=conditions,
            logic=selection_config.get("logic", "AND")
        )

        # 解析信号动作
        actions = []
        for action_def in config.get("actions", []):
            actions.append(SignalAction(
                action=action_def.get("action", "buy"),
                quantity_type=action_def.get("quantity_type", "all"),
                quantity_value=action_def.get("quantity_value")
            ))

        return StrategyDSL(
            name=config.get("name", "Unnamed Strategy"),
            version=config.get("version", "1.0"),
            description=config.get("description", ""),
            market=config.get("market", "A"),
            selection=selection,
            risk=config.get("risk", {}),
            actions=actions
        )

    def _parse_condition(self, cond_def: Dict) -> Optional[Condition]:
        """解析单个条件"""
        field = cond_def.get("field")
        operator = cond_def.get("operator", ">")
        value = cond_def.get("value")
        description = cond_def.get("description", f"{field} {operator} {value}")

        if not field:
            return None

        return Condition(
            field=field,
            operator=operator,
            value=value,
            description=description
        )

    def evaluate(self, strategy: StrategyDSL, data: Dict[str, Any]) -> bool:
        """评估股票数据是否满足策略条件"""
        return strategy.selection.evaluate(data)

    def generate_signal(self, strategy: StrategyDSL, data: Dict[str, Any]) -> Optional[Dict]:
        """
        生成交易信号

        Returns:
            信号字典，包含 action, quantity, reason 等
        """
        if not self.evaluate(strategy, data):
            return None

        # 收集匹配的条件
        matched_conditions = []
        for cond in strategy.selection.conditions:
            if hasattr(cond, 'evaluate') and cond.evaluate(data):
                matched_conditions.append(cond.description if hasattr(cond, 'description') else str(cond))

        # 构建信号
        reason = "; ".join(matched_conditions) if matched_conditions else "策略条件触发"

        # 确定动作（如果有多个动作，取第一个）
        action = strategy.actions[0] if strategy.actions else SignalAction(action="buy")

        return {
            "action": action.action,
            "symbol": data.get("symbol"),
            "market": strategy.market,
            "reason": reason,
            "matched_conditions": matched_conditions,
            "strategy_name": strategy.name,
            "risk_params": strategy.risk
        }

    def cache_strategy(self, strategy_id: str, strategy: StrategyDSL):
        """缓存策略"""
        self._strategy_cache[strategy_id] = strategy
        logger.info(f"策略已缓存: {strategy_id}")

    def get_cached_strategy(self, strategy_id: str) -> Optional[StrategyDSL]:
        """获取缓存的策略"""
        return self._strategy_cache.get(strategy_id)

    def remove_cached_strategy(self, strategy_id: str):
        """移除缓存的策略"""
        if strategy_id in self._strategy_cache:
            del self._strategy_cache[strategy_id]


# 全局 DSL 评估器实例
dsl_evaluator = DSLEvaluator()


# ========== 预定义策略模板 ==========

A_STOCK_SHORT_TERM_TEMPLATE = """
name: A股超短策略模板
version: 1.0
description: 基于技术指标的A股超短选股策略
market: A

selection:
  logic: AND
  conditions:
    - field: change_pct
      operator: between
      value: [3, 8]
      description: 涨幅 3%~8%
    - field: volume_ratio
      operator: ">="
      value: 1.5
      description: 量比 >= 1.5
    - field: turnover
      operator: between
      value: [3, 20]
      description: 换手率 3%~20%
    - field: close
      operator: ">"
      value: 10
      description: 股价大于10元
    - field: is_st
      operator: "=="
      value: false
      description: 非ST股票

risk:
  stop_profit_pct: 2.0
  stop_loss_pct: 2.0
  max_position_pct: 10
  max_daily_positions: 5

actions:
  - action: buy
    quantity_type: fixed
    quantity_value: 100
"""

OPTIONS_EVENT_TEMPLATE = """
name: 期权事件驱动策略模板
version: 1.0
description: 基于财报事件的期权策略
market: US

selection:
  logic: AND
  conditions:
    - field: event_type
      operator: in
      value: ["earnings_beat", "product_launch"]
      description: 利好事件
    - field: implied_volatility
      operator: "<="
      value: 30
      description: IV低于30%

risk:
  max_premium_pct: 5.0
  max_loss_pct: 3.0

actions:
  - action: buy
    quantity_type: percent
    quantity_value: 5
"""