"""
PPO 强化学习交易代理 - V2.2 深度学习策略引擎

包含:
- ActorCriticNetwork: Actor-Critic 共享特征提取网络
- PPOAgent: PPO 交易代理（clip 机制、GAE 优势估计、entropy bonus）
- Continuous action space（支持连续仓位比例 0~1）
- 复用 rl_agent.py 中的 TradingEnvironment
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict, List
import logging
from pathlib import Path

from .rl_agent import TradingEnvironment

logger = logging.getLogger(__name__)


class ActorCriticNetwork(nn.Module):
    """Actor-Critic 网络用于 PPO 交易代理

    共享特征提取层 + 独立 Actor/Critic 头
    输出连续动作空间：仓位比例 [0, 1]
    """

    def __init__(self, state_size: int, hidden_size: int = 256):
        super().__init__()

        # 共享特征提取
        self.shared = nn.Sequential(
            nn.Linear(state_size, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.BatchNorm1d(hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
        )

        # Actor 头：输出动作分布参数（均值和标准差）
        self.actor_mean = nn.Sequential(
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.ReLU(),
            nn.Linear(hidden_size // 4, 1),  # 输出仓位比例均值
        )
        self.actor_log_std = nn.Parameter(torch.zeros(1))  # 可学习的标准差参数

        # Critic 头：输出状态价值
        self.critic = nn.Sequential(
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.ReLU(),
            nn.Linear(hidden_size // 4, 1),  # 输出状态价值
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """前向传播

        Args:
            x: 状态张量 (batch, state_size)

        Returns:
            (action_mean, action_log_std, value)
        """
        # Handle batch size 1 for BatchNorm
        if x.dim() == 1:
            x = x.unsqueeze(0)

        features = self.shared(x)
        action_mean = self.actor_mean(features).squeeze(-1)  # (batch,)
        action_log_std = self.actor_log_std.expand_as(action_mean)  # (batch,)
        value = self.critic(features).squeeze(-1)  # (batch,)

        return action_mean, action_log_std, value

    def get_action(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """采样动作

        Args:
            state: 状态张量

        Returns:
            (action, log_prob, value, entropy)
        """
        action_mean, action_log_std, value = self.forward(state)
        action_std = torch.exp(action_log_std)

        # 从正态分布采样
        dist = torch.distributions.Normal(action_mean, action_std)
        action = dist.sample()

        # 将动作限制在 [0, 1] 范围（仓位比例）
        action = torch.clamp(action, 0, 1)

        log_prob = dist.log_prob(action).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)

        return action, log_prob, value, entropy

    def evaluate_actions(self, states: torch.Tensor, actions: torch.Tensor
                         ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """评估给定动作的 log_prob、value 和 entropy

        Args:
            states: 状态张量 (batch, state_size)
            actions: 动作张量 (batch,)

        Returns:
            (log_prob, value, entropy)
        """
        action_mean, action_log_std, value = self.forward(states)
        action_std = torch.exp(action_log_std)

        dist = torch.distributions.Normal(action_mean, action_std)
        log_prob = dist.log_prob(actions).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)

        return log_prob, value, entropy


class RolloutBuffer:
    """PPO 经验回放缓冲区，存储一轮交互数据"""

    def __init__(self):
        self.states: List[np.ndarray] = []
        self.actions: List[float] = []
        self.rewards: List[float] = []
        self.dones: List[bool] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []

    def push(self, state: np.ndarray, action: float, reward: float,
             done: bool, log_prob: float, value: float):
        """存储一步交互数据"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.dones.append(done)
        self.log_probs.append(log_prob)
        self.values.append(value)

    def clear(self):
        """清空缓冲区"""
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.dones.clear()
        self.log_probs.clear()
        self.values.clear()

    def __len__(self) -> int:
        return len(self.states)


