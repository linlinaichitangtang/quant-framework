"""
强化学习交易环境

提供 OpenAI Gym 兼容的交易环境，支持 DQN/PPO 等强化学习算法。
"""

import gym
from gym import spaces
import numpy as np
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TradingState:
    """交易状态"""
    cash: float              # 现金
    position: float          # 持仓数量
    stock_price: float       # 当前股价
    portfolio_value: float   # 组合价值
    price_history: np.ndarray  # 价格历史
    position_history: np.ndarray  # 持仓历史
    date: str                # 当前日期


class TradingEnvironment(gym.Env):
    """
    交易强化学习环境

    兼容 OpenAI Gym 接口，可用于训练 DQN、PPO 等强化学习策略。

    观察空间 (Observation Space):
        - 归一化价格 (过去 N 天)
        - 归一化持仓 (0-1)
        - 归一化现金比例

    动作空间 (Action Space):
        - 离散: 0=卖出, 1=持有, 2=买入
        - 或连续: -1 到 1 (归一化仓位)

    奖励 (Reward):
        - 每日收益率
        - 或组合价值变化
    """

    metadata = {'render.modes': ['human', 'array']}

    def __init__(
        self,
        prices: np.ndarray,  # 价格序列
        initial_cash: float = 10000.0,
        transaction_cost: float = 0.001,  # 交易成本
        window_size: int = 10,  # 价格窗口大小
        discrete_actions: bool = True,
        reward_type: str = "returns",  # returns / portfolio
        max_position: float = 1.0,  # 最大持仓比例
    ):
        super().__init__()

        self.prices = prices
        self.initial_cash = initial_cash
        self.transaction_cost = transaction_cost
        self.window_size = window_size
        self.discrete_actions = discrete_actions
        self.reward_type = reward_type
        self.max_position = max_position

        # 动作空间
        if discrete_actions:
            self.action_space = spaces.Discrete(3)  # 0=卖出, 1=持有, 2=买入
        else:
            self.action_space = spaces.Box(low=-1, high=1, shape=(1,), dtype=np.float32)

        # 观察空间: window_size 价格 + 持仓 + 现金比例
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(window_size + 2,), dtype=np.float32
        )

        self._current_step = 0
        self._cash = initial_cash
        self._position = 0.0
        self._portfolio_values = []

    def reset(self) -> np.ndarray:
        """重置环境"""
        self._current_step = self.window_size
        self._cash = self.initial_cash
        self._position = 0.0
        self._portfolio_values = [self.initial_cash]
        return self._get_observation()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        执行一步

        Args:
            action: 动作 (离散: 0/1/2, 连续: -1~1)

        Returns:
            observation, reward, done, info
        """
        # 获取当前价格
        current_price = self.prices[self._current_step]
        prev_price = self.prices[self._current_step - 1] if self._current_step > 0 else current_price

        # 执行动作
        if self.discrete_actions:
            self._execute_discrete_action(action, current_price)
        else:
            self._execute_continuous_action(action[0], current_price)

        # 更新步骤
        self._current_step += 1

        # 计算奖励
        reward = self._calculate_reward()

        # 检查结束
        done = self._current_step >= len(self.prices) - 1

        # 记录组合价值
        portfolio_value = self._get_portfolio_value(current_price)
        self._portfolio_values.append(portfolio_value)

        info = {
            'portfolio_value': portfolio_value,
            'cash': self._cash,
            'position': self._position,
            'price': current_price,
            'step': self._current_step,
        }

        return self._get_observation(), reward, done, info

    def _execute_discrete_action(self, action: int, price: float):
        """执行离散动作"""
        if action == 0:  # 卖出
            if self._position > 0:
                self._sell(self._position, price)
        elif action == 2:  # 买入
            # 全仓买入
            target_value = self._cash / (1 + self.transaction_cost)
            shares_to_buy = int(target_value / price)
            if shares_to_buy > 0:
                self._buy(shares_to_buy, price)

        # action == 1 表示持有，什么都不做

    def _execute_continuous_action(self, action: float, price: float):
        """
        执行连续动作

        action: -1 到 1，-1=全空，0=不动，1=全仓
        """
        # 目标持仓比例
        target_position_ratio = (action + 1) / 2 * self.max_position  # 0 ~ max_position

        # 当前组合价值
        portfolio_value = self._get_portfolio_value(price)
        target_position_value = portfolio_value * target_position_ratio
        current_position_value = self._position * price

        # 需要调整的金额
        delta_value = target_position_value - current_position_value

        if delta_value > 0:  # 买入
            shares_to_buy = int(delta_value / (price * (1 + self.transaction_cost)))
            if shares_to_buy > 0:
                self._buy(shares_to_buy, price)
        elif delta_value < 0:  # 卖出
            shares_to_sell = int(-delta_value / price)
            if shares_to_sell > 0:
                self._sell(min(shares_to_sell, self._position), price)

    def _buy(self, shares: int, price: float):
        """买入"""
        cost = shares * price * (1 + self.transaction_cost)
        if cost <= self._cash:
            self._cash -= cost
            self._position += shares

    def _sell(self, shares: int, price: float):
        """卖出"""
        if shares <= self._position:
            revenue = shares * price * (1 - self.transaction_cost)
            self._cash += revenue
            self._position -= shares

    def _get_portfolio_value(self, price: float) -> float:
        """获取组合价值"""
        return self._cash + self._position * price

    def _calculate_reward(self) -> float:
        """计算奖励"""
        if self.reward_type == "returns":
            # 每日收益率
            current_price = self.prices[self._current_step]
            prev_price = self.prices[self._current_step - 1]
            portfolio_value = self._get_portfolio_value(current_price)
            prev_portfolio_value = self._portfolio_values[-1] if self._portfolio_values else portfolio_value

            if prev_portfolio_value > 0:
                return (portfolio_value - prev_portfolio_value) / prev_portfolio_value
            return 0.0

        elif self.reward_type == "portfolio":
            # 组合价值变化
            current_price = self.prices[self._current_step]
            portfolio_value = self._get_portfolio_value(current_price)
            prev_portfolio_value = self._portfolio_values[-1] if self._portfolio_values else self.initial_cash
            return portfolio_value - prev_portfolio_value

        else:
            return 0.0

    def _get_observation(self) -> np.ndarray:
        """获取观察"""
        # 价格历史（归一化）
        start_idx = max(0, self._current_step - self.window_size + 1)
        end_idx = self._current_step + 1
        price_window = self.prices[start_idx:end_idx]

        # 填充到 window_size
        if len(price_window) < self.window_size:
            price_window = np.concatenate([
                np.zeros(self.window_size - len(price_window)),
                price_window
            ])

        # 归一化价格
        max_price = np.max(self.prices) if len(self.prices) > 0 else 1.0
        normalized_prices = price_window / max_price if max_price > 0 else price_window

        # 归一化持仓
        portfolio_value = self._get_portfolio_value(self.prices[self._current_step])
        normalized_position = self._position * self.prices[self._current_step] / portfolio_value if portfolio_value > 0 else 0

        # 现金比例
        cash_ratio = self._cash / portfolio_value if portfolio_value > 0 else 1.0

        return np.concatenate([
            normalized_prices,
            [normalized_position, cash_ratio]
        ]).astype(np.float32)

    def render(self, mode='human'):
        """渲染"""
        if mode == 'human':
            current_price = self.prices[self._current_step]
            portfolio_value = self._get_portfolio_value(current_price)
            print(f"Step: {self._current_step}, Price: {current_price:.2f}, "
                  f"Position: {self._position}, Cash: {self._cash:.2f}, "
                  f"Portfolio: {portfolio_value:.2f}")
        elif mode == 'array':
            return self._get_observation()

    def close(self):
        """关闭环境"""
        pass

    @property
    def sharpe_ratio(self) -> float:
        """计算夏普比率"""
        if len(self._portfolio_values) < 2:
            return 0.0

        returns = np.diff(self._portfolio_values) / self._portfolio_values[:-1]
        if np.std(returns) == 0:
            return 0.0

        return np.mean(returns) / np.std(returns) * np.sqrt(252)

    @property
    def max_drawdown(self) -> float:
        """计算最大回撤"""
        if len(self._portfolio_values) < 2:
            return 0.0

        peak = np.maximum.accumulate(self._portfolio_values)
        drawdown = (self._portfolio_values - peak) / peak
        return np.min(drawdown)


class MultiAssetTradingEnvironment(TradingEnvironment):
    """
    多资产交易环境

    支持多个资产同时交易。
    """

    def __init__(
        self,
        prices: np.ndarray,  # (n_steps, n_assets)
        initial_cash: float = 10000.0,
        transaction_cost: float = 0.001,
        window_size: int = 10,
        reward_type: str = "returns",
        n_positions: int = 3,  # 最多同时持仓资产数
    ):
        self.n_assets = prices.shape[1] if len(prices.shape) > 1 else 1
        self.n_positions = n_positions

        super().__init__(
            prices=prices,
            initial_cash=initial_cash,
            transaction_cost=transaction_cost,
            window_size=window_size,
            discrete_actions=False,  # 多资产需要连续动作
            reward_type=reward_type
        )

        # 动作空间: 每个资产的持仓比例 (-1 到 1)
        self.action_space = spaces.Box(
            low=-1, high=1, shape=(self.n_assets,), dtype=np.float32
        )

        # 观察空间: 所有资产价格 + 现金比例
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(window_size * self.n_assets + 1,), dtype=np.float32
        )

        self._positions = np.zeros(self.n_assets)

    def reset(self) -> np.ndarray:
        """重置环境"""
        self._current_step = self.window_size
        self._cash = self.initial_cash
        self._positions = np.zeros(self.n_assets)
        self._portfolio_values = [self.initial_cash]
        return self._get_observation()

    def _execute_continuous_action(self, actions: np.ndarray, prices: np.ndarray):
        """执行多资产动作"""
        for i, action in enumerate(actions):
            if self.n_assets == 1:
                price = prices
            else:
                price = prices[i]

            # 目标持仓比例
            target_ratio = (action + 1) / 2 * self.max_position
            portfolio_value = self._get_portfolio_value(prices)
            target_value = portfolio_value * target_ratio
            current_value = self._positions[i] * price
            delta_value = target_value - current_value

            if delta_value > 0:
                shares = int(delta_value / (price * (1 + self.transaction_cost)))
                self._buy(shares, price, asset_idx=i)
            elif delta_value < 0:
                shares = int(-delta_value / price)
                self._sell(min(shares, self._positions[i]), price, asset_idx=i)

    def _buy(self, shares: int, price: float, asset_idx: int = 0):
        cost = shares * price * (1 + self.transaction_cost)
        if cost <= self._cash:
            self._cash -= cost
            self._positions[asset_idx] += shares

    def _sell(self, shares: int, price: float, asset_idx: int = 0):
        if shares <= self._positions[asset_idx]:
            revenue = shares * price * (1 - self.transaction_cost)
            self._cash += revenue
            self._positions[asset_idx] -= shares

    def _get_portfolio_value(self, prices: np.ndarray) -> float:
        if self.n_assets == 1:
            return self._cash + self._positions[0] * prices
        else:
            position_value = np.sum(self._positions * prices)
            return self._cash + position_value

    def _get_observation(self) -> np.ndarray:
        obs_parts = []

        for i in range(self.n_assets):
            if self.n_assets == 1:
                price_series = self.prices
            else:
                price_series = self.prices[:, i]

            start_idx = max(0, self._current_step - self.window_size + 1)
            end_idx = self._current_step + 1
            window = price_series[start_idx:end_idx]

            if len(window) < self.window_size:
                window = np.concatenate([np.zeros(self.window_size - len(window)), window])

            max_price = np.max(price_series) if len(price_series) > 0 else 1.0
            normalized = window / max_price if max_price > 0 else window
            obs_parts.append(normalized)

        # 添加现金比例
        if self.n_assets > 1:
            prices = self.prices[self._current_step] if len(self.prices.shape) > 1 else self.prices[self._current_step]
        else:
            prices = self.prices[self._current_step]

        portfolio_value = self._get_portfolio_value(prices)
        cash_ratio = self._cash / portfolio_value if portfolio_value > 0 else 1.0
        obs_parts.append(np.array([cash_ratio]))

        return np.concatenate(obs_parts).astype(np.float32)


# ========== Gym 注册函数 ==========

def register_trading_gym():
    """注册交易环境到 Gym"""
    try:
        from gym.envs.registration import register
        register(
            id='TradingEnv-v0',
            entry_point='backend.app.rl_trading_env:TradingEnvironment',
            max_episode_steps=10000,
        )
        register(
            id='MultiAssetTradingEnv-v0',
            entry_point='backend.app.rl_trading_env:MultiAssetTradingEnvironment',
            max_episode_steps=10000,
        )
        logger.info("交易环境已注册到 Gym")
    except Exception as e:
        logger.warning(f"无法注册 Gym 环境: {e}")