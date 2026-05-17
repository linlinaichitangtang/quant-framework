"""
强化学习交易代理 - V2.2 深度学习策略引擎

包含:
- TradingEnvironment: 量化交易强化学习环境
- DQNNetwork: Deep Q-Network
- ReplayBuffer: 经验回放缓冲区
- DQNAgent: DQN 交易代理
- TradingTrainer: 交易代理训练器
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
import random
from collections import deque
from typing import Optional, Tuple, Dict, List
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class TradingEnvironment:
    """量化交易强化学习环境"""

    def __init__(self, df: pd.DataFrame, initial_capital: float = 100000,
                 commission: float = 0.0003, max_position: float = 0.1):
        """
        Args:
            df: DataFrame with OHLCV + features
            initial_capital: 初始资金
            commission: 手续费率
            max_position: 单只股票最大仓位比例
        """
        self.df = df.copy().reset_index(drop=True)
        self.initial_capital = initial_capital
        self.commission = commission
        self.max_position = max_position

        # State
        self.current_step = 0
        self.cash = initial_capital
        self.position = 0  # shares held
        self.portfolio_value = initial_capital
        self.entry_price = 0.0

        # History for reward calculation
        self.portfolio_history = [initial_capital]

        # Identify feature columns (numeric, non-OHLCV)
        ohlcv_cols = {'open', 'high', 'low', 'close', 'volume'}
        self.feature_cols = [c for c in self.df.columns
                             if c not in ohlcv_cols and self.df[c].dtype in [np.float64, np.float32, np.int64]]
        self.state_size = len(self.feature_cols) + 3  # features + position_norm + portfolio_norm + price_norm

    def reset(self) -> np.ndarray:
        """重置环境"""
        self.current_step = 0
        self.cash = self.initial_capital
        self.position = 0
        self.portfolio_value = self.initial_capital
        self.entry_price = 0.0
        self.portfolio_history = [self.initial_capital]
        return self._get_state()

    def _get_state(self) -> np.ndarray:
        """获取当前状态向量"""
        row = self.df.iloc[self.current_step]

        # Feature values
        features = []
        for col in self.feature_cols:
            val = row.get(col, 0)
            if pd.isna(val):
                val = 0
            features.append(float(val))

        # Position info
        position_norm = self.position * row['close'] / (self.portfolio_value + 1e-8)
        portfolio_norm = self.portfolio_value / self.initial_capital
        price_norm = row['close'] / (self.df['close'].mean() + 1e-8)

        state = features + [position_norm, portfolio_norm, price_norm]
        return np.array(state, dtype=np.float32)

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, dict]:
        """执行一步

        Args:
            action: 0=hold, 1=buy, 2=sell

        Returns:
            (next_state, reward, done, info)
        """
        current_price = self.df.iloc[self.current_step]['close']
        info = {'step': self.current_step, 'price': current_price}

        # Execute action
        if action == 1:  # Buy
            max_shares = int(self.cash * self.max_position / (current_price * (1 + self.commission)))
            if max_shares > 0:
                cost = max_shares * current_price * (1 + self.commission)
                self.cash -= cost
                self.position += max_shares
                self.entry_price = current_price
                info['action'] = 'buy'
                info['shares'] = max_shares

        elif action == 2:  # Sell
            if self.position > 0:
                revenue = self.position * current_price * (1 - self.commission)
                self.cash += revenue
                info['action'] = 'sell'
                info['shares'] = self.position
                info['pnl'] = (current_price - self.entry_price) * self.position
                self.position = 0
                self.entry_price = 0.0
        else:
            info['action'] = 'hold'

        # Update portfolio value
        self.portfolio_value = self.cash + self.position * current_price
        self.portfolio_history.append(self.portfolio_value)

        # Move to next step
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1

        # Calculate reward
        if len(self.portfolio_history) >= 2:
            reward = (self.portfolio_value - self.portfolio_history[-2]) / self.portfolio_history[-2]
            # Risk penalty for large drawdown
            peak = max(self.portfolio_history)
            drawdown = (self.portfolio_value - peak) / (peak + 1e-8)
            reward -= 0.1 * abs(min(drawdown, 0))
        else:
            reward = 0.0

        next_state = self._get_state() if not done else np.zeros(self.state_size, dtype=np.float32)
        info['portfolio_value'] = self.portfolio_value
        info['return'] = (self.portfolio_value - self.initial_capital) / self.initial_capital

        return next_state, reward, done, info


class DQNNetwork(nn.Module):
    """Deep Q-Network for trading"""

    def __init__(self, state_size: int, action_size: int = 3, hidden_size: int = 256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_size, hidden_size),
            nn.BatchNorm1d(hidden_size),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.BatchNorm1d(hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size // 2, hidden_size // 4),
            nn.ReLU(),
            nn.Linear(hidden_size // 4, action_size)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Handle batch size 1 for BatchNorm
        if x.dim() == 1:
            x = x.unsqueeze(0)
        if x.size(0) == 1:
            # BatchNorm 不支持 batch_size=1，跳过 BatchNorm 层
            out = x
            for module in self.net:
                if isinstance(module, nn.BatchNorm1d):
                    continue
                out = module(out)
            return out
        return self.net(x)


class ReplayBuffer:
    """Experience replay buffer"""

    def __init__(self, capacity: int = 100000):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple:
        batch = random.sample(self.buffer, batch_size)
        states = np.array([t[0] for t in batch])
        actions = np.array([t[1] for t in batch])
        rewards = np.array([t[2] for t in batch])
        next_states = np.array([t[3] for t in batch])
        dones = np.array([t[4] for t in batch])
        return states, actions, rewards, next_states, dones

    def __len__(self):
        return len(self.buffer)


class DQNAgent:
    """DQN 交易代理"""

    def __init__(self, state_size: int, action_size: int = 3,
                 learning_rate: float = 0.001, gamma: float = 0.99,
                 epsilon_start: float = 1.0, epsilon_end: float = 0.01,
                 epsilon_decay: float = 0.995):
        self.device = torch.device("cpu")
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay

        self.policy_net = DQNNetwork(state_size, action_size).to(self.device)
        self.target_net = DQNNetwork(state_size, action_size).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        self.memory = ReplayBuffer()

    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Epsilon-greedy action selection"""
        if training and random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)

        with torch.no_grad():
            state_t = torch.from_numpy(state).float().unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_t)
            return int(q_values.argmax(dim=1).item())

    def train_step(self, batch_size: int = 64) -> float:
        """Train on a batch of experiences"""
        if len(self.memory) < batch_size:
            return 0.0

        states, actions, rewards, next_states, dones = self.memory.sample(batch_size)

        states = torch.from_numpy(states).float().to(self.device)
        actions = torch.from_numpy(actions).long().to(self.device)
        rewards = torch.from_numpy(rewards).float().to(self.device)
        next_states = torch.from_numpy(next_states).float().to(self.device)
        dones = torch.from_numpy(dones).float().to(self.device)

        # Current Q values
        q_values = self.policy_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)

        # Target Q values
        with torch.no_grad():
            next_q_values = self.target_net(next_states).max(dim=1)[0]
            target_q_values = rewards + self.gamma * next_q_values * (1 - dones)

        # Loss
        loss = nn.functional.mse_loss(q_values, target_q_values)

        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        self.optimizer.step()

        return loss.item()

    def update_target_network(self):
        """Update target network with policy network weights"""
        self.target_net.load_state_dict(self.policy_net.state_dict())

    def save(self, path: str):
        """Save agent state"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'target_net': self.target_net.state_dict(),
            'epsilon': self.epsilon,
            'state_size': self.state_size,
            'action_size': self.action_size,
        }, str(path / 'dqn_agent.pt'))
        logger.info(f"DQN agent saved to {path}")

    def load(self, path: str):
        """Load agent state"""
        path = Path(path)
        checkpoint = torch.load(str(path / 'dqn_agent.pt'), map_location=self.device, weights_only=False)
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['target_net'])
        self.epsilon = checkpoint.get('epsilon', self.epsilon_end)
        self.policy_net.eval()
        logger.info(f"DQN agent loaded from {path}")


class TradingTrainer:
    """交易代理训练器"""

    def __init__(self, env: TradingEnvironment, agent: DQNAgent):
        self.env = env
        self.agent = agent

    def train(self, num_episodes: int = 500, max_steps: int = None,
              batch_size: int = 64, target_update_freq: int = 10) -> dict:
        """Train the trading agent

        Args:
            num_episodes: Number of training episodes
            max_steps: Max steps per episode (None = full dataset)
            batch_size: Training batch size
            target_update_freq: Target network update frequency

        Returns:
            Training metrics dict
        """
        episode_rewards = []
        portfolio_values = []
        best_return = -float('inf')
        best_model_state = None

        logger.info(f"开始 DQN 训练, episodes={num_episodes}")

        for episode in range(num_episodes):
            state = self.env.reset()
            total_reward = 0
            steps = 0

            while True:
                action = self.agent.select_action(state, training=True)
                next_state, reward, done, info = self.env.step(action)

                self.agent.memory.push(state, action, reward, next_state, done)

                # Train
                self.agent.train_step(batch_size)

                total_reward += reward
                state = next_state
                steps += 1

                if done or (max_steps and steps >= max_steps):
                    break

            # Update epsilon
            self.agent.epsilon = max(
                self.agent.epsilon_end,
                self.agent.epsilon * self.agent.epsilon_decay
            )

            # Update target network
            if (episode + 1) % target_update_freq == 0:
                self.agent.update_target_network()

            # Track metrics
            final_return = info.get('return', 0)
            episode_rewards.append(total_reward)
            portfolio_values.append(self.env.portfolio_value)

            if final_return > best_return:
                best_return = final_return
                best_model_state = {k: v.cpu().clone() for k, v in self.agent.policy_net.state_dict().items()}

            if (episode + 1) % 50 == 0:
                avg_reward = np.mean(episode_rewards[-50:])
                logger.info(
                    f"Episode {episode + 1}/{num_episodes} - "
                    f"Avg Reward: {avg_reward:.4f}, "
                    f"Return: {final_return:.4f}, "
                    f"Epsilon: {self.agent.epsilon:.4f}"
                )

        # Calculate Sharpe ratio
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
            'final_epsilon': self.agent.epsilon,
        }

        logger.info(f"DQN 训练完成, 最佳收益率: {best_return:.4f}, Sharpe: {sharpe_ratio:.4f}")
        return metrics

    def evaluate(self, num_episodes: int = 10) -> dict:
        """Evaluate trained agent (no exploration)"""
        returns = []
        total_rewards = []

        for _ in range(num_episodes):
            state = self.env.reset()
            episode_reward = 0

            while True:
                action = self.agent.select_action(state, training=False)
                next_state, reward, done, info = self.env.step(action)
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
        """Run agent on historical data and return trade log

        Args:
            df: OHLCV DataFrame

        Returns:
            Backtest results dict
        """
        env = TradingEnvironment(df, initial_capital=self.env.initial_capital,
                                  commission=self.env.commission,
                                  max_position=self.env.max_position)
        state = env.reset()
        trades = []
        portfolio_values = [env.initial_capital]

        while True:
            action = self.agent.select_action(state, training=False)
            next_state, reward, done, info = env.step(action)

            if info.get('action') in ('buy', 'sell'):
                trades.append({
                    'step': info['step'],
                    'action': info['action'],
                    'price': info['price'],
                    'shares': info.get('shares', 0),
                    'portfolio_value': info['portfolio_value'],
                })

            portfolio_values.append(info['portfolio_value'])
            state = next_state

            if done:
                break

        # Calculate metrics
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