class PPOAgent:
    """PPO（Proximal Policy Optimization）交易代理

    使用连续动作空间，输出仓位比例 [0, 1]。
    支持 clip 机制、GAE 优势估计和 entropy bonus。
    """

    def __init__(
        self,
        state_size: int,
        learning_rate: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        entropy_coef: float = 0.01,
        value_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        ppo_epochs: int = 10,
        mini_batch_size: int = 64,
    ):
        """
        Args:
            state_size: 状态空间维度
            learning_rate: 学习率
            gamma: 折扣因子
            gae_lambda: GAE lambda 参数
            clip_epsilon: PPO clip 范围
            entropy_coef: 熵正则化系数
            value_coef: 价值损失系数
            max_grad_norm: 梯度裁剪阈值
            ppo_epochs: PPO 更新轮数
            mini_batch_size: 小批量大小
        """
        self.device = torch.device("cpu")
        self.state_size = state_size
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.max_grad_norm = max_grad_norm
        self.ppo_epochs = ppo_epochs
        self.mini_batch_size = mini_batch_size

        # 创建网络
        self.network = ActorCriticNetwork(state_size).to(self.device)
        self.optimizer = optim.Adam(self.network.parameters(), lr=learning_rate)

        # 经验缓冲区
        self.buffer = RolloutBuffer()

    def select_action(self, state: np.ndarray, training: bool = True) -> Tuple[float, float, float]:
        """选择动作（连续仓位比例）

        Args:
            state: 状态向量
            training: 是否训练模式

        Returns:
            (action, log_prob, value)
        """
        state_t = torch.from_numpy(state).float().to(self.device)

        with torch.no_grad():
            if training:
                action, log_prob, value, _ = self.network.get_action(state_t)
            else:
                # 推理时使用均值作为动作
                action_mean, _, value = self.network(state_t)
                action = torch.clamp(action_mean, 0, 1)
                log_prob = torch.tensor(0.0)

        return float(action.cpu().item()), float(log_prob.cpu().item()), float(value.cpu().item())

    def compute_gae(self, next_value: float) -> Tuple[List[float], List[float]]:
        """计算 GAE（Generalized Advantage Estimation）

        Args:
            next_value: 最后一步的状态价值

        Returns:
            (advantages, returns)
        """
        rewards = self.buffer.rewards
        dones = self.buffer.dones
        values = self.buffer.values

        advantages = []
        gae = 0.0

        # 从后向前计算 GAE
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_val = next_value
            else:
                next_val = values[t + 1]

            next_non_terminal = 1.0 - float(dones[t])
            delta = rewards[t] + self.gamma * next_val * next_non_terminal - values[t]
            gae = delta + self.gamma * self.gae_lambda * next_non_terminal * gae
            advantages.insert(0, gae)

        # 计算 returns = advantages + values
        returns = [adv + val for adv, val in zip(advantages, values)]

        return advantages, returns

    def update(self, next_value: float) -> Dict[str, float]:
        """PPO 更新

        Args:
            next_value: 最后一步的状态价值

        Returns:
            训练指标字典
        """
        if len(self.buffer) == 0:
            return {}

        # 计算 GAE
        advantages, returns = self.compute_gae(next_value)

        # 转换为张量
        states = torch.from_numpy(np.array(self.buffer.states)).float().to(self.device)
        actions = torch.tensor(self.buffer.actions, dtype=torch.float32).to(self.device)
        old_log_probs = torch.tensor(self.buffer.log_probs, dtype=torch.float32).to(self.device)
        advantages = torch.tensor(advantages, dtype=torch.float32).to(self.device)
        returns = torch.tensor(returns, dtype=torch.float32).to(self.device)

        # 标准化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_loss = 0.0
        num_updates = 0

        for _ in range(self.ppo_epochs):
            # 随机打乱数据
            indices = torch.randperm(len(states)).to(self.device)

            for start in range(0, len(states), self.mini_batch_size):
                end = start + self.mini_batch_size
                batch_indices = indices[start:end]

                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                batch_advantages = advantages[batch_indices]
                batch_returns = returns[batch_indices]

                # 评估动作
                new_log_probs, new_values, entropy = self.network.evaluate_actions(
                    batch_states, batch_actions
                )

                # PPO clip 损失
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # 价值损失
                value_loss = nn.functional.mse_loss(new_values, batch_returns)

                # 熵 bonus
                entropy_loss = -entropy.mean()

                # 总损失
                loss = policy_loss + self.value_coef * value_loss + self.entropy_coef * entropy_loss

                # 优化
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm)
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.mean().item()
                total_loss += loss.item()
                num_updates += 1

        # 清空缓冲区
        self.buffer.clear()

        metrics = {
            'policy_loss': total_policy_loss / max(num_updates, 1),
            'value_loss': total_value_loss / max(num_updates, 1),
            'entropy': total_entropy / max(num_updates, 1),
            'total_loss': total_loss / max(num_updates, 1),
            'num_updates': num_updates,
        }

        return metrics

    def save(self, path: str):
        """保存代理状态"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            'network_state_dict': self.network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'state_size': self.state_size,
            'gamma': self.gamma,
            'gae_lambda': self.gae_lambda,
            'clip_epsilon': self.clip_epsilon,
            'entropy_coef': self.entropy_coef,
            'value_coef': self.value_coef,
            'ppo_epochs': self.ppo_epochs,
            'mini_batch_size': self.mini_batch_size,
        }, str(path / 'ppo_agent.pt'))
        logger.info(f"PPO agent saved to {path}")

    def load(self, path: str):
        """加载代理状态"""
        path = Path(path)
        checkpoint = torch.load(str(path / 'ppo_agent.pt'), map_location=self.device, weights_only=False)
        self.network.load_state_dict(checkpoint['network_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.state_size = checkpoint.get('state_size', self.state_size)
        self.gamma = checkpoint.get('gamma', self.gamma)
        self.gae_lambda = checkpoint.get('gae_lambda', self.gae_lambda)
        self.clip_epsilon = checkpoint.get('clip_epsilon', self.clip_epsilon)
        self.entropy_coef = checkpoint.get('entropy_coef', self.entropy_coef)
        self.value_coef = checkpoint.get('value_coef', self.value_coef)
        self.ppo_epochs = checkpoint.get('ppo_epochs', self.ppo_epochs)
        self.mini_batch_size = checkpoint.get('mini_batch_size', self.mini_batch_size)
        self.network.eval()
        logger.info(f"PPO agent loaded from {path}")


class PPOTrainer:
    """PPO 交易代理训练器

    复用 TradingEnvironment，将连续动作（仓位比例）映射为交易行为。
    """

    def __init__(self, env: TradingEnvironment, agent: PPOAgent):
        self.env = env
        self.agent = agent

    def _action_to_trade(self, current_position_ratio: float, target_ratio: float,
                         current_price: float) -> int:
        """将连续仓位比例映射为离散交易动作

        Args:
            current_position_ratio: 当前仓位比例
            target_ratio: 目标仓位比例（PPO 输出）
            current_price: 当前价格

        Returns:
            交易动作: 0=hold, 1=buy, 2=sell
        """
        diff = target_ratio - current_position_ratio

        # 设置阈值避免频繁交易
        threshold = 0.05
        if diff > threshold:
            return 1  # 买入
        elif diff < -threshold:
            return 2  # 卖出
        else:
            return 0  # 持有

    def collect_rollout(self, max_steps: Optional[int] = None) -> float:
        """收集一轮交互数据

        Args:
            max_steps: 最大步数（None = 完整数据集）

        Returns:
            最后一步的状态价值
        """
        state = self.env.reset()
        episode_reward = 0
        steps = 0

        while True:
            # 选择动作
            action, log_prob, value = self.agent.select_action(state, training=True)

            # 将连续动作映射为离散交易动作
            current_price = self.env.df.iloc[self.env.current_step]['close']
            current_position_ratio = self.env.position * current_price / (self.env.portfolio_value + 1e-8)
            trade_action = self._action_to_trade(current_position_ratio, action, current_price)

            # 执行交易动作
            next_state, reward, done, info = self.env.step(trade_action)

            # 存储经验（使用连续动作和 log_prob）
            self.agent.buffer.push(state, action, reward, done, log_prob, value)

            episode_reward += reward
            state = next_state
            steps += 1

            if done or (max_steps and steps >= max_steps):
                break

        # 获取最后一步的价值
        if not done:
            _, _, next_value = self.agent.select_action(state, training=False)
        else:
            next_value = 0.0

        return next_value

    def train(self, num_episodes: int = 500, max_steps: Optional[int] = None,
              update_freq: int = 1) -> dict:
        """训练 PPO 代理

        Args:
            num_episodes: 训练轮数
            max_steps: 每轮最大步数
            update_freq: 每多少轮更新一次网络

        Returns:
            训练指标字典
        """
        episode_rewards = []
        portfolio_values = []
        best_return = -float('inf')
        best_model_state = None
        all_metrics = []

        logger.info(f"开始 PPO 训练, episodes={num_episodes}")

        for episode in range(num_episodes):
            # 收集经验
            next_value = self.collect_rollout(max_steps=max_steps)

            # PPO 更新
            if (episode + 1) % update_freq == 0:
                metrics = self.agent.update(next_value)
                all_metrics.append(metrics)

            # 记录指标
            episode_reward = sum(self.env.portfolio_history) - self.env.initial_capital
            final_return = (self.env.portfolio_value - self.env.initial_capital) / self.env.initial_capital
            episode_rewards.append(final_return)
            portfolio_values.append(self.env.portfolio_value)

            if final_return > best_return:
                best_return = final_return
                best_model_state = {k: v.cpu().clone() for k, v in self.agent.network.state_dict().items()}

            if (episode + 1) % 50 == 0:
                avg_reward = np.mean(episode_rewards[-50:])
                last_metrics = all_metrics[-1] if all_metrics else {}
                logger.info(
                    f"Episode {episode + 1}/{num_episodes} - "
                    f"Avg Return: {avg_reward:.4f}, "
                    f"Return: {final_return:.4f}, "
                    f"Policy Loss: {last_metrics.get('policy_loss', 0):.4f}, "
                    f"Value Loss: {last_metrics.get('value_loss', 0):.4f}, "
                    f"Entropy: {last_metrics.get('entropy', 0):.4f}"
                )

        # 计算 Sharpe ratio
        returns = np.diff(episode_rewards)
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0

        metrics = {
            'episode_rewards': episode_rewards,
            'portfolio_values': portfolio_values,
            'best_return': best_return,
            'final_return': final_return,
            'sharpe_ratio': sharpe_ratio,
            'total_episodes': num_episodes,
            'training_metrics': all_metrics,
        }

        logger.info(f"PPO 训练完成, 最佳收益率: {best_return:.4f}, Sharpe: {sharpe_ratio:.4f}")
        return metrics

    def evaluate(self, num_episodes: int = 10) -> dict:
        """评估训练后的代理"""
        returns = []
        total_rewards = []

        for _ in range(num_episodes):
            state = self.env.reset()
            episode_reward = 0

            while True:
                action, _, _ = self.agent.select_action(state, training=False)

                # 映射为交易动作
                current_price = self.env.df.iloc[self.env.current_step]['close']
                current_position_ratio = self.env.position * current_price / (self.env.portfolio_value + 1e-8)
                trade_action = self._action_to_trade(current_position_ratio, action, current_price)

                next_state, reward, done, info = self.env.step(trade_action)
                episode_reward += reward
                state = next_state

                if done:
                    break

            returns.append(info.get('return', 0))
            total_rewards.append(episode_reward)

        return {
            'avg_return': float(np.mean(returns)),
            'std_return': float(np.std(returns)),
            'avg_reward': float(np.mean(total_rewards)),
            'win_rate': float(np.mean([r > 0 for r in returns])),
            'num_episodes': num_episodes,
        }

    def backtest(self, df: pd.DataFrame) -> dict:
        """在历史数据上回测代理

        Args:
            df: OHLCV DataFrame

        Returns:
            回测结果字典
        """
        env = TradingEnvironment(df, initial_capital=self.env.initial_capital,
                                  commission=self.env.commission,
                                  max_position=self.env.max_position)
        state = env.reset()
        trades = []
        portfolio_values = [env.initial_capital]

        while True:
            action, _, _ = self.agent.select_action(state, training=False)

            # 映射为交易动作
            current_price = env.df.iloc[env.current_step]['close']
            current_position_ratio = env.position * current_price / (env.portfolio_value + 1e-8)
            trade_action = self._action_to_trade(current_position_ratio, action, current_price)

            next_state, reward, done, info = env.step(trade_action)

            if info.get('action') in ('buy', 'sell'):
                trades.append({
                    'step': info['step'],
                    'action': info['action'],
                    'price': info['price'],
                    'shares': info.get('shares', 0),
                    'portfolio_value': info['portfolio_value'],
                    'target_ratio': action,
                })

            portfolio_values.append(info['portfolio_value'])
            state = next_state

            if done:
                break

        # 计算指标
        pv = np.array(portfolio_values)
        total_return = (pv[-1] - pv[0]) / pv[0]
        peak = np.maximum.accumulate(pv)
        drawdown = (pv - peak) / peak
        max_drawdown = float(np.min(drawdown))

        daily_returns = np.diff(pv) / pv[:-1]
        if len(daily_returns) > 0 and np.std(daily_returns) > 0:
            sharpe = float(np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252))
        else:
            sharpe = 0.0

        return {
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'final_portfolio_value': float(pv[-1]),
            'num_trades': len(trades),
            'trades': trades,
            'portfolio_values': portfolio_values,
        }
